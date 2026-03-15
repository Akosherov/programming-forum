from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import auth_router
from routers.invitations import invitations_router
from routers.participants import participants_router
from routers.reactions import reactions_router
from routers.replies import replies_router
from routers.stats import stats_router
from routers.topics import topics_router
from routers.users import users_router
from routers.frontend import frontend_router
from common.exceptions import AppError


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------- STATIC FILES --------------


app.mount("/static", StaticFiles(directory="static"), name="static")


# ──----------- ERROR HANDLERS ---------------


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "Internal server error"})


# ── API ROUTERS (all under /api to avoid colliding with HTML routes) ──
app.include_router(auth_router, prefix="/api")
app.include_router(invitations_router, prefix="/api")
app.include_router(participants_router, prefix="/api")
app.include_router(reactions_router, prefix="/api")
app.include_router(replies_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(topics_router, prefix="/api")
app.include_router(users_router, prefix="/api")

# ── HTML PAGES (no prefix — owns /,  /topics, /topics/{id}, etc.) ──
app.include_router(frontend_router)
