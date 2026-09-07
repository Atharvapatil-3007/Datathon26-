"""In-memory session store for chatbot conversations.

State kept per session:
  * ``dataset_id``, ``analysis_mode``, optional secondary / market ids
  * short chat history (bounded)
  * "last" hints — metric / period / entity — so the next turn can
    resolve follow-ups without asking the LLM.

The store is deliberately in-memory and single-process. Sessions are
cheap: recreating one just costs the client an extra round trip to
provide dataset context again. Nothing sensitive is persisted here.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from app.chatbot.types import (
    AnswerClassification,
    ChatIntent,
    ChatMessage,
    ChatRole,
    ConfidenceLevel,
    EntityRef,
    PeriodRef,
)


MAX_HISTORY = 20
SESSION_TTL_SECONDS = 6 * 60 * 60  # 6 hours


@dataclass
class SessionState:
    session_id: str
    dataset_id: Optional[str] = None
    analysis_mode: Optional[str] = None
    secondary_dataset_id: Optional[str] = None
    market_dataset_id: Optional[str] = None

    history: Deque[ChatMessage] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))

    # Slot memory (populated on assistant response)
    last_intent: Optional[ChatIntent] = None
    last_metric_id: Optional[str] = None
    last_period: Optional[PeriodRef] = None
    last_entity: Optional[EntityRef] = None

    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity = time.time()

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "dataset_id": self.dataset_id,
            "analysis_mode": self.analysis_mode,
            "secondary_dataset_id": self.secondary_dataset_id,
            "market_dataset_id": self.market_dataset_id,
            "history": [m.to_dict() for m in self.history],
            "last_intent": self.last_intent.value if self.last_intent else None,
            "last_metric_id": self.last_metric_id,
            "last_period": self.last_period.to_dict() if self.last_period else None,
            "last_entity": self.last_entity.value if self.last_entity else None,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }


class SessionStore:
    """Thread-safe process-wide session dict."""

    def __init__(self, *, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Lookup / creation
    # ------------------------------------------------------------------
    def get_or_create(
        self,
        session_id: Optional[str],
        *,
        dataset_id: Optional[str] = None,
        analysis_mode: Optional[str] = None,
        secondary_dataset_id: Optional[str] = None,
        market_dataset_id: Optional[str] = None,
    ) -> SessionState:
        with self._lock:
            self._sweep_expired_locked()
            if session_id and session_id in self._sessions:
                state = self._sessions[session_id]
                # Refresh dataset context if the client provided new values.
                # If the dataset or mode changed we intentionally reset
                # slot memory (the previous conversation no longer applies).
                if dataset_id and state.dataset_id != dataset_id:
                    state.dataset_id = dataset_id
                    state.last_metric_id = None
                    state.last_period = None
                    state.last_entity = None
                    state.last_intent = None
                if analysis_mode and state.analysis_mode != analysis_mode:
                    state.analysis_mode = analysis_mode
                    state.last_metric_id = None
                    state.last_period = None
                    state.last_entity = None
                    state.last_intent = None
                if secondary_dataset_id is not None:
                    state.secondary_dataset_id = secondary_dataset_id or None
                if market_dataset_id is not None:
                    state.market_dataset_id = market_dataset_id or None
                state.touch()
                return state

            new_id = session_id or _new_id()
            state = SessionState(
                session_id=new_id,
                dataset_id=dataset_id,
                analysis_mode=analysis_mode,
                secondary_dataset_id=secondary_dataset_id or None,
                market_dataset_id=market_dataset_id or None,
            )
            self._sessions[new_id] = state
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            self._sweep_expired_locked()
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    # ------------------------------------------------------------------
    # Message + slot writes
    # ------------------------------------------------------------------
    def append_user(self, state: SessionState, text: str) -> None:
        with self._lock:
            state.history.append(ChatMessage(role=ChatRole.USER, text=text))
            state.touch()

    def append_assistant(
        self,
        state: SessionState,
        *,
        text: str,
        intent: ChatIntent,
        classification: AnswerClassification,
        confidence: ConfidenceLevel,
        evidence=(),
        calculations=(),
        metric_id: Optional[str] = None,
        period: Optional[PeriodRef] = None,
        entity: Optional[EntityRef] = None,
    ) -> ChatMessage:
        with self._lock:
            msg = ChatMessage(
                role=ChatRole.ASSISTANT,
                text=text,
                intent=intent,
                classification=classification,
                confidence=confidence,
                evidence=list(evidence),
                calculations=list(calculations),
            )
            state.history.append(msg)
            state.last_intent = intent
            if metric_id is not None:
                state.last_metric_id = metric_id
            if period is not None:
                state.last_period = period
            if entity is not None:
                state.last_entity = entity
            state.touch()
            return msg

    def history_for(self, state: SessionState) -> List[ChatMessage]:
        with self._lock:
            return list(state.history)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _sweep_expired_locked(self) -> None:
        if not self._ttl:
            return
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > self._ttl
        ]
        for sid in expired:
            self._sessions.pop(sid, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_store_instance: Optional[SessionStore] = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = SessionStore()
    return _store_instance


def reset_session_store_for_tests() -> None:
    global _store_instance
    with _store_lock:
        _store_instance = None


def _new_id() -> str:
    return uuid.uuid4().hex
