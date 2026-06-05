import json
import logging
from fastapi import APIRouter, HTTPException, Request
from store.db import SessionLocal
from models.schemas import (
    AgentRegisterRequest, AgentRegisterResponse,
    AgentMatchRequest, AgentMatchResponse, AgentMatchResult,
    AgentExecuteRequest, AgentExecuteResponse,
    AgentListResponse, AgentDeleteResponse,
    AgentResult, AgentDetail,
)
from services.agent_service import (
    register_agent, match_agent, execute_agent,
    list_agents, get_agent, delete_agent, list_departments,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agent-registry"])


@router.post("/{project}/agents/register", response_model=AgentRegisterResponse,
             status_code=201)
async def register(project: str, data: AgentRegisterRequest):
    session = SessionLocal()
    try:
        result = register_agent(project, data.model_dump(), session)
        if result["status"] == "rejected":
            return AgentRegisterResponse(**result)
        return AgentRegisterResponse(**result)
    finally:
        session.close()


@router.post("/{project}/agents/match", response_model=AgentMatchResponse)
async def match(project: str, data: AgentMatchRequest):
    session = SessionLocal()
    try:
        matches = match_agent(data.task, project, data.top_k, session)
        return AgentMatchResponse(
            task=data.task,
            project=project,
            matches=[
                AgentMatchResult(
                    agent=AgentResult(
                        id=m["agent_id"],
                        name=m["name"],
                        description=m["description"],
                        department=m["department"],
                        protocol=m.get("protocol", "http"),
                        capability_tags=m.get("capability_tags", []),
                        reliability_score=m.get("reliability_score"),
                        similarity=m.get("relevance_score", m.get("vector_similarity")),
                        created_at=m.get("created_at"),
                    ),
                    match_reason=m.get("match_reason", ""),
                )
                for m in matches
            ],
        )
    finally:
        session.close()


@router.post("/{project}/agents/{agent_id}/execute", response_model=AgentExecuteResponse)
async def execute(project: str, agent_id: int, data: AgentExecuteRequest):
    session = SessionLocal()
    try:
        result = execute_agent(agent_id, data.task, data.context, session)
        if result is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentExecuteResponse(**result)
    finally:
        session.close()


@router.get("/{project}/agents", response_model=AgentListResponse)
async def list_endpoint(project: str, department: str | None = None):
    session = SessionLocal()
    try:
        agents = list_agents(project, department, session)
        return AgentListResponse(
            project=project,
            total=len(agents),
            agents=[AgentResult(**a) for a in agents],
        )
    finally:
        session.close()


@router.get("/{project}/agents/{agent_id}", response_model=AgentDetail)
async def get_endpoint(project: str, agent_id: int):
    session = SessionLocal()
    try:
        agent = get_agent(agent_id, session)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentDetail(**agent)
    finally:
        session.close()


@router.delete("/{project}/agents/{agent_id}", response_model=AgentDeleteResponse)
async def delete_endpoint(project: str, agent_id: int):
    session = SessionLocal()
    try:
        ok = delete_agent(agent_id, session)
        if not ok:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentDeleteResponse(status="deleted", agent_id=agent_id)
    finally:
        session.close()


@router.get("/{project}/departments")
async def departments_endpoint(project: str):
    session = SessionLocal()
    try:
        deps = list_departments(project, session)
        return {"project": project, "departments": deps}
    finally:
        session.close()
