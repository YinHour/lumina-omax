from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from open_notebook.ai.usage_audit import (
    request_usage_context,
    reset_usage_audit_context,
    set_usage_audit_context,
)
from open_notebook.utils.encryption import get_secret_from_env
from open_notebook.utils.jwt_config import JWT_ALGORITHM, JWT_SECRET


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware enforcing JWT-based auth on all protected API routes.
    
    Two authentication paths are supported:
    1. JWT tokens (primary) — issued via /auth/login, validated using secrets from
       open_notebook.utils.jwt_config.
    2. Master password backdoor — if OPEN_NOTEBOOK_PASSWORD is configured, the raw
       password can be used as a Bearer token to gain super-admin access.
    
    Routes listed in excluded_paths bypass authentication entirely.
    """
    
    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def _call_next_with_usage(self, request: Request, call_next, user: dict):
        context = request_usage_context(user, request.method, request.url.path)
        token = set_usage_audit_context(context)
        try:
            response = await call_next(request)
        finally:
            reset_usage_audit_context(token)

        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None:
            async def audited_body_iterator():
                iterator_token = set_usage_audit_context(context)
                try:
                    async for chunk in body_iterator:
                        yield chunk
                finally:
                    reset_usage_audit_context(iterator_token)

            response.body_iterator = audited_body_iterator()
        return response

    def _optional_audit_user(self, request: Request) -> Optional[dict]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        if self.password and token == self.password:
            return {
                "id": "user:admin",
                "username": "admin",
                "display_name": "System Admin",
                "role": "admin",
                "status": "active",
            }
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            return None
        return payload if payload.get("status") == "active" else None

    async def dispatch(self, request: Request, call_next):
        # Keep the existing prefix-compatible exclusions, but capture identity
        # from valid tokens so model work can still be attributed safely.
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            audit_user = self._optional_audit_user(request)
            if audit_user:
                request.state.user = audit_user
                return await self._call_next_with_usage(
                    request,
                    call_next,
                    audit_user,
                )
            return await call_next(request)

        # Skip authentication for CORS preflight requests (OPTIONS)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Expected format: "Bearer {token}"
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 1. Backdoor Super Admin Authorization check
        if self.password and token == self.password:
            # Grant full access as super admin
            request.state.user = {
                "id": "user:admin",
                "username": "admin",
                "display_name": "System Admin",
                "role": "admin",
                "status": "active",
            }
            return await self._call_next_with_usage(
                request,
                call_next,
                request.state.user,
            )

        # 2. JWT Verification
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Check user status
            user_status = payload.get("status")
            if user_status == "pending":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "账号等待管理员审批，请联系管理员"},
                )
            elif user_status == "rejected":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "您的账号注册申请已被拒绝"},
                )
            elif user_status != "active":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "您的账号未激活"},
                )

            # Store payload in request state
            request.state.user = payload
            
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or malformed authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # User is authenticated, proceed
        return await self._call_next_with_usage(request, call_next, request.state.user)


# Optional: HTTPBearer security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)


def check_api_password(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> bool:
    """
    Utility function for route-level auth checks.
    Supports super admin backdoor.
    """
    password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
    if not password:
        return True

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Allow master password backdoor
    if credentials.credentials == password:
        return True

    # Check JWT
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("status") == "active":
            return True
    except jwt.PyJWTError:
        pass

    raise HTTPException(
        status_code=401,
        detail="Invalid password or token",
        headers={"WWW-Authenticate": "Bearer"},
    )
