from data.database import read_query, update_query, delete_query, insert_query
from common.exceptions import NotFoundError, ForbiddenError, UnauthorizedError
from data.models import ReactionSummary
from services.topic_service import _has_access_to_private_topic


# ---------------- Internal Helpers ----------------


def _get_reply(reply_id: int) -> dict:
    """
    Return basic Reply metadata needed for permission checks.
    Args:
        reply_id: ID of the reply.
    Returns:
        Dict with reply_id, author_id, topic_id.
    Raises:
        NotFoundError: If the Reply doesnt exist.
    """
    result = list(read_query(
        "SELECT reply_id, author_id, topic_id FROM replies WHERE reply_id = ?",
        (reply_id,))
    )
    if not result:
        raise NotFoundError("Reply not found")
    return {
        "reply_id": result[0][0],
        "author_id": result[0][1],
        "topic_id": result[0][2]
    }


def _get_topic_info(topic_id: int) -> tuple[bool, int]:
    """
    Return if a Topic is private and the Author ID.
    Args:
        topic_id: ID of the Topic.
    Returns:
        Tuple of is_private and author_id.
    Raises:
        NotFoundError if Topic not found.   
    """
    result = list(read_query(
        "SELECT is_private, author_id FROM topics WHERE topic_id = ?",
        (topic_id,),))
    if not result:
        raise NotFoundError("Topic not found")
    return bool(result[0][0]), result[0][1]


def _ensure_reaction_allowed(reply: dict, user_id: int) -> None:
    """
    Validate that a User is permitted to react to a reply.
    Args:
        reply: Reply metadata dict (from _get_reply).
    Raises:
        ForbiddenError if:
        - The User is the reply's Author.
        - The Reply is in a Private Topic and the User is neither
        the Topic author nor an accepted participant.
    """
    if reply['author_id'] == user_id:
        raise ForbiddenError("Cannot react to your own reply")

    # Private topic validation
    is_private, _ = _get_topic_info(reply["topic_id"])

    if is_private:
        if not _has_access_to_private_topic(reply["topic_id"], user_id):
            raise UnauthorizedError(
                "Not authorized to react in this private topic"
            )


# ---------------- Public API ----------------


def add_or_update_reaction(reply_id: int, user_id: int, is_like: bool) -> None:
    """
    Add or update a reaction. User can have only one reaction per reply.
    If reaction exists update it. If not create it.
    Args:
        reply_id: ID of the Reply to react to.
        user_id: ID of the Authenticated User.
        is_like: True for like, False for dislike.
    Raises:
        NotFoundError:  If the reply does not exist.
        ForbiddenError: If the user is not allowed to react.
    """
    reply = _get_reply(reply_id)
    _ensure_reaction_allowed(reply, user_id)

    # Check if reaction already exists
    existing = list(read_query(
        "SELECT 1 FROM reply_reactions WHERE reply_id = ? AND user_id = ?",
        (reply_id, user_id)
    ))

    if existing:
        # Update existing reaction
        update_query(
            """
            UPDATE reply_reactions SET is_like = ?
            WHERE reply_id = ? AND user_id = ?
            """,
            (is_like, reply_id, user_id)
        )
    else:
        # Create new reaction
        insert_query(
            """
            INSERT INTO reply_reactions (reply_id, user_id, is_like)
            VALUES (?, ?, ?)
            """,
            (reply_id, user_id, is_like)
        )


def remove_reaction(reply_id: int, user_id: int) -> None:
    """
    Remove Authenticated User's reaction from a reply.
    Args:
        reply_id: ID of the reply.
        user_id:  ID of the authenticated user.
    Raises:
        NotFoundError: If the reply does not exist.
    """
    _get_reply(reply_id)
    delete_query(
        "DELETE FROM reply_reactions WHERE reply_id = ? AND user_id = ?",
        (reply_id, user_id)
    )


def get_reaction_summary(reply_id: int, user_id: int | None = None) -> ReactionSummary:
    """
    Get reaction counts and current user's reaction if authenticated
    Args:
        reply_id: ID of the reply.
        user_id:  Optional ID of the authenticated user.
    Returns:
        Dict with keys: likes (int), dislikes (int), user_reaction (bool | None).
    Raises:
        NotFoundError: If the reply does not exist.
    """
    _get_reply(reply_id)

    result = list(read_query(
        """
        SELECT
            SUM(CASE WHEN is_like = 1 THEN 1 ELSE 0 END) AS likes,
            SUM(CASE WHEN is_like = 0 THEN 1 ELSE 0 END) AS dislikes
        FROM reply_reactions
        WHERE reply_id = ?
        """, (reply_id,)
    ))
    likes = result[0][0] or 0
    dislikes = result[0][1] or 0

    # Get user's reaction if authenticated
    user_reaction = None
    if user_id is not None:
        user_result = list(read_query(
            """
            SELECT is_like
            FROM reply_reactions
            WHERE reply_id = ? AND user_id = ?
            """,
            (reply_id, user_id)
        ))
        if user_result:
            user_reaction = bool(user_result[0][0])

    return ReactionSummary(
        likes=likes,
        dislikes=dislikes,
        user_reaction=user_reaction
    )
