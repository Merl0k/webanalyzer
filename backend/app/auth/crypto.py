"""
Fernet symmetric encryption for API keys.
Generate key once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Set as ENCRYPTION_KEY in .env
"""
import os
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

_KEY = os.getenv("ENCRYPTION_KEY", "")
_ephemeral_key = None


def _fernet() -> Fernet:
    global _ephemeral_key
    key = _KEY.strip()
    if not key:
        if _ephemeral_key is None:
            _ephemeral_key = Fernet.generate_key().decode()
            logger.warning("ENCRYPTION_KEY not set — using ephemeral key (lost on restart). Set it in .env!")
        key = _ephemeral_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Cannot decrypt API key — encryption key mismatch")
