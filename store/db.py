from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
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


def init_db():
    from sqlalchemy import text
    with engine.connect() as conn:
        if "postgresql" in str(engine.url):
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
