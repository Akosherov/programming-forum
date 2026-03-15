from fastapi import APIRouter, Depends, Query
from services import user_service
from data.models import User, UserPublic, UserUpdate
from data.models import UserDelete, UserRole
from common.auth import get_current_user, get_current_admin
from common.response import success
from common.exceptions import ForbiddenError, NotFoundError


users_router = APIRouter(prefix='/users', tags=['Users'])


# ---------------- Authenticated User Endpoints ----------------


@users_router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the full profile of the currently authenticated user,
    including email, is_blocked, is_deleted, and role_id.
    This is the only endpoint that exposes sensitive fields to the user themselves.
    """
    return success(
        data={
            "user_id":    current_user.user_id,
            "first_name": current_user.first_name,
            "last_name":  current_user.last_name,
            "email":      current_user.email,
            "username":   current_user.username,
            "is_blocked": current_user.is_blocked,
            "is_deleted": current_user.is_deleted,
            "role_id":    current_user.role_id,
        },
        message="Profile retrieved"
    )


@users_router.get("/search")
def search_users(
    q: str | None = None,
    per_page: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Search users by username for invite purposes. Available to all authenticated users."""
    from services import user_service as _us
    users = _us.get_all(q, 1, per_page)
    return success(data=users, message="Users found")


@users_router.patch("/{user_id}")
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)
):

    if current_user.user_id != user_id and current_user.role_id != UserRole.ADMIN:
        raise ForbiddenError()

    updated_user = user_service.update_user(
        user_id,
        user_update,
        current_user=current_user
    )

    if not updated_user:
        raise NotFoundError("User not found")

    return success(
        data=UserPublic.from_user(updated_user),
        message="User updated"
    )


@users_router.delete("/{user_id}")
def delete_user(
    user_id: int,
    data: UserDelete,
    current_user: User = Depends(get_current_user)
):
    user_service.delete_user(user_id, data, current_user)
    return success(message="User deleted")


@users_router.get("/me/topics")
def get_my_topics(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    result = user_service.get_my_topics(current_user.user_id, page, per_page)
    return success(data=result, message="Topics retrieved")


@users_router.get("/me/replies")
def get_my_replies(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    result = user_service.get_my_replies(current_user.user_id, page, per_page)
    return success(data=result, message="Replies retrieved")


@users_router.get("/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    user = user_service.get_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")
    return success(data=user, message="User retrieved")


# ---------------- Admin Endpoints ----------------


@users_router.get('/')
def get_users(
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
    current_admin: User = Depends(get_current_admin)
):
    users = user_service.get_all(search, page, per_page)
    return success(data=users, message="Users retrieved")


@users_router.patch("/{user_id}/block")
def block_user(user_id: int, current_admin: User = Depends(get_current_admin)):
    user_service.block_user(user_id, current_admin)
    return success(message="User blocked")


@users_router.patch("/{user_id}/unblock")
def unblock_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin)
):
    user_service.unblock_user(user_id, current_admin)
    return success(message="User unblocked")


@users_router.patch("/{user_id}/promote")
def promote_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin)
):
    user_service.promote_user(user_id, current_admin)
    return success(message="User promoted")


@users_router.patch("/{user_id}/demote")
def demote_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin)
):
    user_service.demote_user(user_id, current_admin)
    return success(message="User demoted")
