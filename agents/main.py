import os
import json
import logging
import time
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 环境变量注入 ──
NAME = os.environ["AGENT_NAME"]
PORT = int(os.environ["AGENT_PORT"])
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:8000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")

TECH_STACK = [t.strip() for t in os.environ.get("AGENT_TECH_STACK", "").split(",") if t.strip()]
TASK_TYPES = [t.strip() for t in os.environ.get("AGENT_TASK_TYPES", "").split(",") if t.strip()]
DOMAINS = [t.strip() for t in os.environ.get("AGENT_DOMAINS", "").split(",") if t.strip()]
DIFFICULTY = os.environ.get("AGENT_DIFFICULTY", "medium")
PROJECT = os.environ.get("AGENT_PROJECT", "it-department")
DEPARTMENT = os.environ.get("AGENT_DEPARTMENT", "IT")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
ENDPOINT = os.environ.get("AGENT_ENDPOINT", f"http://{NAME.lower().replace(' ', '-')}:{PORT}/run")


def _get_verification():
    raw = os.environ.get("AGENT_VERIFICATION", "")
    if raw:
        try:
            return {"verification": json.loads(raw)}
        except json.JSONDecodeError:
            logger.warning("AGENT_VERIFICATION parse failed")
    return {}


class RunRequest(BaseModel):
    task: str
    context: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在后台线程中注册，避免阻塞服务器启动
    # 服务器必须先启动，验证回调才能成功
    asyncio.create_task(_delayed_register())
    yield


async def _delayed_register():
    """延迟注册：等待服务器就绪后再向 registry 注册。"""
    await asyncio.sleep(3)  # 等服务器完全启动
    payload = {
        "name": NAME,
        "tech_stack": TECH_STACK,
        "task_types": TASK_TYPES,
        "domains": DOMAINS,
        "difficulty": DIFFICULTY,
        "endpoint": ENDPOINT,
        "protocol": "http",
        "department": DEPARTMENT,
        # 可选验证配置
        **_get_verification(),
    }
    for attempt in range(30):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{REGISTRY_URL}/api/v1/{PROJECT}/agents/register",
                    json=payload, timeout=10,
                )
                logger.info("Registered to registry: %s (id=%s)", resp.json().get("status"), resp.json().get("agent_id"))
                break
        except Exception as e:
            if attempt < 29:
                logger.info("Registration attempt %d failed, retrying... (%s)", attempt + 1, e)
                await asyncio.sleep(2)
            else:
                logger.warning("Registration failed after 30 attempts: %s", e)


app = FastAPI(title=NAME, lifespan=lifespan)


@app.post("/run")
async def run(req: RunRequest):
    context_str = json.dumps(req.context, ensure_ascii=False, indent=2) if req.context else ""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{req.task}\n\n{context_str}".strip()},
        ],
        "stream": False,
    }
    resp = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    return {
        "agent": NAME,
        "result": data["message"]["content"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "agent": NAME}
