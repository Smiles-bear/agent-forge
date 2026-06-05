from pydantic import BaseModel
from datetime import datetime


class SkillResult(BaseModel):
    id: int
    name: str
    description: str
    author: str | None = "unknown"
    version: str | None = "1.0.0"
    similarity: float | None = None
    created_at: datetime | None = None


class SkillDetail(BaseModel):
    id: int
    project: str
    name: str
    description: str
    author: str | None
    version: str | None
    skill_content: str
    created_at: datetime | None


class SkillUploadResponse(BaseModel):
    status: str
    skill_id: int | None = None
    name: str
    similarity: float | None = None
    closest_name: str | None = None
    message: str


class SkillSearchResponse(BaseModel):
    query: str
    project: str
    results: list[SkillResult]


class SkillListResponse(BaseModel):
    project: str
    total: int
    skills: list[SkillResult]


class DeleteResponse(BaseModel):
    status: str
    skill_id: int


class HealthResponse(BaseModel):
    status: str
    skill_count: int
    embedding_model: str
