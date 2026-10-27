"""
Learning Chat Schemas
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Literal
from .timestamps import TimestampString


class ChatInputRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Question or concept query")
    subject: Optional[str] = Field("Python Programming", description="Active learning subject; null uses Python Programming")

    @field_validator("subject", mode="before")
    @classmethod
    def default_null_subject(cls, value):
        return "Python Programming" if value is None else value


class ChatMessageResponse(BaseModel):
    id: str
    user_id: str
    subject: str
    role: Literal["user", "assistant"]
    content: str
    suggested_followups: List[str] = Field(default_factory=list)
    is_mock: bool = True
    provider: str = "PragyaX Mock AI"
    created_at: Optional[TimestampString] = None


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessageResponse]
    active_provider: str
    is_mock: bool


class ChatProviderResult(BaseModel):
    model_config = ConfigDict(strict=True)
    reply: str = Field(min_length=1)
    suggested_followups: List[str] = Field(default_factory=list)
    is_mock: bool = True
    provider: str = "PragyaX AI"
