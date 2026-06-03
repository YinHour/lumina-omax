import hmac
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field

from api.rate_limiter import login_limiter, register_limiter
from open_notebook.domain.user import User, hash_password, verify_password
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError
from open_notebook.utils.encryption import get_secret_from_env
from open_notebook.utils.jwt_config import JWT_ALGORITHM, JWT_SECRET

router = APIRouter(prefix="/auth", tags=["auth"])


# Request/Response schemas
class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    role: str
    created: Optional[str] = None


class UserStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(active|rejected|pending)$")


class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user_from_state(request: Request) -> dict:
    """Dependency to get the current user injected by the middleware or decoded from JWT."""
    user = getattr(request.state, "user", None)
    if user:
        return user

    # Fallback: if middleware didn't set request.state.user (e.g., due to
    # ASGI scope/state lifecycle), decode the JWT token directly.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Check master password backdoor first
        master_pwd = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
        if master_pwd and hmac.compare_digest(token, master_pwd):
            return {
                "id": "user:admin",
                "username": "admin",
                "display_name": "System Admin",
                "role": "admin",
                "status": "active",
            }
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            status_check = payload.get("status")
            if status_check == "pending":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="账号等待管理员审批，请联系管理员",
                )
            if status_check == "rejected":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您的账号注册申请已被拒绝",
                )
            if status_check != "active":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您的账号未激活",
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(user: dict = Depends(get_current_user_from_state)):
    """Dependency to ensure the current user is an admin."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Admin privileges required.",
        )
    return user


@router.get("/status")
async def get_auth_status():
    """
    Check if authentication is enabled.
    Always returns True for Lumiton OMax user-auth system.
    """
    return {
        "auth_enabled": True,
        "message": "User-based authentication is enabled",
    }


@router.post("/register", response_model=UserResponse)
async def register_user(req: UserRegisterRequest, request: Request):
    """
    Self-register a new user. The account is created with 'pending' status by default
    and requires administrator approval.
    """
    await register_limiter.check(request)
    # Normalize username
    username_norm = req.username.strip().lower()

    # Super admin password check: do not allow registering "admin" if it exists or conflicts
    if username_norm == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username 'admin' is reserved",
        )

    # Check if user already exists
    existing = await User.get_by_username(username_norm)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Hash password
    pw_hash = hash_password(req.password)

    # Save user
    user = User(
        username=username_norm,
        password_hash=pw_hash,
        display_name=req.display_name.strip(),
        status="pending",
        role="user",
    )
    try:
        await user.save()
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again later.",
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(req: UserLoginRequest, request: Request):
    """
    Authenticate a user and return a JWT access token.
    Supports super admin login using OPEN_NOTEBOOK_PASSWORD.
    """
    await login_limiter.check(request)
    username_norm = req.username.strip().lower()
    master_password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")

    # Super Admin Backdoor Login
    if (
        (username_norm == "admin" or not username_norm)
        and master_password
        and req.password == master_password
    ):
        admin_user_data = {
            "id": "user:admin",
            "username": "admin",
            "display_name": "System Admin",
            "role": "admin",
            "status": "active",
        }
        token = create_access_token(admin_user_data)
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(**admin_user_data),
        )

    # Also check if the password matches master_password for any admin logging in
    if master_password and req.password == master_password:
        # Allow bypass with master password for any existing user, upgrading them to admin
        existing_user = await User.get_by_username(username_norm)
        if existing_user:
            user_data = {
                "id": existing_user.id,
                "username": existing_user.username,
                "display_name": existing_user.display_name,
                "role": "admin",  # Bypassed via backdoor, upgrade role
                "status": "active",
            }
            token = create_access_token(user_data)
            return LoginResponse(
                access_token=token,
                token_type="bearer",
                user=UserResponse(**user_data),
            )

    # Normal user database-backed login
    user = await User.get_by_username(username_norm)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号等待管理员审批，请联系管理员",
        )

    if user.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账号注册申请已被拒绝",
        )

    user_data = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }
    token = create_access_token(user_data)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user_from_state)):
    """Get the currently authenticated user's details."""
    return UserResponse(
        id=current_user.get("id"),
        username=current_user.get("username"),
        display_name=current_user.get("display_name"),
        status=current_user.get("status"),
        role=current_user.get("role"),
    )


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin_user: dict = Depends(require_admin),
):
    """List all registered users (Admin only)."""
    try:
        users = await User.get_all(order_by="created desc")
        return [
            UserResponse(
                id=u.id,
                username=user_username,
                display_name=u.display_name,
                status=u.status,
                role=u.role,
                created=u.created.strftime("%Y-%m-%d %H:%M:%S") if u.created else None,
            )
            for u in users
            if (user_username := getattr(u, "username", "")) != "admin"
        ]
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user list. Please try again later.",
        )


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    admin_user: dict = Depends(require_admin),
):
    """Approve, reject, or suspend a user account (Admin only)."""
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user.status = req.status
        await user.save()

        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user. Please try again later.",
        )


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    admin_user: dict = Depends(require_admin),
):
    """Update a user's role (Admin only). Protects the admin account from demotion."""
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Prevent demoting the system admin account
        if user.username == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change the role of the system admin account",
            )

        user.role = req.role
        await user.save()

        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user. Please try again later.",
        )


class UserPasswordResetRequest(BaseModel):
    password: str = Field(..., min_length=6, max_length=100)


class UserProfileUpdateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)


class UserChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=100)


@router.put("/users/{user_id}/password", response_model=UserResponse)
async def reset_user_password(
    user_id: str,
    req: UserPasswordResetRequest,
    admin_user: dict = Depends(require_admin),
):
    """Reset a user's password (Admin only)."""
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user.password_hash = hash_password(req.password)
        await user.save()

        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again later.",
        )


@router.post("/logout")
async def logout_user(current_user: dict = Depends(get_current_user_from_state)):
    """
    Logout endpoint. Since we use stateless JWTs, the client is responsible
    for discarding the token. This endpoint exists to provide a standard
    logout flow and allow future token blacklisting.
    """
    return {"message": "Logged out successfully", "username": current_user.get("username")}


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    req: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user_from_state),
):
    """Update the current user's display name."""
    try:
        user = await User.get(current_user["id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        stripped = req.display_name.strip()
        if not stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name cannot be empty",
            )
        user.display_name = stripped
        await user.save()
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile. Please try again later.",
        )


@router.put("/me/password", response_model=UserResponse)
async def change_my_password(
    req: UserChangePasswordRequest,
    current_user: dict = Depends(get_current_user_from_state),
):
    """Change the current user's password (requires old password verification)."""
    try:
        user = await User.get(current_user["id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if not verify_password(req.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码不正确",
            )
        user.password_hash = hash_password(req.new_password)
        await user.save()
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            role=user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password. Please try again later.",
        )
