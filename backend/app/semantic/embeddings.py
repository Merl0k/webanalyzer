from sentence_transformers import SentenceTransformer
from loguru import logger

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Model loaded")
    return _model


def create_embedding(text: str):
    """Create a vector embedding for a text string."""
    model = _get_model()
    return model.encode(text)


def create_embeddings_batch(texts: list[str]) -> list:
    """Create embeddings for multiple texts at once (faster)."""
    model = _get_model()
    return model.encode(texts)
