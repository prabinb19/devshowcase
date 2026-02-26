"""Token encryption/decryption using Fernet symmetric encryption — lazy singleton."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy singleton Fernet instance from settings."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.token_encryption_key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string, returning a base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
