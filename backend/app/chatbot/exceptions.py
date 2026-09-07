"""Chatbot exception hierarchy.

Every chatbot error inherits from Phase 1's ``IngestionError`` so the
existing FastAPI global exception handler serialises them into the
standard ``{"success": false, "error": {...}}`` envelope without any
extra plumbing.
"""

from __future__ import annotations

from app.ingestion.exceptions import IngestionError


class ChatbotError(IngestionError):
    """Base class for all chatbot-related errors."""

    code = "CHATBOT_ERROR"
    http_status = 422


class OutOfScopeError(ChatbotError):
    """The user asked something outside the dataset-intelligence domain.

    Note: for UX we usually don't raise this — we return a polite refusal
    response with ``AnswerClassification.UNAVAILABLE``. It's kept here so
    the HTTP layer can distinguish "guardrail refused" from other errors
    when future callers ask it to.
    """

    code = "OUT_OF_SCOPE"
    http_status = 200  # returned as a normal chatbot response, not a failure


class UnsupportedQueryError(ChatbotError):
    """In-scope question but the dataset cannot answer it.

    Also usually surfaced as an in-band UNAVAILABLE response; kept for
    programmatic callers that would rather see a raise.
    """

    code = "UNSUPPORTED_QUERY"
    http_status = 200


class ChatSessionNotFoundError(ChatbotError):
    code = "CHAT_SESSION_NOT_FOUND"
    http_status = 404
