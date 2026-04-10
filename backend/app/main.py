import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import DEFAULT_JWT_SECRET, settings
from .database import bootstrap_schema
from .routers import auth, chat, convert, history, mindmap, quiz, review, today_review, user, wrong_book
from .utils import ok

logger = logging.getLogger(__name__)

bootstrap_schema()

app = FastAPI(title="AI 学习助手平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(wrong_book.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(today_review.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(mindmap.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(convert.router, prefix="/api")


@app.on_event("startup")
def warn_on_insecure_defaults():
    if settings.jwt_secret_key == DEFAULT_JWT_SECRET:
        logger.warning("JWT_SECRET_KEY is using the default development secret. Set a strong secret before deployment.")


@app.get("/api/health")
def health():
    return ok({"status": "ok"})


frontend_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"

if frontend_dist_dir.exists():
    assets_dir = frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    @app.get("/", include_in_schema=False)
    def root_index():
        return FileResponse(frontend_dist_dir / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        file_candidate = frontend_dist_dir / full_path
        if file_candidate.exists() and file_candidate.is_file():
            return FileResponse(file_candidate)
        return FileResponse(frontend_dist_dir / "index.html", headers={"Cache-Control": "no-store"})
elif frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend-dev")
