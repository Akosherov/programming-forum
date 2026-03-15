from fastapi import APIRouter, Depends
from common.auth import get_current_user
from data.models import ReplyUpdate, User
from services import reply_service
from common.response import success


replies_router = APIRouter(prefix='/replies', tags=['Replies'])


@replies_router.put('/{reply_id}')
def update_reply(
    reply_id: int,
    data: ReplyUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a reply's content. Only the author can update.
    """
    reply = reply_service.update_reply(
        reply_id,
        current_user.user_id,
        data.content
    )
    return success(data=reply, message='Reply updated')


@replies_router.delete('/{reply_id}')
def delete_reply(
    reply_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a reply. Only admin or author can delete.
    """
    reply_service.delete_reply(
        reply_id,
        current_user.user_id,
        current_user.role_id
    )
    return success(message='Reply deleted')


# -------------------- Best Reply Actions --------------------


@replies_router.patch('/{reply_id}/mark-best')
def mark_reply_as_best(
    reply_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Mark a reply as the best answer. Only topic author can mark.
    """
    reply = reply_service.mark_as_best_reply(reply_id, current_user.user_id)
    return success(data=reply, message='Reply marked as best answer')


@replies_router.patch('/{reply_id}/unmark-best')
def unmark_reply_as_best(
    reply_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Remove the best reply mark. Only topic author can unmark.
    """
    reply = reply_service.unmark_best_reply(reply_id, current_user.user_id)
    return success(data=reply, message='Best reply mark removed')
