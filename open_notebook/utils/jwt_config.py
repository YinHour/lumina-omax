"""Shared JWT configuration for authentication middleware and routers."""

import hashlib
import os

from loguru import logger

from open_notebook.utils.encryption import get_secret_from_env


def _derive_key(raw: str) -> str:
    """Derive a proper-length HS256 key from any string input.

    If the raw secret is shorter than 32 bytes, hash it with SHA-256 to
    produce a full 32-byte key. Otherwise return the raw value as-is.
    """
    if len(raw.encode()) < 32:
        return hashlib.sha256(raw.encode()).hexdigest()
    return raw


# Use AUTH_JWT_SECRET, fall back to OPEN_NOTEBOOK_ENCRYPTION_KEY.
# Refuse to silently use an insecure default in non-development environments.
_auth_jwt_secret = os.getenv("AUTH_JWT_SECRET")
_encryption_key = get_secret_from_env("OPEN_NOTEBOOK_ENCRYPTION_KEY")

_default_secret = "lumiton-omax-default-jwt-secret-key-change-me"

if _auth_jwt_secret:
    JWT_SECRET = _derive_key(_auth_jwt_secret)
elif _encryption_key:
    JWT_SECRET = _derive_key(_encryption_key)
else:
    env = os.getenv("OPEN_NOTEBOOK_ENV", "").lower()
    is_dev_like = env in {"dev", "development", "local", "test"}

    if is_dev_like:
        logger.warning(
            "Using insecure default JWT secret in '{}' environment. "
            "This must NOT be used in production. "
            "Set AUTH_JWT_SECRET or OPEN_NOTEBOOK_ENCRYPTION_KEY.",
            env or "unknown",
        )
        JWT_SECRET = _derive_key(_default_secret)
    else:
        raise RuntimeError(
            "JWT secret is not configured. "
            "Set AUTH_JWT_SECRET or OPEN_NOTEBOOK_ENCRYPTION_KEY environment variables. "
            "Refusing to use insecure default in non-development environment."
        )

JWT_ALGORITHM = "HS256"
