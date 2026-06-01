import hashlib
import hmac
import os
from typing import ClassVar, Optional

from pydantic import Field, field_validator

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError


def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2 with SHA256 and a random salt."""
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return salt.hex() + ":" + pw_hash.hex()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored salt and hash."""
    try:
        salt_hex, hash_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
        return hmac.compare_digest(pw_hash.hex(), hash_hex)
    except Exception:
        return False


class User(ObjectModel):
    table_name: ClassVar[str] = "user"
    username: str
    password_hash: str
    display_name: str
    status: str = "pending"  # "pending", "active", "rejected"
    role: str = "user"  # "user", "admin"

    @field_validator("username")
    @classmethod
    def username_must_not_be_empty(cls, v):
        if not v.strip():
            raise InvalidInputError("Username cannot be empty")
        return v.strip().lower()  # Force lowercase username for consistency

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_empty(cls, v):
        if not v.strip():
            raise InvalidInputError("Display name cannot be empty")
        return v.strip()

    @classmethod
    async def get_by_username(cls, username: str) -> Optional["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE username = $username LIMIT 1",
                {"username": username.strip().lower()},
            )
            if result:
                return cls(**result[0])
            return None
        except Exception as e:
            raise DatabaseOperationError(e)
