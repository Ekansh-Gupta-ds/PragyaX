"""
Assessment and AI Evaluation Router
Owned by: Ekansh (AI/ML) & Arsh (Backend)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import sys
import os

# Pluggable AI import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from ai.factory import get_ai_provider

from ..schemas.assessments import (
    AssessmentQuestionPublic,
    AssessmentSubmitRequest,
    AssessmentResultResponse,
    AssessmentHistoryResponse,
    AssessmentHistoryItem
)
from ..services.assessment_service import evaluate_assessment
from ..services.auth_service import get_current_user
from ..database.repository import Repository

router = APIRouter(prefix="/assessments", tags=["Assessments"])


@router.get("/questions", response_model=List[AssessmentQuestionPublic])
def get_assessment_questions(subject_id: str = "subj_python", user: dict = Depends(get_current_user)):
    """
    Retrieves the 5 assessment questions.
    SECURITY: Correct answers and explanations are NEVER exposed prior to submission.
    """
    raw_questions = Repository.get_assessment_questions(subject_id)
    if not raw_questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No questions found for the selected subject."
        )

    # Convert to public schema
    return [
        AssessmentQuestionPublic(
            id=q["id"],
            subject_id=q["subject_id"],
            question_number=q["question_number"],
            question_text=q["question_text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            topic=q["topic"],
            difficulty=q["difficulty"]
        )
        for q in raw_questions
    ]


@router.post("/submit", response_model=AssessmentResultResponse)
def submit_assessment(payload: AssessmentSubmitRequest, user: dict = Depends(get_current_user)):
    """
    Evaluates assessment submission against backend reference keys and persists results.
    Rejects incomplete or invalid submissions.
    """
    # 1. Fetch internal questions with answer keys
    ref_questions = Repository.get_raw_assessment_questions_with_answers(payload.subject_id)
    if not ref_questions or len(ref_questions) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment must contain exactly 5 valid questions."
        )

    # 2. Validate that answers are provided for each question (and nothing else)
    valid_options = {"A", "B", "C", "D"}
    unknown = set(payload.answers) - {q["id"] for q in ref_questions}
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown question id(s): {', '.join(sorted(unknown))}."
        )
    for q in ref_questions:
        q_id = q["id"]
        if q_id not in payload.answers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing answer for question #{q['question_number']}."
            )
        ans = str(payload.answers[q_id]).strip().upper()
        if ans not in valid_options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid option '{ans}' for question #{q['question_number']}. Must be A, B, C, or D."
            )

    answers = {q_id: str(opt).strip().upper() for q_id, opt in payload.answers.items()}
    subject = Repository.get_subject_by_id(ref_questions[0]["subject_id"])

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment subject is unavailable."
        )

    # 3. Server-owned grading with AI-provided qualitative feedback
    try:
        eval_result = evaluate_assessment(
            get_ai_provider(),
            subject["title"],
            ref_questions,
            answers
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Assessment provider is temporarily unavailable."
        ) from None

    # 4. Persist result in database
    attempt = Repository.save_assessment_attempt(
        user_id=user["id"],
        subject_id=ref_questions[0]["subject_id"],
        score=eval_result["score"],
        total=eval_result["total"],
        percentage=eval_result["percentage"],
        proficiency_level=eval_result["proficiency_level"],
        summary_feedback=eval_result["summary_feedback"],
        recommended_topics=eval_result["recommended_topics"],
        user_answers=answers,
        breakdown=eval_result["breakdown"]
    )

    return {
        "id": attempt["id"],
        "user_id": user["id"],
        "subject_id": attempt["subject_id"],
        "subject_title": attempt.get("subject_title", "Python Programming"),
        "score": attempt["score"],
        "total": attempt["total"],
        "percentage": attempt["percentage"],
        "proficiency_level": attempt["proficiency_level"],
        "summary_feedback": attempt["summary_feedback"],
        "recommended_topics": attempt["recommended_topics"],
        "breakdown": attempt["breakdown"],
        "is_mock": eval_result.get("is_mock", True),
        "provider": eval_result.get("provider", "PragyaX AI"),
        "created_at": attempt.get("created_at")
    }


@router.get("/history", response_model=AssessmentHistoryResponse)
def get_assessment_history(user: dict = Depends(get_current_user)):
    """Returns list of past completed assessment attempts for the authenticated user."""
    attempts = Repository.get_user_assessment_attempts(user["id"], limit=20)
    return {
        "attempts": [
            AssessmentHistoryItem(
                id=a["id"],
                subject_id=a["subject_id"],
                subject_title=a["subject_title"],
                score=a["score"],
                total=a["total"],
                percentage=a["percentage"],
                proficiency_level=a["proficiency_level"],
                created_at=a.get("created_at")
            )
            for a in attempts
        ]
    }


@router.get("/{attempt_id}", response_model=AssessmentResultResponse)
def get_assessment_attempt_details(attempt_id: str, user: dict = Depends(get_current_user)):
    """
    Retrieves full breakdown of a past assessment.
    Enforces user isolation: Attempt must belong to authenticated user.
    """
    attempt = Repository.get_assessment_attempt_by_id(attempt_id, user["id"])
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found or unauthorized."
        )

    try:
        ai_provider = get_ai_provider()
        provider_name = ai_provider.provider_name
        is_mock = ai_provider.is_mock
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider metadata is temporarily unavailable."
        ) from None

    return {
        "id": attempt["id"],
        "user_id": user["id"],
        "subject_id": attempt["subject_id"],
        "subject_title": attempt.get("subject_title", "Python Programming"),
        "score": attempt["score"],
        "total": attempt["total"],
        "percentage": attempt["percentage"],
        "proficiency_level": attempt["proficiency_level"],
        "summary_feedback": attempt["summary_feedback"],
        "recommended_topics": attempt["recommended_topics"],
        "breakdown": attempt["breakdown"],
        "is_mock": is_mock,
        "provider": provider_name,
        "created_at": attempt.get("created_at")
    }
