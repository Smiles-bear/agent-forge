import logging
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from store.db import init_db
from routers.api import router as api_router
from routers.agent_api import router as agent_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _health_monitor():
    """Background task: ping all agent health endpoints every 60s."""
    import httpx
    from store.db import SessionLocal, Agent

    await asyncio.sleep(30)  # Wait for initial registrations
    while True:
        try:
            session = SessionLocal()
            agents = session.query(Agent).all()
            for agent in agents:
                try:
                    health_url = agent.endpoint.rstrip("/").replace("/run", "/health")
                    resp = httpx.get(health_url, timeout=5)
                    if resp.status_code == 200:
                        agent.last_health_ok = datetime.now(timezone.utc)
                        agent.consecutive_failures = 0
                    else:
                        agent.consecutive_failures = (agent.consecutive_failures or 0) + 1
                except Exception:
                    agent.consecutive_failures = (agent.consecutive_failures or 0) + 1
            session.commit()
            session.close()
        except Exception as e:
            logger.warning("Health monitor error: %s", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("DB init skipped: %s", e)
    monitor_task = asyncio.create_task(_health_monitor())
    yield
    monitor_task.cancel()


app = FastAPI(
    title="AgentForge",
    description="Multi-agent platform with 4-dim capability matching, Docker deployment, and automated verification",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(agent_router)


@app.get("/")
async def root():
    return {
        "service": "AgentForge",
        "version": "2.0.0",
        "endpoints": {
            "skills": {
                "upload": "POST /api/v1/{project}/skills/upload",
                "search": "GET /api/v1/{project}/skills/search?q=...&top_k=5",
                "list": "GET /api/v1/{project}/skills",
                "detail": "GET /api/v1/{project}/skills/{id}",
                "delete": "DELETE /api/v1/{project}/skills/{id}",
            },
            "agents": {
                "register": "POST /api/v1/{project}/agents/register",
                "match": "POST /api/v1/{project}/agents/match",
                "execute": "POST /api/v1/{project}/agents/{id}/execute",
                "list": "GET /api/v1/{project}/agents",
                "detail": "GET /api/v1/{project}/agents/{id}",
                "delete": "DELETE /api/v1/{project}/agents/{id}",
                "departments": "GET /api/v1/{project}/departments",
            },
            "health": {
                "project": "GET /api/v1/{project}/health",
                "global": "GET /api/v1/health",
            },
        },
    }
