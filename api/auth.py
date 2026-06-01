from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from open_notebook.utils.encryption import get_secret_from_env
from open_notebook.utils.jwt_config import JWT_ALGORITHM, JWT_SECRET


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check authentication for all API requests.
    Supports standard JWT tokens, as well as the master password as a backdoor.
    Always active if OPEN_NOTEBOOK_PASSWORD is set.
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

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths (prefix match)
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
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
            return await call_next(request)

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
        response = await call_next(request)
        return response


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
