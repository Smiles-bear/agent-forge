import json
import logging
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from store.db import SessionLocal, Agent
from models.schemas import (
    AgentRegisterRequest, AgentRegisterResponse,
    AgentMatchRequest, AgentMatchResponse, AgentMatchResult,
    AgentExecuteRequest, AgentExecuteResponse,
    AgentListResponse, AgentDeleteResponse,
    AgentResult, AgentDetail,
    VerifyRequest, VerifyResponse, VerificationStatusResponse,
    OrchestrateRequest, OrchestrateResponse,
)
from services.agent_service import (
    register_agent, match_agent, execute_agent,
    list_agents, get_agent, delete_agent, list_departments,
    orchestrate_task,
)
from services.verification import (
    get_verification_status, clear_verification_results, run_verification,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agent-registry"])


@router.post("/{project}/agents/register", response_model=AgentRegisterResponse,
             status_code=201)
async def register(project: str, data: AgentRegisterRequest,
                   background_tasks: BackgroundTasks):
    agent_data = data.model_dump()

    session = SessionLocal()
    try:
        result = register_agent(project, agent_data, session)
        if result["status"] == "rejected":
            return AgentRegisterResponse(**result)

        # 异步触发验证
        agent_id = result["agent_id"]
        vconfig = agent_data.get("verification")
        if vconfig and agent_id:
            from services.verification import run_verification
            endpoint = agent_data["endpoint"]
            background_tasks.add_task(run_verification, agent_id, vconfig, endpoint)
            logger.info("Verification scheduled for agent %d", agent_id)

        return AgentRegisterResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@router.post("/{project}/agents/match", response_model=AgentMatchResponse)
async def match(project: str, data: AgentMatchRequest):
    session = SessionLocal()
    try:
        matches = match_agent(data.task, project, data.top_k, session)

        # 零匹配或低质量匹配时给用户提示
        hint = None
        agent_count = session.query(Agent).filter(Agent.project == project).count()
        if not matches:
            if agent_count == 0:
                hint = f"No agents registered in project '{project}'. Register an agent first."
            else:
                hint = f"No agents matched your task. Try rephrasing — be more specific about tech stack (e.g. 'python', 'react') and task type (e.g. 'review', 'develop'). {agent_count} agents available in this project."
        elif all(m.get("relevance_score", 0) < 0.5 for m in matches):
            hint = f"All matches have low confidence (<0.5). Your task may be outside the capabilities of available agents. Try breaking it into smaller steps or registering a specialized agent."

        return AgentMatchResponse(
            task=data.task,
            project=project,
            matches=[
                AgentMatchResult(
                    agent=AgentResult(
                        id=m["agent_id"],
                        name=m["name"],
                        tech_stack=m.get("tech_stack", []),
                        task_types=m.get("task_types", []),
                        domains=m.get("domains", []),
                        difficulty=m.get("difficulty"),
                        department=m["department"],
                        protocol=m.get("protocol", "http"),
                        capability_tags=m.get("capability_tags", []),
                        reliability_score=m.get("reliability_score"),
                        similarity=m.get("relevance_score"),
                        created_at=m.get("created_at"),
                    ),
                    tech_sim=m.get("tech_sim"),
                    task_sim=m.get("task_sim"),
                    domain_sim=m.get("domain_sim"),
                    diff_sim=m.get("diff_sim"),
                    match_reason=m.get("match_reason", ""),
                )
                for m in matches
            ],
            hint=hint,
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


@router.post("/{project}/agents/{agent_id}/verify", response_model=VerifyResponse)
async def verify_agent(project: str, agent_id: int,
                       data: VerifyRequest | None = None,
                       background_tasks: BackgroundTasks = None):
    """Async re-verification of an agent."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Use provided test_cases or existing verification_config
        vconfig = data.test_cases if data and data.test_cases else None
        if not vconfig and agent.verification_config:
            try:
                vconfig = json.loads(agent.verification_config) if isinstance(agent.verification_config, str) else agent.verification_config
            except Exception:
                pass
        if not vconfig or not vconfig.get("test_cases"):
            raise HTTPException(status_code=400, detail="No test cases available for verification")

        # Clear old results
        clear_verification_results(agent_id)

        # Trigger async verification
        background_tasks.add_task(run_verification, agent_id, vconfig, agent.endpoint)
        logger.info("Re-verification scheduled for agent %d", agent_id)

        return VerifyResponse(status="scheduled", agent_id=agent_id,
                              message="Verification started")
    finally:
        session.close()


@router.get("/{project}/agents/{agent_id}/verification",
            response_model=VerificationStatusResponse)
async def get_verification(project: str, agent_id: int):
    """Query agent verification progress and results."""
    status = get_verification_status(agent_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return VerificationStatusResponse(**status)


@router.post("/{project}/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(project: str, data: OrchestrateRequest):
    """CEO orchestration: decompose complex task → match → execute → merge."""
    logger.info("Orchestrate request: %s", data.task[:80])
    result = orchestrate_task(project, data.task)
    return OrchestrateResponse(**result)
