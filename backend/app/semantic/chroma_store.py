"""
app/semantic/chroma_store.py

Persistent vector store using ChromaDB.
- Collections are keyed per-query so searches stay isolated.
- Embeddings are provided externally (sentence-transformers).
- Data persists across restarts via volume-mounted ./chroma_data.
"""
import uuid
import numpy as np
from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
    logger.warning("chromadb not installed — falling back to FAISS in-memory")


# ── FAISS fallback (identical to original vector_store.py) ─────────
class _FaissStore:
    def __init__(self):
        import faiss
        self.index = faiss.IndexFlatL2(384)
        self.documents: list[dict] = []

    def add_documents(self, embeddings, docs, _query=""):
        if embeddings is None or len(embeddings) == 0:
            return
        vecs = np.array(embeddings).astype("float32")
        self.index.add(vecs)
        self.documents.extend(docs)

    def search(self, query_embedding, k=5) -> list[dict]:
        if self.index.ntotal == 0:
            return self.documents
        k = min(k, self.index.ntotal)
        vec = np.array([query_embedding]).astype("float32")
        distances, indices = self.index.search(vec, k)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                doc = self.documents[idx].copy()
                doc["_score"] = float(distances[0][i])
                results.append(doc)
        return results


# ── ChromaDB store ──────────────────────────────────────────────────
class _ChromaStore:
    PERSIST_DIR = "./chroma_data"

    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=self.PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection_name: str | None = None
        self._collection = None
        self._docs: list[dict] = []

    def _get_or_create_collection(self, name: str):
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, embeddings: list, docs: list[dict], query: str = ""):
        """
        Create an isolated ephemeral collection for this search session.
        Naming: search_<uuid4> — deleted after use to avoid stale data.
        """
        if embeddings is None or len(embeddings) == 0 or not docs:
            return

        coll_name = f"search_{uuid.uuid4().hex}"
        self._collection_name = coll_name
        self._get_or_create_collection(coll_name)
        self._docs = docs

        ids = [f"doc_{i}" for i in range(len(docs))]
        metadatas = [
            {"title": d.get("title", "")[:256],
             "url":   d.get("url",   "")[:512],
             "domain":d.get("domain","")[:128]}
            for d in docs
        ]
        # ChromaDB needs list[list[float]]
        vecs = [emb.tolist() if hasattr(emb, "tolist") else list(emb)
                for emb in embeddings]

        self._collection.add(
            ids=ids,
            embeddings=vecs,
            metadatas=metadatas,
        )
        logger.debug(f"ChromaDB: added {len(docs)} docs to collection '{coll_name}'")

    def search(self, query_embedding, k: int = 5) -> list[dict]:
        if self._collection is None or not self._docs:
            return self._docs

        k = min(k, len(self._docs))
        vec = query_embedding.tolist() if hasattr(query_embedding, "tolist") else list(query_embedding)

        results = self._collection.query(
            query_embeddings=[vec],
            n_results=k,
        )

        ids = results["ids"][0]
        distances = results["distances"][0]

        out = []
        for doc_id, dist in zip(ids, distances):
            idx = int(doc_id.split("_")[1])
            if idx < len(self._docs):
                doc = self._docs[idx].copy()
                doc["_score"] = float(dist)
                out.append(doc)

        # Cleanup ephemeral collection
        try:
            if self._collection_name:
                self._client.delete_collection(self._collection_name)
                logger.debug(f"ChromaDB: deleted collection '{self._collection_name}'")
        except Exception:
            pass

        logger.debug(f"ChromaDB search returned {len(out)} results")
        return out


# ── Public factory ──────────────────────────────────────────────────
def ChromaStore():
    """Return the best available vector store."""
    if _CHROMA_AVAILABLE:
        return _ChromaStore()
    return _FaissStore()
