import os
import json
import logging
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


class RunRequest(BaseModel):
    task: str
    context: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    payload = {
        "name": NAME,
        "tech_stack": TECH_STACK,
        "task_types": TASK_TYPES,
        "domains": DOMAINS,
        "difficulty": DIFFICULTY,
        "endpoint": f"http://{NAME.lower().replace(' ', '-')}:{PORT}/run",
        "protocol": "http",
        "department": DEPARTMENT,
    }
    import time
    for attempt in range(30):
        try:
            resp = httpx.post(
                f"{REGISTRY_URL}/api/v1/{PROJECT}/agents/register",
                json=payload, timeout=10,
            )
            logger.info("Registered to registry: %s (id=%s)", resp.json().get("status"), resp.json().get("agent_id"))
            break
        except Exception as e:
            if attempt < 29:
                logger.info("Registration attempt %d failed, retrying... (%s)", attempt + 1, e)
                time.sleep(2)
            else:
                logger.warning("Registration failed after 30 attempts: %s", e)
    yield


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
    resp = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return {
        "agent": NAME,
        "result": data["message"]["content"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "agent": NAME}
