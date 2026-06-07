from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL
from store.db import Skill, Agent

_shared_embedder = None


def get_embedder():
    global _shared_embedder
    if _shared_embedder is None:
        _shared_embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _shared_embedder


class VectorStore:
    def __init__(self):
        self.embedder = get_embedder()

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.encode(texts).tolist()

    def cosine_search(self, query_embedding: list[float], project: str,
                      top_k: int, session, model: str = "skills", dim: str = None):
        """单维度余弦搜索。model='skills' 走 Skill 表，否则走 Agent 表 + 指定 dim 列。"""
        if model in ("skills", "skill"):
            table = Skill
            col = Skill.embedding
        else:
            table = Agent
            dim_cols = {
                "tech": Agent.tech_emb,
                "task": Agent.task_emb,
                "domain": Agent.domain_emb,
                "difficulty": Agent.difficulty_emb,
            }
            col = dim_cols.get(dim, Agent.tech_emb)

        return session.query(
            table,
            col.cosine_distance(query_embedding).label("distance")
        ).filter(table.project == project) \
         .order_by("distance").limit(top_k).all()

    def cosine_search_multi_dim(self, query_embedding: list[float], project: str,
                                top_k: int, session):
        """四维度并行搜索，返回去重候选池。
        每个候选: {"agent": Agent, "tech_sim": float|None, "task_sim": float|None, ...}
        """
        dims = {
            "tech": Agent.tech_emb,
            "task": Agent.task_emb,
            "domain": Agent.domain_emb,
            "diff": Agent.difficulty_emb,
        }

        candidates = {}  # agent_id -> dict
        for dim_name, col in dims.items():
            rows = session.query(
                Agent,
                col.cosine_distance(query_embedding).label("distance")
            ).filter(Agent.project == project) \
             .filter(Agent.reliability_score.isnot(None)) \
             .filter(Agent.consecutive_failures < 3) \
             .order_by("distance").limit(top_k).all()

            for agent, dist in rows:
                sim = round(1.0 - (dist / 2.0), 4)
                if agent.id not in candidates:
                    candidates[agent.id] = {
                        "agent": agent,
                        "tech_sim": None,
                        "task_sim": None,
                        "domain_sim": None,
                        "diff_sim": None,
                    }
                candidates[agent.id][f"{dim_name}_sim"] = sim

        return list(candidates.values())
