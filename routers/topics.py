from fastapi import APIRouter, Depends, Query
from common.auth import get_current_user, get_current_admin, get_optional_user
from data.models import TopicCreate, TopicUpdate, User, ReplyCreate
from services import topic_service, reply_service
from common.response import success


topics_router = APIRouter(prefix='/topics', tags=['Topics'])


# -------------------- Create Topics --------------------


@topics_router.post('/')
def create_topic(
    data: TopicCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new topic (public or private)
    Only authenticated users can do this action
    """
    topic = topic_service.create_topic(data, current_user.user_id)
    return success(data=topic, message='Topic created', status_code=201)


# -------------------- Create Topic Replies --------------------


@topics_router.post('/{topic_id}/replies')
def create_reply(
    topic_id: int,
    data: ReplyCreate,
    current_user: User = Depends(get_current_user)
):
    '''
    Create a new reply to a topic.
    Blocked users and locked topics are restricted.
    '''
    reply_data = ReplyCreate(topic_id=topic_id, content=data.content)
    reply = reply_service.create_reply(reply_data, current_user.user_id)
    return success(data=reply, message='Reply created', status_code=201)


# -------------------- Get Topics --------------------


@topics_router.get('/')
def get_topics(
    search: str | None = Query(None, description='Search in title and content'),
    author_id: int | None = Query(None, description='Filter by author ID'),
    is_private: bool | None = Query(None, description='Filter by private/public'),
    is_locked: bool | None = Query(None, description='Filter by locked status'),
    sort_by: str = Query('created_at', description='Sort by: created_at, reply_count, title'),
    sort_order: str = Query('asc', description='Sort order: asc or desc'),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user)
):
    """
    Get all topics with optional filters.
    Public topics visible to all.
    Private topics only visible to participants.
    """
    current_user_id = current_user.user_id if current_user else None
    result = topic_service.get_topics(
        current_user_id=current_user_id,
        search=search,
        author_id=author_id,
        is_private=is_private,
        is_locked=is_locked,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
        )

    return success(data=result, message='Topics retrieved')


# -------------------- Get Topic --------------------


@topics_router.get('/{topic_id}')
def get_topic(
    topic_id: int,
    current_user: User | None = Depends(get_optional_user)
):
    """
    Get a single topic by ID
    Private topics require authentication and access
    """
    current_user_id = current_user.user_id if current_user else None
    topic = topic_service.get_topic_by_id(topic_id, current_user_id)

    return success(data=topic, message='Topic retrieved')


# -------------------- Get Topic Replies --------------------


@topics_router.get('/{topic_id}/replies')
def get_replies(
    topic_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user)
):
    '''
    Get all replies for a topic.
    Best reply shows first, then sorted by creation date.
    '''

    current_user_id = current_user.user_id if current_user else None
    result = reply_service.get_replies(
        topic_id,
        current_user_id,
        page,
        per_page
    )
    return success(data=result, message='Replies retrieved')


# -------------------- Update Topics --------------------


@topics_router.patch('/{topic_id}')
def update_topic(
    topic_id: int,
    data: TopicUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a topic's title or content
    Only the topic author can update
    Cannot update locked topics
    """
    topic = topic_service.update_topic(
        topic_id,
        data,
        current_user.user_id,
        current_user.role_id
    )
    return success(data=topic, message='Topic updated!')


# -------------------- Delete Topics --------------------


@topics_router.delete('/{topic_id}')
def delete_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a topic.
    Only the author or an admin can delete the topic.
    """
    topic_service.delete_topic(
        topic_id,
        current_user.user_id,
        current_user.role_id
    )
    return success(message='Topic deleted!')


# -------------------- Admin Actions --------------------


@topics_router.patch('/{topic_id}/lock')
def lock_topic(
    topic_id: int,
    current_admin: User = Depends(get_current_admin)
):
    """
    Lock a topic (prevents new replies)
    Only admin can do this action
    """
    topic = topic_service.lock_topic(topic_id, current_admin.user_id)
    return success(data=topic, message='Topic locked!')


@topics_router.patch('/{topic_id}/unlock')
def unlock_topic(
    topic_id: int,
    current_admin: User = Depends(get_current_admin)
):
    """
    Unlock a topic (allows new replies)
    Only admin can do this action
    """
    topic = topic_service.unlock_topic(topic_id, current_admin.user_id)
    return success(data=topic, message='Topic unlocked!')
