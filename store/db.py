from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ARRAY
from sqlalchemy.orm import sessionmaker, declarative_base
from pgvector.sqlalchemy import Vector
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project = Column(String(128), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    author = Column(String(128), default="unknown")
    version = Column(String(32), default="1.0.0")
    skill_content = Column(Text, nullable=False)
    embedding = Column(Vector(512), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project = Column(String(128), nullable=False, index=True)
    name = Column(String(256), nullable=False)

    # 四维能力标签
    tech_stack = Column(ARRAY(String), nullable=False, default=list)
    task_types = Column(ARRAY(String), nullable=False, default=list)
    domains = Column(ARRAY(String), nullable=False, default=list)
    difficulty = Column(String(32), default="medium")

    # 四维能力向量
    tech_emb = Column(Vector(512), nullable=False)
    task_emb = Column(Vector(512), nullable=False)
    domain_emb = Column(Vector(512), nullable=False)
    difficulty_emb = Column(Vector(512), nullable=False)

    # 可执行信息
    endpoint = Column(String(512), nullable=False)
    protocol = Column(String(32), default="http")
    input_schema = Column(Text, nullable=True)
    output_schema = Column(Text, nullable=True)
    tools = Column(Text, nullable=True)

    # 分类与分组
    department = Column(String(128), default="uncategorized")
    capability_tags = Column(Text, nullable=True)

    # 能力验证
    verification_config = Column(Text, nullable=True, comment="JSON: test_cases + steps")

    # 运行时指标
    reliability_score = Column(Float, nullable=True, default=None)
    verified_at = Column(DateTime, nullable=True, comment="Last verification timestamp")
    avg_latency_ms = Column(Integer, default=0)
    total_calls = Column(Integer, default=0)

    # 健康监控
    last_health_ok = Column(DateTime, nullable=True, comment="Last successful health check")
    consecutive_failures = Column(Integer, default=0, comment="Consecutive failed health checks")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, nullable=False, index=True)
    test_index = Column(Integer, nullable=False, comment="第几道测试题(0-based)")
    step_scores = Column(Text, nullable=False, comment="JSON: {'contract': 1.0, 'rubric': 0.75}")
    overall = Column(Float, nullable=False, comment="本题最终得分")
    raw_output = Column(Text, nullable=True, comment="Agent 原始回复")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    from sqlalchemy import text
    with engine.connect() as conn:
        if "postgresql" in str(engine.url):
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
