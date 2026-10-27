"""
Personalized Learning Roadmap Router
Exposes endpoints for retrieving diagnostic roadmaps, viewing module details,
and signaling module completion (pending database schema provisioning).
Owned by: Arsh (FastAPI Backend Architecture)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.roadmap import (
    RoadmapDetailResponse,
    RoadmapModuleResponse,
    RoadmapProgressResponse,
    UpdateProgressRequest
)
from ..services.auth_service import get_current_user
from ..services.roadmap_service import (
    build_deterministic_roadmap,
    SUPPORTED_SUBJECTS,
    SUBJECT_CATALOGS,
    SubjectCatalogComingSoonError
)
from ..database.repository import Repository

router = APIRouter(prefix="/roadmap", tags=["Learning Roadmaps"])


@router.get("", response_model=RoadmapDetailResponse)
def get_user_roadmap(
    subject_id: Optional[str] = Query(None, description="Optional target subject ID"),
    user: dict = Depends(get_current_user)
):
    """
    Retrieves the learner's personalized learning roadmap.
    Constructed deterministically using the student's active subject and
    weakness topics identified during recent assessment evaluations.
    """
    user_id = user["id"]

    # 1. Determine active subject
    if subject_id:
        if subject_id not in SUPPORTED_SUBJECTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject '{subject_id}' is not supported. Supported: {', '.join(sorted(SUPPORTED_SUBJECTS.keys()))}."
            )
        if subject_id not in SUBJECT_CATALOGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Roadmaps for this subject are coming soon."
            )
        target_subject_id = subject_id
    else:
        selected_subject = Repository.get_user_selected_subject(user_id)
        target_subject_id = selected_subject.get("id", "subj_python")
        if target_subject_id not in SUBJECT_CATALOGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Roadmaps for this subject are coming soon."
            )

    # 2. Extract diagnostic weaknesses from user's latest assessment attempt
    attempts = Repository.get_user_assessment_attempts(user_id, limit=1)
    weaknesses = attempts[0].get("recommended_topics", []) if attempts else []

    # 3. Generate deterministic roadmap
    try:
        roadmap_data = build_deterministic_roadmap(
            subject_id=target_subject_id,
            weaknesses=weaknesses,
            user_id=user_id
        )
    except SubjectCatalogComingSoonError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return roadmap_data


@router.get("/{module_id}", response_model=RoadmapModuleResponse)
def get_roadmap_module(
    module_id: str,
    subject_id: Optional[str] = Query(None, description="Optional subject ID context"),
    user: dict = Depends(get_current_user)
):
    """
    Retrieves detailed specifications for a specific roadmap module,
    including prerequisite dependencies and completion requirements.
    """
    user_id = user["id"]

    if subject_id:
        if subject_id not in SUPPORTED_SUBJECTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject '{subject_id}' is not supported."
            )
        if subject_id not in SUBJECT_CATALOGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Roadmaps for this subject are coming soon."
            )
        target_subject_id = subject_id
    else:
        target_subject_id = Repository.get_user_selected_subject(user_id).get("id", "subj_python")
        if target_subject_id not in SUBJECT_CATALOGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Roadmaps for this subject are coming soon."
            )

    attempts = Repository.get_user_assessment_attempts(user_id, limit=1)
    weaknesses = attempts[0].get("recommended_topics", []) if attempts else []

    try:
        roadmap_data = build_deterministic_roadmap(
            subject_id=target_subject_id,
            weaknesses=weaknesses,
            user_id=user_id
        )
    except SubjectCatalogComingSoonError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    module = next((m for m in roadmap_data["modules"] if m["id"] == module_id), None)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_id}' not found in active roadmap."
        )

    return module


@router.post("/{module_id}/complete", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def complete_roadmap_module(
    module_id: str,
    payload: Optional[UpdateProgressRequest] = None,
    user: dict = Depends(get_current_user)
):
    """
    Signals completion of a learning roadmap module.
    
    IMPORTANT:
    Persistent database tables for user roadmap progress ('learning_roadmaps', 'user_roadmap_progress')
    have not yet been provisioned in the database schema by Nagin.
    In accordance with architectural safety rules, this endpoint strictly returns HTTP 501
    rather than faking successful persistence.
    """
    # Enforces authentication and parameter validation
    if not module_id or len(module_id.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid module_id is required."
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Roadmap progress persistence is not yet implemented. Waiting for database schema provisioning."
    )
