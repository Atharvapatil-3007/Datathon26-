"""Pluggable LLM client (optional paraphrase layer).

Design:
  * The chatbot's answer is always constructed from verified evidence by
    ``answer_generator``. The LLM never touches the numbers.
  * When ``CHATBOT_LLM_ENABLED=true`` is set in the environment, this module
    can be extended to call an OpenAI-compatible endpoint that rewrites the
    answer into a smoother tone while preserving every numeric token.
  * Out of the box, no network dependency exists and the paraphrase is a
    no-op — we return the deterministic answer as-is.

If a future integrator plugs in a real LLM, the ``paraphrase()`` function
below is the only place that should change. It also verifies that no numeric
value present in the evidence disappears after paraphrase — if that check
fails, the deterministic answer is returned instead.
"""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional

from app.chatbot.types import ChatEvidence
from app.utils.logging import get_logger


log = get_logger(__name__)


_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def is_enabled() -> bool:
    """True if a real LLM should be called on top of templated answers."""
    return os.getenv("CHATBOT_LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")


def paraphrase(
    deterministic_answer: str,
    evidence: Iterable[ChatEvidence],
    *,
    intent_label: Optional[str] = None,
) -> str:
    """Optionally rewrite ``deterministic_answer`` while preserving numbers.

    In the default configuration (no LLM), returns the deterministic answer
    unchanged. If a provider is wired up later:

      1. Send the deterministic answer + evidence to the model with a strict
         system prompt that forbids changing numeric values.
      2. Verify every number from the source appears in the rewrite.
      3. If verification fails, fall back to the deterministic answer.
    """
    if not is_enabled():
        return deterministic_answer

    # ---- Placeholder integration -----------------------------------------
    # Real integrators plug their SDK in here. The block below is intentionally
    # left empty; if it ever gets replaced, the safety check underneath
    # guarantees the output still contains every numeric fact from the
    # deterministic answer. Anything else is treated as a failure and the
    # deterministic answer wins.
    try:
        rewritten: Optional[str] = None  # e.g. openai.ChatCompletion.create(...)
    except Exception as exc:  # noqa: BLE001
        log.warning("chatbot_llm_paraphrase_failed", error=str(exc))
        rewritten = None

    if not rewritten:
        return deterministic_answer

    if not _preserves_numbers(deterministic_answer, rewritten):
        log.warning("chatbot_llm_paraphrase_number_mismatch")
        return deterministic_answer

    return rewritten


def _preserves_numbers(source: str, rewrite: str) -> bool:
    source_numbers = set(_NUMBER_RE.findall(source))
    rewrite_numbers = set(_NUMBER_RE.findall(rewrite))
    return source_numbers.issubset(rewrite_numbers)
