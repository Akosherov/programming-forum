from fastapi import APIRouter, Depends
from services import participant_service
from data.models import User
from common.auth import get_current_user
from common.response import success


participants_router = APIRouter(prefix="/topics", tags=['Participants'])


@participants_router.get('/{topic_id}/participants')
def get_participants(
    topic_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    List all participants of a private topic.
    Requires authentication, the caller must
    be a participant, the topic author, or admin.
    """
    participants = participant_service.get_participants(topic_id, current_user)
    return success(data=participants, message="Participants retrieved")


@participants_router.delete('/{topic_id}/participants/{user_id}')
def remove_participant(
    topic_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Remove a participant from a private topic (author & admin only).
    """
    participant_service.remove_participant(topic_id, user_id, current_user)
    return success(message="Participant removed")


@participants_router.post('/{topic_id}/leave')
def leave_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Leave a private topic, participants only(not author)
    """
    participant_service.leave_topic(topic_id, current_user)
    return success(message="You left the topic")
