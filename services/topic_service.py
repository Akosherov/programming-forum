from common.exceptions import NotFoundError, ForbiddenError, UnauthorizedError
from typing import Optional
from data.database import read_query, insert_query, update_query, delete_query
from data.models import TopicCreate, TopicUpdate, TopicResponse, TopicListItem
from data.models import TopicList, UserRole


def _row_to_topic(row) -> TopicResponse:

    """Convert database row to TopicResponse model."""

    (topic_id, title, content, is_locked, is_private,
     created_at, author_id, author_username, reply_count) = row

    return TopicResponse(
        topic_id=topic_id,
        title=title,
        content=content,
        is_locked=bool(is_locked),
        is_private=bool(is_private),
        created_at=created_at,
        author_id=author_id,
        author_username=author_username,
        reply_count=reply_count or 0
    )


def _row_to_topic_list_item(row) -> TopicListItem:

    """Convert database row to TopicListItem model."""

    (topic_id, title, is_locked, is_private,
     created_at, author_username, reply_count) = row

    return TopicListItem(
        topic_id=topic_id,
        title=title,
        is_locked=bool(is_locked),
        is_private=bool(is_private),
        created_at=created_at,
        author_username=author_username,
        reply_count=reply_count or 0
    )


def create_topic(topic_data: TopicCreate, author_id: int) -> TopicResponse:

    user = read_query(
        'SELECT is_blocked FROM users WHERE user_id = ?',
        (author_id,)
    )

    if not user:
        raise NotFoundError('User not found!')

    if user[0][0]:  # is_blocked
        raise ForbiddenError('Blocked users cannot create topics!')

    sql = '''
        INSERT INTO topics (title, content, is_private, author_id)
        VALUES (?, ?, ?, ?)
        '''

    topic_id = insert_query(
        sql,
        (topic_data.title, topic_data.content,
            1 if topic_data.is_private else 0, author_id)
    )

    if topic_data.is_private:
        insert_query(
            'INSERT INTO topic_participants (topic_id, user_id) VALUES (?, ?)',
            (topic_id, author_id)
        )

    return get_topic_by_id(topic_id, author_id)


def get_topic_by_id(
        topic_id: int,
        current_user_id: Optional[int] = None
) -> TopicResponse:

    # Get a single topic by ID

    row = read_query(
        '''
        SELECT
            t.topic_id,
            t.title,
            t.content,
            t.is_locked,
            t.is_private,
            t.created_at,
            t.author_id,
            u.username as author_username,
            COALESCE(
                (SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id),
                0
            ) as reply_count
        FROM topics t
        JOIN users u ON t.author_id = u.user_id
        WHERE t.topic_id = ?
        ''',
        (topic_id,)
    )

    if not row:
        raise NotFoundError('Topic not found!')

    topic = _row_to_topic(row[0])

    # Check access for private topics
    if topic.is_private and current_user_id:
        if not _has_access_to_private_topic(topic_id, current_user_id):
            raise UnauthorizedError('You do not have access to this private topic!')

    elif topic.is_private and not current_user_id:
        raise UnauthorizedError('Authentication required to view private topics!')

    return topic


def get_topics(
        current_user_id: Optional[int] = None,
        search: Optional[str] = None,
        author_id: Optional[int] = None,
        is_private: Optional[bool] = None,
        is_locked: Optional[bool] = None,
        sort_by: Optional[str] = 'created_at',  # ← NEW: Sort field
        sort_order: Optional[str] = 'desc',      # ← NEW: Sort direction
        page: int = 1,
        per_page: int = 20,
) -> TopicList:

    '''
    Get all topics with optional filters
    Private topics only shown if user has access
    '''

    where_conditions = []
    params = []

    # Filter search in title or content
    if search:
        where_conditions.append('(t.title LIKE ? OR t.content LIKE ?)')
        search_param = f'%{search}%'
        params.extend([search_param, search_param])

    # Filter by author
    if author_id is not None:
        where_conditions.append('t.author_id = ?')
        params.append(author_id)

    if is_private is not None:
        where_conditions.append('t.is_private = ?')
        params.append(1 if is_private else 0)

    if is_locked is not None:
        where_conditions.append('t.is_locked = ?')
        params.append(1 if is_locked else 0)

    # Access control for private topics
    if current_user_id:
        where_conditions.append(
            '''(
            t.is_private = 0
            OR t.author_id = ?
            OR EXISTS (
                SELECT 1 FROM topic_participants tp
                WHERE tp.topic_id = t.topic_id AND tp.user_id = ?
                )
            )'''
        )
        params.extend([current_user_id, current_user_id])

    else:
        where_conditions.append('t.is_private = 0')

    where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''

    # ==================== NEW: Build ORDER BY clause ====================

    # Validate sort_by field (prevent SQL injection)
    valid_sort_fields = {
        'created_at': 't.created_at',
        'reply_count': 'reply_count',
        'title': 't.title'
    }

    sort_column = valid_sort_fields.get(sort_by, 't.created_at')

    # Validate sort_order (prevent SQL injection)
    sort_direction = 'DESC' if sort_order and sort_order.lower() == 'desc' else 'ASC'

    order_by_clause = f'ORDER BY {sort_column} {sort_direction}'

    # =====================================================================

    # Get total count
    count_query = f'''
        SELECT COUNT(*)
        FROM topics t
        {where_clause}
    '''
    total = read_query(count_query, tuple(params))[0][0]

    # Get paginated results
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    rows = read_query(
        f'''
        SELECT
            t.topic_id,
            t.title,
            t.is_locked,
            t.is_private,
            t.created_at,
            u.username as author_username,
            COALESCE(
                (SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id),
                0
            ) as reply_count
        FROM topics t
        JOIN users u ON t.author_id = u.user_id
        {where_clause}
        {order_by_clause}
        LIMIT ? OFFSET ?
        ''',
        tuple(params)
    )

    topics = [_row_to_topic_list_item(row) for row in rows]

    return TopicList(
        topics=topics,
        total=total,
        page=page,
        per_page=per_page
    )


def update_topic(
        topic_id: int,
        topic_update: TopicUpdate,
        current_user_id: int,
        current_user_role_id: int
) -> TopicResponse:

    topic = read_query(
        'SELECT author_id, is_locked FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')

    author_id, is_locked = topic[0]

    is_author = author_id == current_user_id
    is_admin = current_user_role_id == UserRole.ADMIN

    if not is_author and not is_admin:
        raise UnauthorizedError('Only topic author or admin can update the topic!')

    if is_locked and not is_admin:
        raise ForbiddenError('Cannot update locked topic')

    fields = []
    params = []

    if topic_update.title is not None:
        fields.append('title = ?')
        params.append(topic_update.title)

    if topic_update.content is not None:
        fields.append('content = ?')
        params.append(topic_update.content)

    if topic_update.is_private is not None:
        fields.append('is_private = ?')
        params.append(1 if topic_update.is_private else 0)

    if not fields:
        # No update provided just return current topic
        return get_topic_by_id(topic_id, current_user_id)

    params.append(topic_id)

    sql = f'''
        UPDATE topics
        SET {', '.join(fields)}
        WHERE topic_id = ?
    '''

    update_query(sql, tuple(params))

    return get_topic_by_id(topic_id, current_user_id)


def delete_topic(
        topic_id: int,
        current_user_id: int,
        current_user_role_id: int
) -> None:

    topic = read_query(
        'SELECT author_id FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')

    is_author = topic[0][0] == current_user_id
    is_admin = current_user_role_id == UserRole.ADMIN

    if not is_author and not is_admin:
        raise UnauthorizedError("Only topic author or admin can delete the topic")

    delete_query('DELETE FROM topics WHERE topic_id = ?', (topic_id,))


def _has_access_to_private_topic(topic_id: int, user_id: int) -> bool:
    # Check if user has access to private topic

    admin_check = read_query(
        "SELECT 1 FROM users WHERE user_id = ? AND role_id = ?",
        (user_id, UserRole.ADMIN)
    )
    if admin_check:
        return True

    # Check if user is author
    author_check = read_query(
        'SELECT 1 FROM topics WHERE topic_id = ? AND author_id = ?',
        (topic_id, user_id)
    )

    if author_check:
        return True

    # Check if user is a participant
    participant_check = read_query(
        'SELECT 1 FROM topic_participants WHERE topic_id = ? AND user_id = ?',
        (topic_id, user_id)
    )

    if participant_check:
        return True


# -------------------- Admin Actions --------------------


def lock_topic(topic_id: int, admin_user_id: int) -> TopicResponse:
    # Lock a topic (admin only)

    topic = read_query(
        'SELECT topic_id FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')

    update_query(
        'UPDATE topics SET is_locked = 1 WHERE topic_id = ?',
        (topic_id,)
    )

    return get_topic_by_id(topic_id, admin_user_id)


def unlock_topic(topic_id: int, admin_user_id: int) -> TopicResponse:
    # Unlock a topic (admin only)

    topic = read_query(
        'SELECT topic_id FROM topics WHERE topic_id = ?',
        (topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')

    update_query(
        'UPDATE topics SET is_locked = 0 WHERE topic_id = ?',
        (topic_id,)
    )

    return get_topic_by_id(topic_id, admin_user_id)
