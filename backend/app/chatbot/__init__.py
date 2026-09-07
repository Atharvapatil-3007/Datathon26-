"""Dataset Intelligence Chatbot.

A finance-first, evidence-grounded chatbot that answers questions about the
user's uploaded dataset, its Phase 2 profile, and its Phase 3 financial
analysis (self / merger / competitor+market benchmark). It never invents
values — every numeric answer traces back to verified analytical evidence
produced by the existing Phase 1/2/3 stack.

Pipeline (see :mod:`app.chatbot.service`):

    User question
      -> guardrail        (finance-domain + safety filter)
      -> classifier       (intent + slot extraction)
      -> semantic_resolver (metric / period / entity resolution)
      -> context_builder  (Phase 2 profile + Phase 3 results, cached)
      -> query_engine     (evidence retrieval / calculation)
      -> answer_generator (deterministic natural-language templating)
      -> optional LLM paraphrase (verified against evidence)
      -> session update
      -> ChatResponse
"""

from app.chatbot.exceptions import (
    ChatbotError,
    OutOfScopeError,
    UnsupportedQueryError,
)
from app.chatbot.types import (
    AnalysisMode,
    AnswerClassification,
    ChatEvidence,
    ChatIntent,
    ChatMessage,
    ChatResponse,
    ChatRole,
    ClassifiedQuery,
    ConfidenceLevel,
    EntityRef,
    EvidenceBundle,
    PeriodRef,
    QuerySlots,
)

__all__ = [
    "AnalysisMode",
    "AnswerClassification",
    "ChatEvidence",
    "ChatIntent",
    "ChatMessage",
    "ChatResponse",
    "ChatRole",
    "ChatbotError",
    "ClassifiedQuery",
    "ConfidenceLevel",
    "EntityRef",
    "EvidenceBundle",
    "OutOfScopeError",
    "PeriodRef",
    "QuerySlots",
    "UnsupportedQueryError",
]
