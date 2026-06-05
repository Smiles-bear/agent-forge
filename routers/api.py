import logging
from fastapi import APIRouter, Request, HTTPException
from store.db import SessionLocal, Skill
from models.schemas import (
    SkillUploadResponse, SkillSearchResponse, SkillListResponse,
    SkillDetail, DeleteResponse, HealthResponse, SkillResult,
)
from services.parser import parse_skill_md
from services.skill_service import (
    upload_skill, search_skills, list_skills, get_skill, delete_skill,
)
from config import EMBEDDING_MODEL, SEARCH_DEFAULT_TOP_K

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["skill-registry"])


@router.post("/{project}/skills/upload", response_model=SkillUploadResponse,
             status_code=201)
async def upload(project: str, request: Request):
    body = (await request.body()).decode("utf-8")
    if not body.strip():
        raise HTTPException(status_code=400, detail="Request body is empty")

    try:
        parsed = parse_skill_md(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = SessionLocal()
    try:
        result = upload_skill(project, parsed, session)
        if result["status"] == "rejected":
            return SkillUploadResponse(**result)  # return 200 for rejected, not 201
        return SkillUploadResponse(**result)
    finally:
        session.close()


@router.get("/{project}/skills/search", response_model=SkillSearchResponse)
async def search(project: str, q: str = "", top_k: int = SEARCH_DEFAULT_TOP_K):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    session = SessionLocal()
    try:
        results = search_skills(q, project, top_k, session)
        return SkillSearchResponse(query=q, project=project, results=[
            SkillResult(**r) for r in results
        ])
    finally:
        session.close()


@router.get("/{project}/skills", response_model=SkillListResponse)
async def list_skills_endpoint(project: str):
    session = SessionLocal()
    try:
        skills = list_skills(project, session)
        return SkillListResponse(project=project, total=len(skills), skills=[
            SkillResult(**s) for s in skills
        ])
    finally:
        session.close()


@router.get("/{project}/skills/{skill_id}", response_model=SkillDetail)
async def get_skill_endpoint(project: str, skill_id: int):
    session = SessionLocal()
    try:
        skill = get_skill(skill_id, session)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return SkillDetail(**skill)
    finally:
        session.close()


@router.delete("/{project}/skills/{skill_id}", response_model=DeleteResponse)
async def delete_skill_endpoint(project: str, skill_id: int):
    session = SessionLocal()
    try:
        ok = delete_skill(skill_id, session)
        if not ok:
            raise HTTPException(status_code=404, detail="Skill not found")
        return DeleteResponse(status="deleted", skill_id=skill_id)
    finally:
        session.close()


@router.get("/{project}/health", response_model=HealthResponse)
async def project_health(project: str):
    session = SessionLocal()
    try:
        count = session.query(Skill).filter(Skill.project == project).count()
        return HealthResponse(status="ok", skill_count=count,
                              embedding_model=EMBEDDING_MODEL)
    finally:
        session.close()


@router.get("/health", response_model=HealthResponse)
async def global_health():
    session = SessionLocal()
    try:
        count = session.query(Skill).count()
        return HealthResponse(status="ok", skill_count=count,
                              embedding_model=EMBEDDING_MODEL)
    finally:
        session.close()
