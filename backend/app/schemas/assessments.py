"""
Assessment Schemas
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from .timestamps import TimestampString


class AssessmentQuestionPublic(BaseModel):
    id: str
    subject_id: str
    question_number: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    topic: str
    difficulty: str


class AssessmentSubmitRequest(BaseModel):
    subject_id: str = Field(..., description="Subject identifier (e.g. 'subj_python')")
    answers: Dict[str, str] = Field(..., description="Map of question_id -> selected option ('A', 'B', 'C', or 'D')")


class QuestionBreakdownItem(BaseModel):
    question_id: str
    question_text: str
    selected_option: str
    correct_option: str
    is_correct: bool
    explanation: str
    topic: str


class AssessmentResultResponse(BaseModel):
    id: str
    user_id: str
    subject_id: str
    subject_title: Optional[str] = "Python Programming"
    score: int
    total: int
    percentage: float
    proficiency_level: str
    summary_feedback: str
    recommended_topics: List[str]
    breakdown: List[QuestionBreakdownItem]
    is_mock: bool
    provider: str
    created_at: Optional[TimestampString] = None


class AssessmentHistoryItem(BaseModel):
    id: str
    subject_id: str
    subject_title: str
    score: int
    total: int
    percentage: float
    proficiency_level: str
    created_at: Optional[TimestampString] = None


class AssessmentHistoryResponse(BaseModel):
    attempts: List[AssessmentHistoryItem]
