from data.database import read_query, insert_query, update_query
from data.models import User, UserPublic, UserCreate, UserUpdate
from data.models import UserDelete, UserRole, UserListResponse
from data.models import TopicList, TopicListItem, ReplyResponse, ReplyList
from common.security import hash_password, verify_password
from common.exceptions import ForbiddenError, UnauthorizedError, NotFoundError


# ---------------- Internal Helpers ----------------


def _get_user_by_username_internal(username: str) -> User | None:
    """
    Return full User object by username including hashed password.
    Returns None if not found or soft deleted.
    Used internally for authentication
    """
    result = list(
        read_query("SELECT * FROM users WHERE username = ?", (username,))
    )
    if not result:
        return None
    return User.from_query_result(*result[0])


def _get_by_id_internal(user_id: int) -> User | None:
    """
    Return a full User object by ID, including hashed password.
    Returns None if not found. Includes soft_deleted users (so we can
    still operate on them internally)
    """
    result = list(
        read_query("SELECT * FROM users WHERE user_id = ?", (user_id,))
    )
    if not result:
        return None
    return User.from_query_result(*result[0])


# ---------------- Public Services ----------------


def get_all(
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        ) -> UserListResponse:
    """
    Return a paginated list of active users.
    Optionally filter by a search term:
    username, email, first or last name.
    Args:
        search: Optional substring to match against user fields.
        page: Page number
        per_page: Number of results per page.
    Returns:
        List of UserPublic objects with paginated data.
    """
    base_where = "WHERE is_deleted = 0"
    params: list = []

    if search:
        base_where += """
            AND (username LIKE ?
                OR email LIKE ?
                OR first_name LIKE ?
                OR last_name LIKE ?)
        """

        param = f"%{search}%"
        params.extend([param, param, param, param])

    count_sql = f"SELECT COUNT(*) FROM users {base_where}"
    total = read_query(count_sql, tuple(params))[0][0]

    offset = (page - 1) * per_page
    data_sql = f"""
        SELECT *
        FROM users
        {base_where}
        ORDER BY username
        LIMIT ? OFFSET ?
    """

    rows = read_query(data_sql, (*params, per_page, offset))

    users = [
        UserPublic.from_user(User.from_query_result(*row)) for row in rows
    ]
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page
    )


def get_by_id(user_id: int) -> UserPublic | None:
    """
    Return public user data by ID.
    Returns None if the user doesn't exist.
    Soft deleted users are returned but flagged.
    Args:
        user_id: The user id we are looking for.
    Returns:
        The PublicUser object.
    """
    user = _get_by_id_internal(user_id)
    if not user:
        return None
    return UserPublic.from_user(user)


def create_user(user_data: UserCreate) -> User:
    """
    Register a new user with a hashed password.
    Raises ForbiddenError if Username or Email is already taken.
    Args:
        user_data: Registration payload.
    Returns:
        The newly created User object.
    """
    if username_or_email_exists(user_data.username, user_data.email):
        raise ForbiddenError("Username or Email already exists")

    hashed_password = hash_password(user_data.password)
    sql = """
        INSERT INTO users (
                first_name,
                last_name,
                email,
                username,
                password,
                is_blocked,
                is_deleted,
                role_id)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?)
    """
    user_id = insert_query(sql, (
        user_data.first_name,
        user_data.last_name,
        user_data.email,
        user_data.username,
        hashed_password,
        UserRole.USER
    ))

    return User.from_query_result(
        user_id,
        user_data.first_name,
        user_data.last_name,
        user_data.email,
        user_data.username,
        hashed_password,
        False,
        False,
        UserRole.USER
    )


def username_or_email_exists(username: str, email: str) -> bool:
    """
    Check if Username or Email is already registered.
    Args:
        username: Username to check.
        email: Email to check
    Returns:
      True if either already exists in the DB
    """
    sql = """
        SELECT 1 FROM users
        WHERE (username = ? OR email = ?) AND is_deleted = 0
        LIMIT 1
    """
    result = read_query(sql, (username, email))
    return len(result) > 0


# ---------------- Authenticated User Endpoints ----------------


def update_user(
        user_id: int,
        user_update: UserUpdate,
        current_user: User
) -> User | None:
    """
    Updates a user. Requires the current password to proceed.
    Unless it is the admin updating someone else.
    Fields that are None in user_update are left unchanged.
    Args:
        user_id: ID of the user to update.
        user_update: Partial update payload.
        current_user: The authenticated user.
    Returns:
        Updated User object, or None if User doesn't exist.
    Raises:
        ForbiddenError: If email is taken.
        UnauthorizedError: If bad credentials.
    """
    existing = _get_by_id_internal(user_id)
    if not existing:
        return None

    # Admins updating other users skip password verification.
    # Regular users must always provide their password
    if current_user.role_id != UserRole.ADMIN:
        if not user_update.current_password:
            raise UnauthorizedError("Password required")
        if not verify_password(user_update.current_password, existing.password):
            raise UnauthorizedError("Incorrect credentials")

    fields = []
    params = []

    if user_update.first_name is not None:
        fields.append("first_name = ?")
        params.append(user_update.first_name)

    if user_update.last_name is not None:
        fields.append("last_name = ?")
        params.append(user_update.last_name)

    if user_update.email is not None:

        # Check if email already exists
        sql = "SELECT 1 FROM users WHERE email = ? AND user_id != ?"
        if read_query(sql, (user_update.email, user_id)):
            raise ForbiddenError("Email already in use")
        fields.append("email = ?")
        params.append(user_update.email)

    if user_update.password is not None:
        hashed_password = hash_password(user_update.password)
        fields.append("password = ?")
        params.append(hashed_password)

    if not fields:
        return existing

    sql = f"""
        UPDATE users
        SET {", ".join(fields)}
        WHERE user_id = ?
    """

    params.append(user_id)
    update_query(sql, tuple(params))

    return _get_by_id_internal(user_id)


def delete_user(user_id: int, data: UserDelete, current_user: User) -> bool:
    """
    Soft delete a user. The user's account is marked as deleted
    but all their content is preserved. The account can no longer
    be accessed after this operation.
        - Self deletion required password confirmation
        - Admins can delete any user without a password
        - Users cannot delete other users
    Args:
        user_id: ID of the user to delete.
        data: Deletion payload.
        current_user: The authenticated caller.
    Returns:
    True if the User was deleted, False if not found.
    Raises:
        ForbiddenError: If caller is forbidden.
        UnauthorizedError: If bad credentials.
    """
    user = _get_by_id_internal(user_id)
    if not user or user.is_deleted:
        return False
    # If not self and not admin deleting another user is not allowed
    if current_user.user_id != user_id and current_user.role_id != UserRole.ADMIN:
        raise ForbiddenError("Forbidden")
    # If self require password confirmation
    if current_user.user_id == user_id:
        if not verify_password(data.password, user.password):
            raise UnauthorizedError("Invalid credentials")

    update_query(
        "UPDATE users SET is_deleted = 1 WHERE user_id = ?",
        (user_id,)
    )
    return True


def get_my_topics(
        user_id: int,
        page: int = 1,
        per_page: int = 20
) -> TopicList:
    """
    Return a paginated list of all topics created by the user.
    Includes their private topics.
    Args:
        user_id: ID of the authenticated user.
        page: Page number.
        per_page: Number of results per page.
    Returns:
        Dict with keys: topics, total, page, per_page.
    """
    count_sql = "SELECT COUNT(*) FROM topics WHERE author_id = ?"
    total = read_query(count_sql, (user_id,))[0][0]

    offset = (page - 1) * per_page
    rows = read_query(
        """
        SELECT
            t.topic_id,
            t.title,
            t.is_locked,
            t.is_private,
            t.created_at,
            u.username AS author_username,
            COALESCE(
                (SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id),
                0
            ) AS reply_count
        FROM topics t
        JOIN users u ON t.author_id = u.user_id
        WHERE t.author_id = ?
        ORDER BY t.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, per_page, offset)
    )

    topics = [
        TopicListItem(
            topic_id=row[0],
            title=row[1],
            is_locked=bool(row[2]),
            is_private=bool(row[3]),
            created_at=row[4],
            author_username=row[5],
            reply_count=row[6] or 0
        )
        for row in rows
    ]

    return TopicList(
        topics=topics,
        total=total,
        page=page,
        per_page=per_page
    )


def get_my_replies(user_id: int, page: int = 1, per_page: int = 20) -> ReplyList:
    """
    Return a paginated list of all replies created by the user.
    Includes like/dislike counts and the user's own reaction on each reply.
    Args:
        user_id: ID of the authenticated user.
        page: Page number.
        per_page: Number of results per page.
    Returns:
        Dict with keys: replies, total, page, per_page.
    """
    count_sql = "SELECT COUNT(*) FROM replies WHERE author_id = ?"
    total = read_query(count_sql, (user_id,))[0][0]

    offset = (page - 1) * per_page
    rows = read_query(
        """
        SELECT
            r.reply_id,
            r.author_id,    
            r.reply_content,
            u.username AS author_username,
            COALESCE(SUM(CASE WHEN rr.is_like = 1 THEN 1 ELSE 0 END), 0) AS likes,
            COALESCE(SUM(CASE WHEN rr.is_like = 0 THEN 1 ELSE 0 END), 0) AS dislikes,
            r.created_at,
            r.is_best,
            (
                SELECT is_like
                FROM reply_reactions
                WHERE reply_id = r.reply_id AND user_id = ?
            ) AS my_reactions
        FROM replies r
        JOIN users u ON r.author_id = u.user_id
        LEFT JOIN reply_reactions rr ON r.reply_id = rr.reply_id
        WHERE r.author_id = ?
        GROUP BY r.reply_id, r.reply_content, u.username, r.created_at, r.is_best
        ORDER BY r.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, user_id, per_page, offset)
    )

    replies = [
        ReplyResponse(
            id=row[0],
            author_id=row[1],
            content=row[2],
            author_username=row[3],
            likes=row[4],
            dislikes=row[5],
            created_at=row[6],
            is_best=bool(row[7]),
            current_user_reaction=(
                "like" if row[8] == 1 else "dislike"
            ) if row[8] is not None else None
        )
        for row in rows
    ]

    return ReplyList(
        replies=replies,
        total=total,
        page=page,
        per_page=per_page
    )


# ---------------- Admin Endpoints ----------------


def block_user(user_id: int, current_admin: User) -> bool:
    """
    Block a user preventing them from creating topics or replies.
    Admins cannot block themselves
    Args:
        user_id: ID of the user to block
        current_admin: The admin performing the action
    Returns:
        True if blocked, False if user not found.
    Raises:
        ForbiddenError if admin tries to block self.
    """
    existing = _get_by_id_internal(user_id)
    if not existing:
        raise NotFoundError("User not found")
    if user_id == current_admin.user_id:
        raise ForbiddenError("Cannot block yourself")

    update_query(
        "UPDATE users SET is_blocked = 1 WHERE user_id = ?",
        (user_id,)
    )
    return True


def unblock_user(user_id: int, current_admin: User) -> bool:
    """
    Unblock a previously blocked User.
    Admins cannot unblock themselves.
    Args:
        user_id: ID of the user to unblock.
        current_admin: The admin performing the action.
    Raises:
        NotFoundError: If user not found.
        ForbiddenError: If admin tries to unblock themselves.
    """
    if not _get_by_id_internal(user_id):
        raise NotFoundError("User not found")

    if user_id == current_admin.user_id:
        raise ForbiddenError("Cannot unblock yourself")

    update_query(
        "UPDATE users SET is_blocked = 0 WHERE user_id = ?",
        (user_id,)
    )
    return True


def promote_user(user_id: int, current_admin: User) -> bool:
    """
    Promote a user to admin.
    Admin cannot promote themselves.
    Args:
        user_id: ID of the user to promote.
        current_admin: The admin performing the action.
    Raises:
        NotFoundError: If user not found.
        ForbiddenError: If admin tries to promote themselves.
    """
    user = _get_by_id_internal(user_id)
    if not user:
        raise NotFoundError("User not found")

    if user_id == current_admin.user_id:
        raise ForbiddenError("Cannot promote yourself")

    if user.role_id == UserRole.ADMIN:
        raise ForbiddenError("User is already an admin")

    update_query(
        "UPDATE users SET role_id = ? WHERE user_id = ?",
        (UserRole.ADMIN, user_id)
    )
    return True


def demote_user(user_id: int, current_admin: User) -> bool:
    """
    Demote an Admin to User.
    Prevents the last remaining Admin to be demoted.
    Args:
        user_id: ID of user to demote.
        current_admin: The admin performing the action.
    Returns:
        True if demoted, False if user not found.
    Raises:
        NotFoundError: If user not found.
        ForbiddenError: If this will remove the last Admin.
    """
    user = _get_by_id_internal(user_id)
    if not user:
        raise NotFoundError("User not found")

    if user.role_id != UserRole.ADMIN:
        raise ForbiddenError("User is not an Admin")

    # Prevent demoting the last admin
    count = read_query(
        "SELECT COUNT(*) FROM users WHERE role_id = ? AND user_id !=?",
        (UserRole.ADMIN, user_id)
    )[0][0]
    if count == 0:
        raise ForbiddenError("Cannot demote the last admin")

    update_query(
        "UPDATE users SET role_id = ? WHERE user_id = ?",
        (UserRole.USER, user_id)
    )
    return True
