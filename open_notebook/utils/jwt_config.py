"""Shared JWT configuration for authentication middleware and routers."""

import os

from loguru import logger

from open_notebook.utils.encryption import get_secret_from_env

# Use AUTH_JWT_SECRET, fall back to OPEN_NOTEBOOK_ENCRYPTION_KEY.
# Refuse to silently use an insecure default in non-development environments.
_auth_jwt_secret = os.getenv("AUTH_JWT_SECRET")
_encryption_key = get_secret_from_env("OPEN_NOTEBOOK_ENCRYPTION_KEY")

_default_secret = "lumiton-omax-default-jwt-secret-key-change-me"

if _auth_jwt_secret:
    JWT_SECRET = _auth_jwt_secret
elif _encryption_key:
    JWT_SECRET = _encryption_key
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
        JWT_SECRET = _default_secret
    else:
        raise RuntimeError(
            "JWT secret is not configured. "
            "Set AUTH_JWT_SECRET or OPEN_NOTEBOOK_ENCRYPTION_KEY environment variables. "
            "Refusing to use insecure default in non-development environment."
        )

JWT_ALGORITHM = "HS256"
