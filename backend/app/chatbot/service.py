"""Chatbot service — orchestrates the full pipeline.

Given a question and dataset context this module:

  1. Sends the raw question through the guardrail. If refused, returns an
     ``AnswerClassification.REFUSED`` response immediately.
  2. Resolves conversation state (previous metric / period / entity) from
     the session store to enable follow-up questions.
  3. Classifies the question into a ``ClassifiedQuery``.
  4. Builds (or reuses cached) ``ChatContext`` for the current mode +
     dataset(s).
  5. Runs the query engine against the context.
  6. Renders the deterministic answer, optionally paraphrasing via LLM.
  7. Records the exchange in the session store and returns a ``ChatResponse``.

There is exactly one public entrypoint: ``ChatbotService.handle_query``.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Optional

from app.analysis.types import AnalysisMode
from app.chatbot import answer_generator, llm_client
from app.chatbot.classifier import ConversationState, classify
from app.chatbot.context_builder import ChatContext, build_context
from app.chatbot.exceptions import ChatbotError
from app.chatbot.guardrail import evaluate as guardrail_evaluate
from app.chatbot.prompts import (
    MISSING_ANALYSIS_MESSAGE,
    NO_DATASET_MESSAGE,
)
from app.chatbot.query_engine import answer as run_query_engine
from app.chatbot.session_store import SessionState, get_session_store
from app.chatbot.suggestions import suggest_followups, suggest_starter_questions
from app.chatbot.types import (
    AnswerClassification,
    ChatContextInfo,
    ChatIntent,
    ChatResponse,
    ConfidenceLevel,
    EntityRef,
    EvidenceBundle,
)
from app.ingestion.exceptions import DatasetNotFoundError
from app.utils.logging import get_logger


log = get_logger(__name__)


class ChatbotService:
    """Facade over the whole chatbot pipeline."""

    # ------------------------------------------------------------------
    # Session helpers exposed for the API layer
    # ------------------------------------------------------------------
    def start_session(
        self,
        *,
        dataset_id: Optional[str],
        analysis_mode: Optional[str],
        secondary_dataset_id: Optional[str] = None,
        market_dataset_id: Optional[str] = None,
    ) -> SessionState:
        return get_session_store().get_or_create(
            None,
            dataset_id=dataset_id,
            analysis_mode=analysis_mode,
            secondary_dataset_id=secondary_dataset_id,
            market_dataset_id=market_dataset_id,
        )

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return get_session_store().get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return get_session_store().delete(session_id)

    def suggestions_for(
        self,
        *,
        dataset_id: str,
        analysis_mode: Optional[str],
        secondary_dataset_id: Optional[str] = None,
        market_dataset_id: Optional[str] = None,
        last_intent: Optional[str] = None,
        limit: int = 6,
    ) -> List[str]:
        try:
            ctx = build_context(
                analysis_mode=analysis_mode or AnalysisMode.SELF_ANALYSIS.value,
                dataset_id=dataset_id,
                secondary_dataset_id=secondary_dataset_id,
                market_dataset_id=market_dataset_id,
            )
        except DatasetNotFoundError:
            return []
        except ChatbotError:
            # Missing counterparty dataset — fall back to a generic list.
            return _generic_starters(analysis_mode)
        if last_intent:
            return suggest_followups(ctx, last_intent, limit=limit)
        return suggest_starter_questions(ctx, limit=limit)

    # ------------------------------------------------------------------
    # Main entrypoint
    # ------------------------------------------------------------------
    def handle_query(
        self,
        *,
        message: str,
        session_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        analysis_mode: Optional[str] = None,
        secondary_dataset_id: Optional[str] = None,
        market_dataset_id: Optional[str] = None,
        primary_display_name: Optional[str] = None,
        secondary_display_name: Optional[str] = None,
        market_display_name: Optional[str] = None,
    ) -> ChatResponse:
        started = time.perf_counter()

        store = get_session_store()
        session = store.get_or_create(
            session_id,
            dataset_id=dataset_id,
            analysis_mode=analysis_mode,
            secondary_dataset_id=secondary_dataset_id,
            market_dataset_id=market_dataset_id,
        )

        # 1. Guardrail
        has_history = len(session.history) > 0
        verdict = guardrail_evaluate(message, has_conversation_history=has_history)

        # Always record the user's message on the session — even for refusals —
        # so they can see the exchange in the history.
        store.append_user(session, message)

        if not verdict.allowed:
            refusal = verdict.refusal_message or "That question is outside my scope."
            msg = store.append_assistant(
                session,
                text=refusal,
                intent=ChatIntent.UNRELATED,
                classification=AnswerClassification.REFUSED,
                confidence=ConfidenceLevel.NONE,
            )
            log.info(
                "chatbot_refusal",
                session_id=session.session_id,
                category=verdict.category,
                reason=verdict.reason,
            )
            return _build_response(
                session,
                msg_id=id(msg),
                answer=refusal,
                intent=ChatIntent.UNRELATED,
                classification=AnswerClassification.REFUSED,
                confidence=ConfidenceLevel.NONE,
                bundle=None,
                context=_context_info(session, primary_display_name, secondary_display_name, market_display_name),
                suggestions=_generic_starters(session.analysis_mode),
                warnings=[verdict.reason] if verdict.reason else [],
            )

        # 2. Precondition — a dataset must be available.
        if not session.dataset_id:
            msg = store.append_assistant(
                session,
                text=NO_DATASET_MESSAGE,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
            )
            return _build_response(
                session,
                msg_id=id(msg),
                answer=NO_DATASET_MESSAGE,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
                bundle=None,
                context=_context_info(session, primary_display_name, secondary_display_name, market_display_name),
                suggestions=[],
            )

        # 3. Build (or reuse) analytical context.
        try:
            ctx = build_context(
                analysis_mode=session.analysis_mode or AnalysisMode.SELF_ANALYSIS.value,
                dataset_id=session.dataset_id,
                secondary_dataset_id=session.secondary_dataset_id,
                market_dataset_id=session.market_dataset_id,
                primary_display_name=primary_display_name,
                secondary_display_name=secondary_display_name,
                market_display_name=market_display_name,
            )
        except DatasetNotFoundError as exc:
            msg = store.append_assistant(
                session,
                text=f"I couldn't find the dataset for this session: {exc.message}",
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
            )
            return _build_response(
                session,
                msg_id=id(msg),
                answer=exc.message,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
                bundle=None,
                context=_context_info(session, primary_display_name, secondary_display_name, market_display_name),
                suggestions=[],
                warnings=[exc.message],
            )
        except ChatbotError as exc:
            # e.g. merger mode without secondary dataset
            msg = store.append_assistant(
                session,
                text=exc.message,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
            )
            return _build_response(
                session,
                msg_id=id(msg),
                answer=exc.message,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
                bundle=None,
                context=_context_info(session, primary_display_name, secondary_display_name, market_display_name),
                suggestions=[],
                warnings=[exc.message],
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("chatbot_context_build_failed")
            fallback = (
                "I couldn't assemble the analytical context for this dataset. "
                f"Details: {exc}"
            )
            msg = store.append_assistant(
                session,
                text=fallback,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
            )
            return _build_response(
                session,
                msg_id=id(msg),
                answer=fallback,
                intent=ChatIntent.UNSUPPORTED,
                classification=AnswerClassification.UNAVAILABLE,
                confidence=ConfidenceLevel.NONE,
                bundle=None,
                context=_context_info(session, primary_display_name, secondary_display_name, market_display_name),
                suggestions=[],
                warnings=[str(exc)],
            )

        # 4. Classify the question with follow-up-aware state.
        classified = classify(
            message,
            state=ConversationState(
                last_metric_id=session.last_metric_id,
                last_period=session.last_period,
                last_entity=session.last_entity,
                last_intent=session.last_intent,
            ),
            analysis_mode=ctx.analysis_mode.value,
        )
        log.info(
            "chatbot_classified",
            session_id=session.session_id,
            intent=classified.intent.value,
            metric_ids=classified.slots.metric_ids,
            periods=[p.label for p in classified.slots.periods],
            entity=classified.slots.entity.value,
            used_context=classified.used_context,
        )

        # 5. Run the query engine.
        bundle: EvidenceBundle = run_query_engine(classified, ctx)

        # 6. Missing analysis fallback (self mode without an analysis_result).
        if (
            classified.intent
            in (
                ChatIntent.FINANCIAL_HEALTH,
                ChatIntent.RISK_ANALYSIS,
                ChatIntent.STRENGTH_ANALYSIS,
                ChatIntent.OPPORTUNITY_ANALYSIS,
                ChatIntent.WEAKNESS_ANALYSIS,
                ChatIntent.RECOMMENDATION,
            )
            and ctx.analysis_result is None
        ):
            bundle.headline = MISSING_ANALYSIS_MESSAGE
            bundle.classification = AnswerClassification.UNAVAILABLE
            bundle.confidence = ConfidenceLevel.NONE

        # 7. Render deterministic answer + optional LLM paraphrase.
        deterministic = answer_generator.render_answer(bundle)
        answer_text = llm_client.paraphrase(
            deterministic, bundle.evidence, intent_label=classified.intent.value
        )

        # 8. Update session slot memory + record the assistant message.
        msg = store.append_assistant(
            session,
            text=answer_text,
            intent=classified.intent,
            classification=bundle.classification,
            confidence=bundle.confidence,
            evidence=bundle.evidence,
            calculations=bundle.calculations,
            metric_id=bundle.metric_hint or (
                classified.slots.metric_ids[0] if classified.slots.metric_ids else None
            ),
            period=bundle.period_hint or (
                classified.slots.periods[0] if classified.slots.periods else None
            ),
            entity=bundle.entity_hint or classified.slots.entity,
        )

        # 9. Suggested follow-ups.
        followups = suggest_followups(ctx, classified.intent.value, limit=4)

        log.info(
            "chatbot_answered",
            session_id=session.session_id,
            intent=classified.intent.value,
            classification=bundle.classification.value,
            evidence_count=len(bundle.evidence),
            calculation_count=len(bundle.calculations),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

        return _build_response(
            session,
            msg_id=id(msg),
            answer=answer_text,
            intent=classified.intent,
            classification=bundle.classification,
            confidence=bundle.confidence,
            bundle=bundle,
            context=_context_info(session, ctx.primary.display_name, secondary_display_name, market_display_name),
            suggestions=followups,
            used_context=classified.used_context,
            warnings=bundle.warnings,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _context_info(
    session: SessionState,
    primary_name: Optional[str],
    secondary_name: Optional[str],
    market_name: Optional[str],
) -> ChatContextInfo:
    return ChatContextInfo(
        dataset_id=session.dataset_id,
        dataset_name=primary_name,
        analysis_mode=session.analysis_mode,
        secondary_dataset_id=session.secondary_dataset_id,
        secondary_dataset_name=secondary_name,
        market_dataset_id=session.market_dataset_id,
        market_dataset_name=market_name,
    )


def _build_response(
    session: SessionState,
    *,
    msg_id: int,
    answer: str,
    intent: ChatIntent,
    classification: AnswerClassification,
    confidence: ConfidenceLevel,
    bundle: Optional[EvidenceBundle],
    context: ChatContextInfo,
    suggestions,
    used_context: bool = False,
    warnings=(),
) -> ChatResponse:
    return ChatResponse(
        session_id=session.session_id,
        message_id=str(msg_id),
        answer=answer,
        intent=intent,
        classification=classification,
        confidence=confidence,
        evidence=list(bundle.evidence) if bundle else [],
        calculations=list(bundle.calculations) if bundle else [],
        context=context,
        suggested_followups=list(suggestions),
        warnings=list(warnings) if warnings else [],
        used_context=used_context,
    )


def _generic_starters(mode: Optional[str]) -> List[str]:
    if mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS.value:
        return [
            "What would combined revenue look like?",
            "What are the biggest merger risks?",
            "What synergies could exist?",
        ]
    if mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK.value:
        return [
            "Where are we behind the competitor?",
            "What is our biggest benchmark gap?",
            "What should we improve first?",
        ]
    return [
        "How financially healthy are we?",
        "What is our revenue trend?",
        "What are our biggest risks?",
    ]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_service: Optional[ChatbotService] = None


def get_chatbot_service() -> ChatbotService:
    global _service
    if _service is None:
        _service = ChatbotService()
    return _service


def reset_chatbot_service_for_tests() -> None:
    global _service
    _service = None
