"""HTTP API for the Dataset Intelligence Chatbot.

Routes:

    POST   /api/v1/chat/query
    GET    /api/v1/chat/sessions/{session_id}
    DELETE /api/v1/chat/sessions/{session_id}
    POST   /api/v1/chat/suggestions

Every payload is JSON. Errors follow the existing platform contract
(``{"success": false, "error": {"code": ..., "message": ...}}``) thanks
to the global exception handler in ``app/main.py`` — chatbot exceptions
inherit from ``IngestionError``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.chatbot.service import get_chatbot_service
from app.chatbot.types import ChatMessage
from app.utils.logging import get_logger


log = get_logger(__name__)

router_chat = APIRouter(prefix="/chat", tags=["chat"])


# ============================================================================
# Request / response schemas
# ============================================================================
class ChatQueryRequest(BaseModel):
    message: str = Field(..., description="User's question", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, description="Chat session identifier")
    dataset_id: Optional[str] = Field(default=None, description="Primary dataset id")
    analysis_mode: Optional[str] = Field(
        default=None,
        description="One of self_analysis / merger_partnership_analysis / competitor_market_benchmark",
    )
    secondary_dataset_id: Optional[str] = Field(default=None)
    market_dataset_id: Optional[str] = Field(default=None)
    primary_display_name: Optional[str] = Field(default=None, max_length=200)
    secondary_display_name: Optional[str] = Field(default=None, max_length=200)
    market_display_name: Optional[str] = Field(default=None, max_length=200)


class ChatSessionResponse(BaseModel):
    session_id: str
    dataset_id: Optional[str]
    analysis_mode: Optional[str]
    secondary_dataset_id: Optional[str] = None
    market_dataset_id: Optional[str] = None
    messages: List[Dict[str, Any]]


class SuggestionsRequest(BaseModel):
    dataset_id: str = Field(..., description="Primary dataset id")
    analysis_mode: Optional[str] = Field(default=None)
    secondary_dataset_id: Optional[str] = Field(default=None)
    market_dataset_id: Optional[str] = Field(default=None)
    last_intent: Optional[str] = Field(default=None)
    limit: int = Field(default=6, ge=1, le=12)


class SuggestionsResponse(BaseModel):
    suggestions: List[str]


# ============================================================================
# Routes
# ============================================================================
@router_chat.post(
    "/query",
    status_code=status.HTTP_200_OK,
    summary="Send a message to the dataset intelligence chatbot",
)
async def chat_query(payload: ChatQueryRequest) -> Dict[str, Any]:
    log.info(
        "chat_query_requested",
        session_id=payload.session_id,
        dataset_id=payload.dataset_id,
        analysis_mode=payload.analysis_mode,
        message_length=len(payload.message),
    )
    service = get_chatbot_service()
    response = await run_in_threadpool(
        service.handle_query,
        message=payload.message,
        session_id=payload.session_id,
        dataset_id=payload.dataset_id,
        analysis_mode=payload.analysis_mode,
        secondary_dataset_id=payload.secondary_dataset_id,
        market_dataset_id=payload.market_dataset_id,
        primary_display_name=payload.primary_display_name,
        secondary_display_name=payload.secondary_display_name,
        market_display_name=payload.market_display_name,
    )
    return response.to_dict()


@router_chat.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Fetch conversation history for a chat session",
)
async def chat_get_session(session_id: str) -> ChatSessionResponse:
    service = get_chatbot_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Chat session '{session_id}' not found")
    return ChatSessionResponse(
        session_id=session.session_id,
        dataset_id=session.dataset_id,
        analysis_mode=session.analysis_mode,
        secondary_dataset_id=session.secondary_dataset_id,
        market_dataset_id=session.market_dataset_id,
        messages=[m.to_dict() for m in session.history],
    )


@router_chat.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear a chat session",
)
async def chat_delete_session(session_id: str):
    service = get_chatbot_service()
    service.delete_session(session_id)
    return None


@router_chat.post(
    "/suggestions",
    response_model=SuggestionsResponse,
    summary="Get context-aware suggested chatbot questions",
)
async def chat_suggestions(payload: SuggestionsRequest) -> SuggestionsResponse:
    service = get_chatbot_service()
    items = await run_in_threadpool(
        service.suggestions_for,
        dataset_id=payload.dataset_id,
        analysis_mode=payload.analysis_mode,
        secondary_dataset_id=payload.secondary_dataset_id,
        market_dataset_id=payload.market_dataset_id,
        last_intent=payload.last_intent,
        limit=payload.limit,
    )
    return SuggestionsResponse(suggestions=list(items))
