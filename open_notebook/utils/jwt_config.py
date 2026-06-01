"""Shared JWT configuration for authentication middleware and routers."""

import os

from open_notebook.utils.encryption import get_secret_from_env

# Use AUTH_JWT_SECRET, fall back to OPEN_NOTEBOOK_ENCRYPTION_KEY, then default
JWT_SECRET = os.getenv(
    "AUTH_JWT_SECRET",
    get_secret_from_env("OPEN_NOTEBOOK_ENCRYPTION_KEY")
    or "lumiton-omax-default-jwt-secret-key-change-me",
)
JWT_ALGORITHM = "HS256"
