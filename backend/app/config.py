import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)


def _env_flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off"}


def _env_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


DEFAULT_SQLITE_PATH = (BACKEND_DIR / "ai_study_helper.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]
DEFAULT_JWT_SECRET = "dev-secret-change-me"


def _normalize_database_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        return DEFAULT_DATABASE_URL
    sqlite_prefix = "sqlite:///"
    if value.startswith(sqlite_prefix):
        sqlite_path = value[len(sqlite_prefix) :]
        if sqlite_path.startswith("./"):
            resolved = (BACKEND_DIR / sqlite_path[2:]).resolve()
            return f"{sqlite_prefix}{resolved.as_posix()}"
    return value


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET)
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    database_url: str = _normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    auto_bootstrap_schema: bool = _env_flag("AUTO_BOOTSTRAP_SCHEMA", "0")
    cors_origins: list[str] = _env_csv("CORS_ORIGINS") or DEFAULT_CORS_ORIGINS


settings = Settings()
