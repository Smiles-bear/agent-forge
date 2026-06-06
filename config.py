import os

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kb_user:kb_pass@127.0.0.1:5433/skill_registry")
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

DEDUP_HIGH_THRESHOLD = 0.95
DEDUP_WARN_THRESHOLD = 0.85
SEARCH_DEFAULT_TOP_K = 10

# ── Agent 能力维度受控词汇表 ──

TECH_TAGS = [
    "react", "vue", "angular", "svelte",
    "typescript", "javascript", "python", "go", "rust", "java",
    "fastapi", "flask", "django", "express", "nextjs",
    "postgresql", "mysql", "redis", "mongodb",
    "docker", "kubernetes", "nginx",
    "css", "html", "tailwind", "webpack", "vite",
]

TASK_TYPE_TAGS = [
    "develop", "review", "debug", "refactor",
    "test", "document", "design", "deploy",
]

DOMAIN_TAGS = [
    "frontend", "backend", "fullstack",
    "devops", "security", "data",
    "mobile", "embedded", "ai_ml",
]

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

# ── Agent 能力验证 ──

VERIFICATION_TIMEOUT = 180      # 每道测试题超时秒数
RUBRIC_MODEL = "qwen3:8b"       # 量规评分的 LLM 模型
RUBRIC_DOUBLE_CHECK = True       # 双评取低分
