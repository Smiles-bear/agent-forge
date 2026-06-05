import json
import logging
import time
from sqlalchemy import text
from store.db import SessionLocal, Agent
from store.vector_store import VectorStore
from config import DEDUP_HIGH_THRESHOLD, SEARCH_DEFAULT_TOP_K

logger = logging.getLogger(__name__)


def _serialize_tags(tags: list[str] | None) -> str | None:
    return json.dumps(tags, ensure_ascii=False) if tags else None


def _deserialize_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Register ────────────────────────────────────────────

def register_agent(project: str, data: dict, session) -> dict:
    vs = VectorStore()
    emb = vs.encode([data["description"]])[0]

    # 去重检查：同 project 内有没有能力高度相似的 Agent
    results = vs.cosine_search(emb, project, top_k=1, session=session, model="agents")
    closest, distance = results[0] if results else (None, None)
    sim = round(1.0 - (distance / 2.0), 4) if distance else None

    if closest and sim and sim > DEDUP_HIGH_THRESHOLD:
        return {
            "status": "rejected",
            "agent_id": None,
            "name": data["name"],
            "similarity": sim,
            "closest_agent": closest.name,
            "message": f"Agent too similar to '{closest.name}' ({sim:.1%}). Register rejected.",
        }

    agent = Agent(
        project=project,
        name=data["name"],
        description=data["description"],
        embedding=emb,
        endpoint=data["endpoint"],
        protocol=data.get("protocol", "http"),
        input_schema=json.dumps(data.get("input_schema"), ensure_ascii=False) if data.get("input_schema") else None,
        output_schema=json.dumps(data.get("output_schema"), ensure_ascii=False) if data.get("output_schema") else None,
        tools=_serialize_tags(data.get("tools")),
        department=data.get("department", "uncategorized"),
        capability_tags=_serialize_tags(data.get("capability_tags")),
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    return {
        "status": "created",
        "agent_id": agent.id,
        "name": agent.name,
        "similarity": sim,
        "closest_agent": closest.name if closest else None,
        "message": "Agent registered successfully.",
    }


# ── Match ───────────────────────────────────────────────

def match_agent(task: str, project: str, top_k: int, session) -> list[dict]:
    vs = VectorStore()
    task_emb = vs.encode([task])[0]
    results = vs.cosine_search(task_emb, project, top_k=top_k, session=session, model="agents")

    if not results:
        return []

    candidates = []
    for agent, distance in results:
        sim = round(1.0 - (distance / 2.0), 4)
        candidates.append({
            "agent_id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "department": agent.department,
            "capability_tags": _deserialize_tags(agent.capability_tags),
            "vector_similarity": sim,
        })

    # LLM 二次排序
    reranked = _llm_rerank(task, candidates)
    return reranked[:top_k]


def _llm_rerank(task: str, candidates: list[dict]) -> list[dict]:
    """用本地 Ollama 对候选 Agent 做二次排序"""
    import ollama

    candidate_text = ""
    for i, c in enumerate(candidates):
        tags = ", ".join(c.get("capability_tags", [])) or "无"
        candidate_text += (
            f"[{i}] {c['name']} ({c['department']})\n"
            f"    能力描述: {c['description']}\n"
            f"    标签: {tags}\n\n"
        )

    prompt = f"""你是一个 Agent 调度器。根据用户任务，从候选 Agent 中选择最合适的。

任务: {task}

候选 Agent:
{candidate_text}

按适合度从高到低排列所有候选，返回 JSON 数组。每个元素: candidate_index(候选编号), relevance_score(0-1), reason(一句话理由)。
只返回 JSON，不要其他内容。

示例: [{{"candidate_index": 0, "relevance_score": 0.92, "reason": "该Agent最擅长此任务"}}]"""

    try:
        resp = ollama.chat(
            model="qwen3:8b",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        content = resp["message"]["content"].strip()
        # 去掉可能的 markdown 包裹
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3]
            content = content.strip()

        rankings = json.loads(content)

        # 用 candidate_index 映射回实际的 agent_id
        merged = []
        for r in rankings:
            idx = r.get("candidate_index", -1)
            if 0 <= idx < len(candidates):
                c = candidates[idx]
                merged.append({
                    **c,
                    "relevance_score": r.get("relevance_score", c["vector_similarity"]),
                    "match_reason": r.get("reason", ""),
                })
        if merged:
            return merged
    except Exception as e:
        logger.warning("LLM rerank failed: %s, falling back to vector scores", e)

    # fallback: 直接用向量结果
    return [
        {**c, "relevance_score": c["vector_similarity"],
         "match_reason": "向量匹配"}
        for c in candidates
    ]


# ── Execute ─────────────────────────────────────────────

def execute_agent(agent_id: int, task: str, context: dict | None, session) -> dict:
    agent = session.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return None

    start = time.time()

    if agent.protocol == "http":
        result = _execute_http(agent, task, context)
    elif agent.protocol == "mcp":
        result = f"[MCP] Agent {agent.name}: MCP 协议调用待实现 (endpoint={agent.endpoint})"
    else:
        result = f"[Unknown] 不支持的协议: {agent.protocol}"

    latency = int((time.time() - start) * 1000)

    # 更新指标
    agent.total_calls = (agent.total_calls or 0) + 1
    agent.avg_latency_ms = int(
        (agent.avg_latency_ms * (agent.total_calls - 1) + latency) / agent.total_calls
    )
    session.commit()

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "task": task,
        "result": result,
        "latency_ms": latency,
    }


def _execute_http(agent: Agent, task: str, context: dict | None) -> str:
    import httpx

    payload = {"task": task}
    if context:
        payload["context"] = context
    try:
        resp = httpx.post(agent.endpoint, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        return f"HTTP error calling {agent.name}: {e}"
    except Exception as e:
        return f"Error calling {agent.name}: {e}"


def _execute_mcp(agent: Agent, task: str, context: dict | None) -> str:
    # MCP 调用待实现
    return f"[MCP] Agent {agent.name} called with task: {task}"


# ── CRUD ────────────────────────────────────────────────

def list_agents(project: str, department: str | None, session) -> list[dict]:
    q = session.query(Agent).filter(Agent.project == project)
    if department:
        q = q.filter(Agent.department == department)
    agents = q.order_by(Agent.created_at.desc()).all()
    return [_agent_to_result(a) for a in agents]


def get_agent(agent_id: int, session) -> dict | None:
    a = session.query(Agent).filter(Agent.id == agent_id).first()
    if not a:
        return None
    return {
        "id": a.id,
        "project": a.project,
        "name": a.name,
        "description": a.description,
        "endpoint": a.endpoint,
        "protocol": a.protocol,
        "input_schema": json.loads(a.input_schema) if a.input_schema else None,
        "output_schema": json.loads(a.output_schema) if a.output_schema else None,
        "tools": _deserialize_tags(a.tools),
        "department": a.department,
        "capability_tags": _deserialize_tags(a.capability_tags),
        "reliability_score": a.reliability_score,
        "avg_latency_ms": a.avg_latency_ms,
        "total_calls": a.total_calls,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def delete_agent(agent_id: int, session) -> bool:
    a = session.query(Agent).filter(Agent.id == agent_id).first()
    if not a:
        return False
    session.delete(a)
    session.commit()
    return True


def list_departments(project: str, session) -> list[dict]:
    rows = (
        session.query(Agent.department, text("count(*) as agent_count"))
        .filter(Agent.project == project)
        .group_by(Agent.department)
        .order_by(text("agent_count DESC"))
        .all()
    )
    return [{"department": r[0], "agent_count": r[1]} for r in rows]


def _agent_to_result(a: Agent) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "department": a.department,
        "protocol": a.protocol,
        "capability_tags": _deserialize_tags(a.capability_tags),
        "reliability_score": a.reliability_score,
        "similarity": None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
