from data.models import UserPublic, User, UserRole
from data.database import read_query, delete_query
from common.exceptions import NotFoundError, ForbiddenError, UnauthorizedError


def get_participants(topic_id: int, current_user: User) -> list[UserPublic]:
    """
    Return all accepted participants of a private topic.
    The topic author is not included, they have implicit access..
    Args:
        topic_id: ID of the private topic
    Returns:
        List of UserPublic for each participant.
    Raises:
        NotFoundError: If the Topic doesnt exist.
        ForbiddenError: If the caller is not authorized to view participants.
    """
    topic = read_query(
        "SELECT author_id FROM topics WHERE topic_id = ?",
        (topic_id,)
    )
    if not topic:
        raise NotFoundError("Topic not found")

    author_id = topic[0][0]

    is_author = current_user.user_id == author_id
    is_admin = current_user.role_id == UserRole.ADMIN

    if not is_author and not is_admin:
        is_participant = bool(read_query(
            "SELECT 1 FROM topic_participants WHERE topic_id = ? AND user_id = ?",
            (topic_id, current_user.user_id)
        ))
        if not is_participant:
            raise UnauthorizedError("Not authorized to view participants of this topic")

    sql = """
        SELECT u.user_id, u.first_name, u.last_name, u.username, u.is_deleted
        FROM topic_participants tp
        JOIN users u ON tp.user_id = u.user_id
        WHERE tp.topic_id = ?
        ORDER BY u.username
    """
    results = read_query(sql, (topic_id,))
    return [UserPublic(
        user_id=row[0],
        first_name=row[1],
        last_name=row[2],
        username=row[3],
        is_deleted=bool(row[4])
    ) for row in results]


def remove_participant(topic_id: int, user_id: int, current_user: User) -> bool:
    """
    Remove participant from a private topic. Their content is preserved
    unless explicitly deleted via reply_service.
    Only topic author or admin can remove a participant.
    The Topic author cannot be removed.
    Args:
        topic_id: ID of the Topic.
        user_id: ID of the User to remove.
        current_user: the authenticated caller.
    Returns:
        True if the participant was removed.
    Raises:
        NotFoundError: If the Topic or Participant is not found
        ForbiddenError: If the caller lacks permission or tries
                        to remove the Author
    """
    result = read_query(
        "SELECT author_id FROM topics WHERE topic_id = ?", (topic_id,))
    if not result:
        raise NotFoundError("Topic not found")

    author_id = result[0][0]

    if current_user.user_id != author_id and current_user.role_id != UserRole.ADMIN:
        raise UnauthorizedError("Only topic author or admin can remove participants")

    if user_id == author_id:
        raise ForbiddenError("Cannot remove topic author")

    if not read_query(
        "SELECT 1 FROM topic_participants WHERE topic_id = ? AND user_id = ?",
        (topic_id, user_id)
    ):
        raise NotFoundError("User is not a participant")

    delete_query(
        "DELETE FROM topic_participants WHERE topic_id = ? AND user_id = ?",
        (topic_id, user_id)
    )
    return True


def leave_topic(topic_id: int, current_user: User) -> bool:
    """
    Leave a private topic.
    Cannot leave if you are the author.
    Args:
        topic_id: ID of the Topic to leave.
        current_user: The authenticated caller.
    Returns:
        True if the User successfully left.
    Raises:
        NotFoundError: If the Topic is not found,
                        or the User is not a participant.
        ForbiddenError: If the caller is the Topic author.
    """
    result = read_query(
        "SELECT author_id FROM topics WHERE topic_id = ?", (topic_id,))
    if not result:
        raise NotFoundError("Topic not found")

    if result[0][0] == current_user.user_id:
        raise ForbiddenError("Topic author cannot leave their own topic")

    if not read_query(
        "SELECT 1 FROM topic_participants WHERE topic_id = ? AND user_id = ?",
        (topic_id, current_user.user_id)
    ):
        raise NotFoundError("You are not a participant of this topic")

    delete_query(
        "DELETE FROM topic_participants WHERE topic_id = ? AND user_id = ?",
        (topic_id, current_user.user_id)
    )
    return True
