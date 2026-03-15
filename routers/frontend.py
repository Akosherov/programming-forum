from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services import topic_service, user_service
from data.database import read_query
import os
from jose import jwt, JWTError

templates = Jinja2Templates(directory="templates")

frontend_router = APIRouter(include_in_schema=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM", "HS256")


# ── AUTH HELPER ───────────────────────────────────────────────────
def _user_from_request(request: Request):
    """
    Decode the df_token cookie set by app.js on login.
    Returns the User object or None (never raises).
    """
    token = request.cookies.get("df_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        user = user_service._get_by_id_internal(user_id)
        if not user or user.is_deleted or user.is_blocked:
            return None
        return user
    except JWTError:
        return None


# ── HOME ──────────────────────────────────────────────────────────
@frontend_router.get("/", response_class=HTMLResponse)
def home(request: Request):
    total_users = read_query(
        "SELECT COUNT(*) FROM users WHERE is_deleted = 0"
    )[0][0]
    total_topics = read_query("SELECT COUNT(*) FROM topics")[0][0]

    top_replied_rows = read_query(
        """
        SELECT t.topic_id, t.title, u.username, t.created_at,
               COALESCE((SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id), 0) AS reply_count
        FROM topics t
        JOIN users u ON t.author_id = u.user_id
        WHERE t.is_private = 0
        ORDER BY reply_count DESC LIMIT 10
        """
    )
    top_recent_rows = read_query(
        """
        SELECT t.topic_id, t.title, u.username, t.created_at,
               COALESCE((SELECT COUNT(*) FROM replies r WHERE r.topic_id = t.topic_id), 0) AS reply_count
        FROM topics t
        JOIN users u ON t.author_id = u.user_id
        WHERE t.is_private = 0
        ORDER BY t.created_at DESC LIMIT 10
        """
    )

    def fmt(row):
        return {
            "topic_id": row[0], "title": row[1],
            "author_username": row[2], "created_at": str(row[3]),
            "reply_count": row[4],
        }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": {
            "total_users":         total_users,
            "total_topics":        total_topics,
            "top_10_most_replied": [fmt(r) for r in top_replied_rows],
            "top_10_most_recent":  [fmt(r) for r in top_recent_rows],
        },
        "active_page": "home",
    })


# ── TOPICS LIST ───────────────────────────────────────────────────
@frontend_router.get("/topics", response_class=HTMLResponse)
def topics_page(
    request:    Request,
    search:     str | None = Query(None),
    sort_by:    str = Query("created_at"),
    sort_order: str = Query("desc"),
    page:       int = Query(1, ge=1),
    per_page:   int = Query(15, ge=1, le=100),
):
    user = _user_from_request(request)
    current_user_id = user.user_id if user else None

    result = topic_service.get_topics(
        current_user_id=current_user_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
    )

    topics = result.topics if hasattr(result, "topics") else result.get("topics", [])
    total = result.total  if hasattr(result, "total")  else result.get("total", 0)
    total_pages = max(1, -(-total // per_page))

    def topic_to_dict(t):
        if isinstance(t, dict):
            return t
        return {
            "topic_id":        t.topic_id,
            "title":           t.title,
            "content":         getattr(t, "content", ""),
            "is_locked":       t.is_locked,
            "is_private":      t.is_private,
            "reply_count":     getattr(t, "reply_count", 0),
            "created_at":      str(t.created_at),
            "author_username": t.author_username,
            "author_id":       getattr(t, "author_id", None),
        }

    return templates.TemplateResponse("topics.html", {
        "request":     request,
        "topics":      [topic_to_dict(t) for t in topics],
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": total_pages,
        "search":      search or "",
        "sort_by":     sort_by,
        "sort_order":  sort_order,
        "active_page": "topics",
    })


# ── TOPIC DETAIL ──────────────────────────────────────────────────
@frontend_router.get("/topics/{topic_id}", response_class=HTMLResponse)
def topic_detail_page(request: Request, topic_id: int):
    from services import reply_service

    user = _user_from_request(request)
    current_user_id = user.user_id if user else None

    try:
        topic_resp = topic_service.get_topic_by_id(topic_id, current_user_id=current_user_id)
        replies_resp = reply_service.get_replies(topic_id, current_user_id=current_user_id, page=1, per_page=100)
    except Exception:
        return RedirectResponse("/topics", status_code=302)

    def obj_to_dict(obj):
        if isinstance(obj, dict):
            return obj
        # Pydantic v2 model
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Pydantic v1 model
        if hasattr(obj, "dict"):
            return obj.dict()
        return vars(obj) if hasattr(obj, "__dict__") else {}

    topic = obj_to_dict(topic_resp) if topic_resp else {}

    raw_replies = []
    if replies_resp:
        if hasattr(replies_resp, "replies"):
            raw_replies = replies_resp.replies
        elif isinstance(replies_resp, dict):
            raw_replies = replies_resp.get("replies", [])

    def reply_to_dict(r):
        if isinstance(r, dict):
            return r
        return {
            "id":                    r.id,
            "author_id":             r.author_id,
            "author_username":       r.author_username,
            "content":               r.content,
            "likes":                 r.likes,
            "dislikes":              r.dislikes,
            "is_best":               r.is_best,
            "created_at":            str(r.created_at),
            "current_user_reaction": r.current_user_reaction,
        }

    # Fetch current participants so the invite panel can show them (author of private topic only)
    participants = []
    if user and topic.get("author_id") == user.user_id and topic.get("is_private"):
        rows = read_query(
            """
            SELECT u.user_id, u.username, u.first_name, u.last_name
            FROM topic_participants tp
            JOIN users u ON tp.user_id = u.user_id
            WHERE tp.topic_id = ?
            """,
            (topic_id,)
        )
        participants = [
            {"user_id": r[0], "username": r[1],
             "first_name": r[2], "last_name": r[3]}
            for r in rows
        ]

    # Convert current_user to a plain dict so Jinja2 can access fields cleanly
    current_user_dict = None
    if user:
        if hasattr(user, "model_dump"):
            current_user_dict = user.model_dump()
        elif hasattr(user, "dict"):
            current_user_dict = user.dict()
        else:
            current_user_dict = vars(user)

    return templates.TemplateResponse("topic_detail.html", {
        "request":      request,
        "topic":        topic,
        "replies":      [reply_to_dict(r) for r in raw_replies],
        "current_user": current_user_dict,
        "participants": participants,
        "active_page":  "topics",
    })


# ── PROFILE ───────────────────────────────────────────────────────
@frontend_router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {
        "request": request, "active_page": "profile",
    })


# ── ADMIN ─────────────────────────────────────────────────────────
@frontend_router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    total_users = read_query("SELECT COUNT(*) FROM users WHERE is_deleted = 0")[0][0]
    total_topics = read_query("SELECT COUNT(*) FROM topics")[0][0]
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": {"total_users": total_users, "total_topics": total_topics},
        "active_page": "admin",
    })
