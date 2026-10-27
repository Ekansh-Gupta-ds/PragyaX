"""
PragyaX Pydantic Schemas
Owned by: Arsh (FastAPI Backend Architecture)
"""

from .auth import RegisterRequest, LoginRequest, AuthResponse, UserProfileResponse
from .subjects import SubjectItemResponse, SubjectListResponse, SelectSubjectRequest
from .chat import ChatInputRequest, ChatMessageResponse, ChatHistoryResponse
from .assessments import AssessmentQuestionPublic, AssessmentSubmitRequest, AssessmentResultResponse, AssessmentHistoryResponse
from .dashboard import DashboardResponse
from .challenges import DailyChallengeResponse, ChallengeSubmitRequest, ChallengeResultResponse
from .roadmap import (
    RoadmapStatus,
    RoadmapModuleResponse,
    RoadmapDetailResponse,
    RoadmapProgressResponse,
    UpdateProgressRequest
)

__all__ = [
    "RegisterRequest", "LoginRequest", "AuthResponse", "UserProfileResponse",
    "SubjectItemResponse", "SubjectListResponse", "SelectSubjectRequest",
    "ChatInputRequest", "ChatMessageResponse", "ChatHistoryResponse",
    "AssessmentQuestionPublic", "AssessmentSubmitRequest", "AssessmentResultResponse", "AssessmentHistoryResponse",
    "DashboardResponse",
    "DailyChallengeResponse", "ChallengeSubmitRequest", "ChallengeResultResponse",
    "RoadmapStatus", "RoadmapModuleResponse", "RoadmapDetailResponse", "RoadmapProgressResponse", "UpdateProgressRequest"
]
