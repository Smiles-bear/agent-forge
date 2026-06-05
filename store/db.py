from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
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
    description = Column(Text, nullable=False)
    embedding = Column(Vector(512), nullable=False)

    # 可执行信息
    endpoint = Column(String(512), nullable=False)
    protocol = Column(String(32), default="http")
    input_schema = Column(Text, nullable=True)
    output_schema = Column(Text, nullable=True)
    tools = Column(Text, nullable=True)

    # 分类与分组
    department = Column(String(128), default="uncategorized")
    capability_tags = Column(Text, nullable=True)

    # 运行时指标
    reliability_score = Column(Float, default=0.0)
    avg_latency_ms = Column(Integer, default=0)
    total_calls = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    from sqlalchemy import text
    with engine.connect() as conn:
        if "postgresql" in str(engine.url):
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
