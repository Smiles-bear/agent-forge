import json
import logging
import time
from sqlalchemy import text
from store.db import SessionLocal, Agent
from store.vector_store import VectorStore
from config import (
    DEDUP_HIGH_THRESHOLD, SEARCH_DEFAULT_TOP_K,
    TECH_TAGS, TASK_TYPE_TAGS, DOMAIN_TAGS, DIFFICULTY_LEVELS,
)

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


def _validate_tags(tech_stack: list[str], task_types: list[str],
                   domains: list[str], difficulty: str):
    """校验所有标签在受控词汇表内，不在则 raise ValueError。"""
    errors = []
    for tag in tech_stack:
        if tag not in TECH_TAGS:
            errors.append(f"tech_stack '{tag}' not in allowed values")
    for tag in task_types:
        if tag not in TASK_TYPE_TAGS:
            errors.append(f"task_types '{tag}' not in allowed values")
    for tag in domains:
        if tag not in DOMAIN_TAGS:
            errors.append(f"domains '{tag}' not in allowed values")
    if difficulty not in DIFFICULTY_LEVELS:
        errors.append(f"difficulty '{difficulty}' not in allowed values")
    if errors:
        raise ValueError("; ".join(errors))


# ── Register ────────────────────────────────────────────

def register_agent(project: str, data: dict, session) -> dict:
    _validate_tags(
        data["tech_stack"], data["task_types"],
        data["domains"], data["difficulty"],
    )

    vs = VectorStore()

    # 四个维度各自 encode
    tech_text = ", ".join(data["tech_stack"])
    task_text = ", ".join(data["task_types"])
    domain_text = ", ".join(data["domains"])
    diff_text = data["difficulty"]

    texts = [tech_text, task_text, domain_text, diff_text]
    embeddings = vs.encode(texts)
    tech_emb, task_emb, domain_emb, diff_emb = embeddings

    # 去重：四维各搜最相似 Agent，取平均相似度
    sims = []
    closest_agent = None
    for dim_name, emb in [("tech", tech_emb), ("task", task_emb),
                           ("domain", domain_emb), ("difficulty", diff_emb)]:
        results = vs.cosine_search(emb, project, top_k=1, session=session,
                                   model="agents", dim=dim_name)
        if results:
            agent, dist = results[0]
            sims.append(round(1.0 - (dist / 2.0), 4))
            closest_agent = agent

    avg_sim = round(sum(sims) / len(sims), 4) if sims else 0

    if avg_sim > DEDUP_HIGH_THRESHOLD:
        return {
            "status": "rejected",
            "agent_id": None,
            "name": data["name"],
            "similarity": avg_sim,
            "closest_agent": closest_agent.name if closest_agent else None,
            "message": f"Agent too similar to '{closest_agent.name}' ({avg_sim:.1%}). Register rejected.",
        }

    agent = Agent(
        project=project,
        name=data["name"],
        tech_stack=data["tech_stack"],
        task_types=data["task_types"],
        domains=data["domains"],
        difficulty=data["difficulty"],
        tech_emb=tech_emb,
        task_emb=task_emb,
        domain_emb=domain_emb,
        difficulty_emb=diff_emb,
        endpoint=data["endpoint"],
        protocol=data.get("protocol", "http"),
        input_schema=json.dumps(data.get("input_schema"), ensure_ascii=False) if data.get("input_schema") else None,
        output_schema=json.dumps(data.get("output_schema"), ensure_ascii=False) if data.get("output_schema") else None,
        tools=_serialize_tags(data.get("tools")),
        department=data.get("department", "uncategorized"),
        capability_tags=_serialize_tags(data.get("capability_tags")),
        verification_config=json.dumps(data["verification"], ensure_ascii=False) if data.get("verification") else None,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # 协议验证
    protocol_check = _validate_protocol(data["endpoint"])

    return {
        "status": "created",
        "agent_id": agent.id,
        "name": agent.name,
        "similarity": avg_sim if avg_sim else None,
        "closest_agent": closest_agent.name if closest_agent else None,
        "endpoint_reachable": protocol_check["ok"],
        "protocol_check": protocol_check,
        "message": "Agent registered successfully."
        if protocol_check["ok"]
        else f"Agent registered but protocol check failed: {protocol_check.get('error', 'unknown')}",
    }


def _validate_protocol(endpoint: str) -> dict:
    """Validate agent endpoint conforms to AgentForge Protocol.
    Returns {"ok": true/false, "health": true/false, "run": true/false, "error": "..."}
    """
    import httpx
    from urllib.parse import urlparse, urlunparse

    result = {"ok": False, "health": False, "run": False, "error": None}
    parsed = urlparse(endpoint.rstrip("/"))

    # 1. Health check
    try:
        health_url = urlunparse(parsed._replace(path="/health"))
        resp = httpx.get(health_url, timeout=5)
        if resp.status_code == 200:
            result["health"] = True
    except Exception as e:
        result["error"] = f"Health check failed: {e}"
        return result

    # 2. Protocol probe — send a test task, check response format
    try:
        run_url = endpoint.rstrip("/")
        probe = {"task": "protocol probe — reply with {\"agent\":\"...\",\"result\":\"ok\"}", "context": None}
        resp = httpx.post(run_url, json=probe, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "agent" in data and "result" in data:
                result["run"] = True
            else:
                result["error"] = f"Response missing 'agent' or 'result' fields: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        else:
            result["error"] = f"/run returned {resp.status_code}"
    except Exception as e:
        result["error"] = f"Protocol probe failed: {e}"
        return result

    result["ok"] = result["health"] and result["run"]
    return result


def _ping_endpoint(endpoint: str) -> bool:
    """Check if agent endpoint is reachable (kept for backward compat)."""
    result = _validate_protocol(endpoint)
    return result["ok"]


# ── Match ───────────────────────────────────────────────

def match_agent(task: str, project: str, top_k: int, session) -> list[dict]:
    vs = VectorStore()
    task_emb = vs.encode([task])[0]

    # 四维并行搜索，去重候选池
    candidates = vs.cosine_search_multi_dim(task_emb, project, top_k, session)

    if not candidates:
        return []

    # LLM 二次排序
    reranked = _llm_rerank(task, candidates)
    return reranked[:top_k]


def _llm_rerank(task: str, candidates: list[dict]) -> list[dict]:
    import ollama

    candidate_text = ""
    for i, c in enumerate(candidates):
        agent = c["agent"]
        tags = ", ".join(_deserialize_tags(agent.capability_tags)) or "无"
        tech_str = ", ".join(agent.tech_stack or [])
        task_str = ", ".join(agent.task_types or [])
        domain_str = ", ".join(agent.domains or [])

        candidate_text += (
            f"[{i}] {agent.name} ({agent.department})\n"
            f"    技术栈: {tech_str}\n"
            f"    任务类型: {task_str}\n"
            f"    领域: {domain_str}\n"
            f"    难度: {agent.difficulty}\n"
            f"    技术栈相似度: {c.get('tech_sim', 'N/A')}\n"
            f"    任务类型相似度: {c.get('task_sim', 'N/A')}\n"
            f"    领域相似度: {c.get('domain_sim', 'N/A')}\n"
            f"    难度匹配度: {c.get('diff_sim', 'N/A')}\n"
            f"    标签: {tags}\n\n"
        )

    prompt = f"""你是一个 Agent 调度器。根据用户任务，从候选 Agent 中选择最合适的。

任务: {task}

候选 Agent（含四维相似度分数）:
{candidate_text}

按适合度从高到低排列所有候选，返回 JSON 数组。每个元素: candidate_index(候选编号), relevance_score(0-1), reason(一句话理由)。
只返回 JSON，不要其他内容。

示例: [{{"candidate_index": 0, "relevance_score": 0.92, "reason": "该Agent的技术栈和任务类型最匹配"}}]"""

    try:
        resp = ollama.chat(
            model="qwen3:8b",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        content = resp["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3]
            content = content.strip()

        rankings = json.loads(content)

        merged = []
        for r in rankings:
            idx = r.get("candidate_index", -1)
            if 0 <= idx < len(candidates):
                c = candidates[idx]
                merged.append({
                    "agent_id": c["agent"].id,
                    "name": c["agent"].name,
                    "tech_stack": c["agent"].tech_stack or [],
                    "task_types": c["agent"].task_types or [],
                    "domains": c["agent"].domains or [],
                    "difficulty": c["agent"].difficulty,
                    "department": c["agent"].department,
                    "capability_tags": _deserialize_tags(c["agent"].capability_tags),
                    "tech_sim": c.get("tech_sim"),
                    "task_sim": c.get("task_sim"),
                    "domain_sim": c.get("domain_sim"),
                    "diff_sim": c.get("diff_sim"),
                    "relevance_score": r.get("relevance_score", 0.5),
                    "match_reason": r.get("reason", ""),
                })
        if merged:
            return merged
    except Exception as e:
        logger.warning("LLM rerank failed: %s, falling back to vector scores", e)

    # fallback: 用各维平均相似度排序
    fallback = []
    for c in candidates:
        sims = [v for v in [c.get("tech_sim"), c.get("task_sim"),
                            c.get("domain_sim"), c.get("diff_sim")] if v is not None]
        avg = sum(sims) / len(sims) if sims else 0
        fallback.append({
            "agent_id": c["agent"].id,
            "name": c["agent"].name,
            "tech_stack": c["agent"].tech_stack or [],
            "task_types": c["agent"].task_types or [],
            "domains": c["agent"].domains or [],
            "difficulty": c["agent"].difficulty,
            "department": c["agent"].department,
            "capability_tags": _deserialize_tags(c["agent"].capability_tags),
            "tech_sim": c.get("tech_sim"),
            "task_sim": c.get("task_sim"),
            "domain_sim": c.get("domain_sim"),
            "diff_sim": c.get("diff_sim"),
            "relevance_score": round(avg, 4),
            "match_reason": "向量匹配（LLM fallback）",
        })
    fallback.sort(key=lambda x: x["relevance_score"], reverse=True)
    return fallback


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
        "tech_stack": a.tech_stack or [],
        "task_types": a.task_types or [],
        "domains": a.domains or [],
        "difficulty": a.difficulty,
        "verification_config": json.loads(a.verification_config) if a.verification_config else None,
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
        "tech_stack": a.tech_stack or [],
        "task_types": a.task_types or [],
        "domains": a.domains or [],
        "difficulty": a.difficulty,
        "department": a.department,
        "protocol": a.protocol,
        "capability_tags": _deserialize_tags(a.capability_tags),
        "reliability_score": a.reliability_score,
        "similarity": None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
