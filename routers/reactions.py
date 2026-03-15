from fastapi import APIRouter, Depends
from services import reaction_service
from data.models import User
from common.auth import get_current_user, get_optional_user
from common.response import success


reactions_router = APIRouter(prefix="/replies", tags=['Reactions'])


@reactions_router.post('/{reply_id}/like')
def like_reply(
    reply_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Like a reply or change dislike to like
    """
    reaction_service.add_or_update_reaction(
        reply_id, current_user.user_id, True
        )
    return success(message="Reply liked")


@reactions_router.post('/{reply_id}/dislike')
def dislike_reply(
    reply_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Dislike a reply or change to dislike
    """
    reaction_service.add_or_update_reaction(
        reply_id, current_user.user_id, False
    )
    return success(message="Reply disliked")


@reactions_router.delete('/{reply_id}/reactions')
def delete_reaction(
    reply_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Delete reaction from a reply
    """
    reaction_service.remove_reaction(reply_id, current_user.user_id)
    return success(message="Reaction removed")


@reactions_router.get('/{reply_id}/reactions')
async def get_reactions(
    reply_id: int,
    current_user: User | None = Depends(get_optional_user)
):
    """
    Get reactions summary for a reply (public endpoint)
    """
    user_id = current_user.user_id if current_user else None
    summary = reaction_service.get_reaction_summary(reply_id, user_id)
    return success(data=summary, message="Reactions retrieved")
