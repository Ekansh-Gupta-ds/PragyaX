"""
Learning Chat Router
Powered by Pluggable AI Service Layer
Owned by: Ekansh (AI/ML) & Arsh (Backend)
"""

from fastapi import APIRouter, Depends, HTTPException, status
import sys
import os

# Ensure ai directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from ai.factory import get_ai_provider

from ..schemas.chat import (
    ChatInputRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatProviderResult
)
from ..services.auth_service import get_current_user
from ..database.repository import Repository

router = APIRouter(prefix="/chat", tags=["Learning Chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_chat_message(payload: ChatInputRequest, user: dict = Depends(get_current_user)):
    """Processes educational chat message through the active AI provider."""
    user_msg_content = payload.message.strip()
    if not user_msg_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    # 1. Read prior history before saving current prompt (avoids duplicate prompt in context)
    history = Repository.get_chat_history(user["id"], limit=10)
    history_tuples = [{"role": h["role"], "content": h["content"]} for h in history]

    # 2. Query and validate pluggable AI Provider
    try:
        ai_provider = get_ai_provider()
        ai_result = ChatProviderResult.model_validate(ai_provider.generate_chat_response(
            prompt=user_msg_content,
            subject=payload.subject,
            history=history_tuples
        )).model_dump()
    except Exception:
        # Provider errors may contain credentials; never return or log their text.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Learning provider is temporarily unavailable."
        ) from None

    # 3. Save user query to persistent history (only after generation succeeds)
    Repository.save_chat_message(
        user_id=user["id"],
        subject=payload.subject,
        role="user",
        content=user_msg_content
    )

    # 4. Save AI reply to persistent history
    ai_msg = Repository.save_chat_message(
        user_id=user["id"],
        subject=payload.subject,
        role="assistant",
        content=ai_result["reply"],
        suggested_followups=ai_result.get("suggested_followups", [])
    )

    return {
        "id": ai_msg["id"],
        "user_id": user["id"],
        "subject": payload.subject,
        "role": "assistant",
        "content": ai_result["reply"],
        "suggested_followups": ai_result.get("suggested_followups", []),
        "is_mock": ai_result.get("is_mock", True),
        "provider": ai_result.get("provider", "PragyaX AI"),
        "created_at": None
    }


@router.get("/history", response_model=ChatHistoryResponse)
def get_chat_history(user: dict = Depends(get_current_user)):
    """Retrieves persistent learning chat history for the authenticated learner."""
    history = Repository.get_chat_history(user["id"], limit=50)
    try:
        ai_provider = get_ai_provider()
        provider_name = ai_provider.provider_name
        is_mock = ai_provider.is_mock
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider metadata is temporarily unavailable."
        ) from None
    
    formatted = []
    for h in history:
        formatted.append({
            "id": h["id"],
            "user_id": h["user_id"],
            "subject": h["subject"],
            "role": h["role"],
            "content": h["content"],
            "suggested_followups": h.get("suggested_followups", []),
            "is_mock": is_mock,
            "provider": provider_name,
            "created_at": h.get("created_at")
        })

    return {
        "messages": formatted,
        "active_provider": provider_name,
        "is_mock": is_mock
    }
