import faiss
import numpy as np
from loguru import logger

DIMENSION = 384  # all-MiniLM-L6-v2 output dimension


class VectorStore:
    """In-memory FAISS vector store for semantic document ranking."""

    def __init__(self):
        self.index = faiss.IndexFlatL2(DIMENSION)
        self.documents: list[dict] = []

    def reset(self):
        self.index = faiss.IndexFlatL2(DIMENSION)
        self.documents = []

    def add_documents(self, embeddings: list, docs: list[dict]):
        """Add documents with their embeddings to the store."""
        if embeddings is None or len(embeddings) == 0:
            return
        vecs = np.array(embeddings).astype("float32")
        self.index.add(vecs)
        self.documents.extend(docs)
        logger.debug(f"Added {len(docs)} docs to vector store (total: {len(self.documents)})")

    def search(self, query_embedding, k: int = 5) -> list[dict]:
        """Find top-k most similar documents to the query embedding."""
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

        logger.debug(f"Vector search returned {len(results)} results")
        return results
