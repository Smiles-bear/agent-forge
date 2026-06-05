from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL
from store.db import Skill

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
                      top_k: int, session):
        return session.query(
            Skill,
            Skill.embedding.cosine_distance(query_embedding).label("distance")
        ).filter(Skill.project == project) \
         .order_by("distance").limit(top_k).all()
