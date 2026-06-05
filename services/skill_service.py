import logging
from store.db import SessionLocal, Skill
from store.vector_store import VectorStore
from config import DEDUP_HIGH_THRESHOLD, DEDUP_WARN_THRESHOLD, SEARCH_DEFAULT_TOP_K

logger = logging.getLogger(__name__)


def check_duplicate(embedding: list[float], project: str, session):
    """Find closest existing Skill in the same project by cosine distance.
    Returns (closest_skill | None, similarity: float | None)
    """
    vs = VectorStore()
    results = vs.cosine_search(embedding, project, top_k=1, session=session)
    if not results:
        return None, None
    skill, distance = results[0]
    similarity = 1.0 - (distance / 2.0)
    return skill, round(similarity, 4)


def upload_skill(project: str, parsed: dict, session) -> dict:
    """Embed description, dedup check, insert if accepted."""
    vs = VectorStore()
    emb = vs.encode([parsed["description"]])[0]

    closest, sim = check_duplicate(emb, project, session)

    if closest and sim > DEDUP_HIGH_THRESHOLD:
        return {
            "status": "rejected",
            "skill_id": None,
            "name": parsed["name"],
            "similarity": sim,
            "closest_name": closest.name,
            "message": f"Skill too similar to '{closest.name}' ({sim:.1%}). Upload rejected.",
        }

    skill = Skill(
        project=project,
        name=parsed["name"],
        description=parsed["description"],
        skill_content=f"---\nname: {parsed['name']}\ndescription: {parsed['description']}\n---\n\n{parsed['body']}",
        embedding=emb,
    )
    session.add(skill)
    session.commit()
    session.refresh(skill)

    if closest and sim > DEDUP_WARN_THRESHOLD:
        return {
            "status": "created_with_warning",
            "skill_id": skill.id,
            "name": parsed["name"],
            "similarity": sim,
            "closest_name": closest.name,
            "message": f"Similar to '{closest.name}' ({sim:.1%}). Consider reviewing for redundancy.",
        }

    return {
        "status": "created",
        "skill_id": skill.id,
        "name": parsed["name"],
        "similarity": None,
        "closest_name": None,
        "message": "Skill created successfully.",
    }


def search_skills(query: str, project: str, top_k: int, session) -> list[dict]:
    vs = VectorStore()
    emb = vs.encode([query])[0]
    results = vs.cosine_search(emb, project, top_k, session=session)
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "author": s.author,
            "version": s.version,
            "similarity": round(1.0 - (d / 2.0), 4),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s, d in results
    ]


def list_skills(project: str, session) -> list[dict]:
    skills = (
        session.query(Skill)
        .filter(Skill.project == project)
        .order_by(Skill.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "author": s.author,
            "version": s.version,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in skills
    ]


def get_skill(skill_id: int, session) -> dict | None:
    s = session.query(Skill).filter(Skill.id == skill_id).first()
    if not s:
        return None
    return {
        "id": s.id,
        "project": s.project,
        "name": s.name,
        "description": s.description,
        "author": s.author,
        "version": s.version,
        "skill_content": s.skill_content,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def delete_skill(skill_id: int, session) -> bool:
    s = session.query(Skill).filter(Skill.id == skill_id).first()
    if not s:
        return False
    session.delete(s)
    session.commit()
    return True
