import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from store.db import init_db
from routers.api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("DB init skipped: %s", e)
    yield


app = FastAPI(
    title="Skill Registry",
    description="AI Skill management with vector-based semantic search and deduplication",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "service": "Skill Registry",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /api/v1/{project}/skills/upload",
            "search": "GET /api/v1/{project}/skills/search?q=...&top_k=5",
            "list": "GET /api/v1/{project}/skills",
            "detail": "GET /api/v1/{project}/skills/{id}",
            "delete": "DELETE /api/v1/{project}/skills/{id}",
            "project_health": "GET /api/v1/{project}/health",
            "global_health": "GET /api/v1/health",
        },
    }
