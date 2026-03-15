from fastapi import APIRouter
from data.database import read_query
from common.response import success


stats_router = APIRouter(prefix="/stats", tags=['Stats'])


@stats_router.get("/")
def get_stats():
    """
    Public endpoint returning platform statistics.
    Returns total number of registered users and total number of topics.
    Top 10 by replies, and top 10 most recently created.
    Accessible without authentication.
    """
    user_count = read_query(
        "SELECT COUNT(*) FROM users WHERE is_deleted = 0"
    )[0][0]

    topic_count = read_query(
        "SELECT COUNT(*) FROM topics "
    )[0][0]

    top_replied_rows = read_query(
        """
        SELECT
            t.topic_id,
            t.title,
            u.username AS author_username,
            t.created_at,
            COALESCE(
                (SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id),
                0
            ) AS reply_count
            FROM topics t
            JOIN users u ON t.author_id = u.user_id
            WHERE t.is_private = 0
            ORDER BY reply_count DESC
            LIMIT 10
            """
    )

    top_recent_rows = read_query(
        """
        SELECT
            t.topic_id,
            t.title,
            u.username AS author_username,
            t.created_at,
            COALESCE(
                (SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id),
                0
            ) AS reply_count
            FROM topics t
            JOIN users u ON t.author_id = u.user_id
            WHERE t.is_private = 0
            ORDER BY t.created_at DESC
            LIMIT 10
            """
    )

    def format_topic(row):
        return {
            "topic_id": row[0],
            "title": row[1],
            "author_username": row[2],
            "created_at": str(row[3]),
            "reply_count": row[4]
        }

    return success(data={
        "total_users": user_count,
        "total_topics": topic_count,
        "top_10_most_replied": [format_topic(row) for row in top_replied_rows],
        "top_10_most_recent": [format_topic(row) for row in top_recent_rows]
    }, message='Stats retrieved')
