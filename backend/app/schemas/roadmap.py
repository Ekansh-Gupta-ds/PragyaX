"""
Roadmap Schemas
Owned by: Arsh (FastAPI Backend Architecture)
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

RoadmapStatus = Literal["locked", "unlocked", "in_progress", "completed"]


class RoadmapModuleResponse(BaseModel):
    id: str = Field(..., description="Unique module identifier (e.g. 'mod_py_foundations')")
    title: str = Field(..., description="Human-readable module title")
    description: str = Field(..., description="Educational module scope and overview")
    subject_id: str = Field(..., description="Associated subject identifier")
    difficulty: str = Field("Beginner", description="'Beginner', 'Intermediate', or 'Advanced'")
    estimated_minutes: int = Field(30, description="Estimated completion time in minutes")
    prerequisite_module_ids: List[str] = Field(default_factory=list, description="List of required module IDs")
    status: RoadmapStatus = Field("locked", description="'locked', 'unlocked', 'in_progress', or 'completed'")
    completion_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Module progress percentage (0.0 to 100.0)")


class RoadmapDetailResponse(BaseModel):
    id: str = Field(..., description="Unique roadmap identifier (e.g. 'rdm_py_usr_...')")
    user_id: str = Field(..., description="Owner user ID")
    subject_id: str = Field(..., description="Target subject ID")
    title: str = Field(..., description="Personalized roadmap title")
    description: str = Field(..., description="Roadmap objective based on assessment diagnostic")
    modules: List[RoadmapModuleResponse] = Field(..., description="Ordered sequence of learning modules")
    overall_progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Overall average completion percentage")


class RoadmapProgressResponse(BaseModel):
    module_id: str = Field(..., description="Module identifier")
    status: RoadmapStatus = Field(..., description="'locked', 'unlocked', 'in_progress', or 'completed'")
    completion_percentage: float = Field(..., ge=0.0, le=100.0, description="Completion percentage")
    updated_at: Optional[str] = Field(None, description="ISO timestamp of last update")


class UpdateProgressRequest(BaseModel):
    status: Optional[RoadmapStatus] = Field(None, description="'in_progress' or 'completed'")
    completion_percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="New percentage (0.0 - 100.0)")
