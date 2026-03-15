from common.exceptions import NotFoundError, ForbiddenError, UnauthorizedError
from typing import Optional
from data.database import read_query, insert_query, update_query, delete_query
from data.models import ReplyResponse, ReplyCreate, UserRole, ReplyList
from services.topic_service import _has_access_to_private_topic


def _row_to_reply(row) -> ReplyResponse:
    """
    Convert database row to ReplyResponse model.
    Row must include my_reaction as column 10.
    """
    id, topic_id, author_id, content, like_count, dislike_count, is_best, created_at, username, my_reaction = row

    if my_reaction == 1:
        reaction = "like"
    elif my_reaction == 0:
        reaction = "dislike"
    else:
        reaction = None

    return ReplyResponse(
        id=id,
        content=content,
        author_id=author_id,
        author_username=username,
        likes=like_count,
        dislikes=dislike_count,
        created_at=created_at,
        is_best=bool(is_best),
        current_user_reaction=reaction
    )


def create_reply(reply_data: ReplyCreate, author_id: int) -> ReplyResponse:
    # Check if user is blocked
    user = read_query(
        'SELECT is_blocked FROM users WHERE user_id = ?',
        (author_id,)
    )

    if not user:
        raise NotFoundError('User not found!')

    if user[0][0]:  # is_blocked
        raise ForbiddenError('Blocked users cannot create replies!')

    topic = read_query(
        """
        SELECT topic_id, is_locked, is_private
        FROM topics
        WHERE topic_id = ?
        """,
        (reply_data.topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')

    topic_id, is_locked, is_private = topic[0]

    # Check locked
    if is_locked:
        raise ForbiddenError("Topic is locked")

    # Check if private
    if is_private:
        if not _has_access_to_private_topic(topic_id, author_id):
            raise UnauthorizedError(
                "You are not allowed to reply to this topic."
            )

    # Insert reply
    sql = '''
        INSERT INTO replies (topic_id, author_id, reply_content)
        VALUES (?, ?, ?)
    '''

    reply_id = insert_query(sql, (topic_id, author_id, reply_data.content))

    return get_reply_by_id(reply_id, author_id)


def get_reply_by_id(reply_id: int, current_user_id: Optional[int] = None) -> ReplyResponse:

    row = read_query(
        '''
        SELECT
        r.reply_id,
        r.topic_id,
        r.author_id,
        r.reply_content,
        COALESCE(SUM(CASE WHEN rr.is_like = 1 THEN 1 ELSE 0 END), 0) as like_count,
        COALESCE(SUM(CASE WHEN rr.is_like = 0 THEN 1 ELSE 0 END), 0) as dislike_count,
        r.is_best,
        r.created_at,
        u.username,
        (
            SELECT is_like FROM reply_reactions
            WHERE reply_id = r.reply_id AND user_id = ?
        ) AS my_reaction
        FROM replies r
        JOIN users u ON r.author_id = u.user_id
        LEFT JOIN reply_reactions rr ON r.reply_id = rr.reply_id
        WHERE r.reply_id = ?
        GROUP BY r.reply_id, r.topic_id, r.author_id, r.reply_content, r.is_best, r.created_at, u.username
        ''',
        (current_user_id, reply_id,)
    )

    if not row:
        raise NotFoundError('Reply not found!')

    return _row_to_reply(row[0])


def get_replies(topic_id: int, current_user_id: Optional[int] = None,
                page: int = 1, per_page: int = 20) -> ReplyList:

    # Check if topic exists
    topic = read_query(
        'SELECT topic_id, is_private FROM topics WHERE topic_id = ?',
        (topic_id,)
    )
    if not topic:
        raise NotFoundError('Topic not found!')

    _, is_private = topic[0]
    if is_private:
        if not current_user_id:
            raise UnauthorizedError(
                "Authentication required to view replies of a private topic"
            )
        if not _has_access_to_private_topic(topic_id, current_user_id):
            raise UnauthorizedError(
                "You do not have access to this private topic"
            )

    count_row = read_query(
        'SELECT COUNT(*) FROM replies WHERE topic_id = ?', (topic_id,)
    )
    total = count_row[0][0]

    offset = (page - 1) * per_page
    rows = read_query(
            '''
            SELECT
            r.reply_id,
            r.topic_id,
            r.author_id,
            r.reply_content,
            COALESCE(SUM(CASE WHEN rr.is_like = 1 THEN 1 ELSE 0 END), 0) as like_count,
            COALESCE(SUM(CASE WHEN rr.is_like = 0 THEN 1 ELSE 0 END), 0) as dislike_count,
            r.is_best,
            r.created_at,
            u.username,
            (
                SELECT is_like FROM reply_reactions
                WHERE reply_id = r.reply_id AND user_id = ?
            ) AS my_reaction
            FROM replies r
            JOIN users u ON r.author_id = u.user_id
            LEFT JOIN reply_reactions rr ON r.reply_id = rr.reply_id
            WHERE r.topic_id = ?
            GROUP BY r.reply_id, r.topic_id, r.author_id, r.reply_content, r.is_best, r.created_at, u.username
            ORDER BY r.is_best DESC, r.created_at
            LIMIT ? OFFSET ?
            ''',
            (current_user_id, topic_id, per_page, offset))

    replies = [_row_to_reply(row) for row in rows]

    return ReplyList(
        replies=replies,
        total=total,
        page=page,
        per_page=per_page
    )


def update_reply(reply_id: int, user_id: int, new_content: str) -> ReplyResponse:
    # Check to see if reply exists and the author is the same
    row = read_query(
        'SELECT author_id FROM replies WHERE reply_id = ?', (reply_id,)
    )

    if not row:
        raise NotFoundError('Reply not found!')
    if row[0][0] != user_id:
        raise UnauthorizedError('Not your reply!')

    update_query(
        'UPDATE replies SET reply_content = ? WHERE reply_id = ?',
        (new_content, reply_id)
    )

    return get_reply_by_id(reply_id, user_id)


def delete_reply(reply_id, user_id: int, user_role_id: int) -> None:
    # Delete a reply. Author or admin can delete.

    row = read_query(
        'SELECT author_id, topic_id FROM replies WHERE reply_id = ?',
        (reply_id,)
    )

    if not row:
        raise NotFoundError('Reply not found!')

    author_id, topic_id = row[0]

    if author_id != user_id and user_role_id != UserRole.ADMIN:
        raise UnauthorizedError(
            'Only reply author or admin can delete this reply!'
        )

    delete_query('DELETE from replies WHERE reply_id = ?', (reply_id, ))


# -------------------- Best Reply Actions --------------------


def mark_as_best_reply(reply_id: int, user_id: int) -> ReplyResponse:
    '''
    Mark a reply as best answer
    Only the topic author can mark a reply as best
    Only one reply per topic can be marked as best
    '''

    reply_row = read_query(
        'SELECT topic_id, author_id FROM replies WHERE reply_id = ?',
        (reply_id,)
    )

    if not reply_row:
        raise NotFoundError('Reply not found!')

    topic_id, reply_author_id = reply_row[0]

    # Get topic author
    topic_row = read_query(
        'SELECT author_id FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic_row:
        raise NotFoundError('Topic not found!')

    topic_author_id = topic_row[0][0]

    if user_id != topic_author_id:
        raise UnauthorizedError('Only topic authors can mark best reply!')

    # Prevent marking own reply as best
    if reply_author_id == user_id:
        raise ForbiddenError('Cannot mark your own reply as best!')

    # Unmark any existing best reply for this topic
    update_query(
        'UPDATE replies SET is_best = 0 WHERE topic_id = ?',
        (topic_id,)
    )

    # Mark new best reply
    update_query(
        'UPDATE replies SET is_best = 1 WHERE reply_id = ?',
        (reply_id,)
    )

    return get_reply_by_id(reply_id, user_id)


def unmark_best_reply(reply_id: int, user_id: int) -> ReplyResponse:
    '''
    Remove the best reply
    Only the topic author can unmark best reply
    '''

    reply_row = read_query(
        'SELECT topic_id, is_best FROM replies WHERE reply_id = ?',
        (reply_id,)
    )

    if not reply_row:
        raise NotFoundError('Reply not found!')

    topic_id, is_best = reply_row[0]

    # Check if reply is marked as best

    if not is_best:
        raise ForbiddenError('Reply is not marked as best!')

    topic_row = read_query(
        'SELECT author_id FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic_row:
        raise NotFoundError('Topic not found!')

    topic_author_id = topic_row[0][0]

    # Check if current user is the topic author
    if user_id != topic_author_id:
        raise UnauthorizedError('Only the topic author can unmark the best reply!')

    update_query(
        'UPDATE replies SET is_best = 0 WHERE reply_id= ? ',
        (reply_id,)
    )

    return get_reply_by_id(reply_id, user_id)
