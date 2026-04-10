import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def should_bootstrap_schema(existing_tables: set[str], app_tables: set[str]) -> bool:
    if not app_tables:
        return False
    if "alembic_version" in existing_tables:
        return False
    return not (existing_tables & app_tables)


def bootstrap_schema():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    app_tables = set(Base.metadata.tables.keys())
    if should_bootstrap_schema(existing_tables, app_tables):
        if not settings.auto_bootstrap_schema:
            return
        logger.warning("AUTO_BOOTSTRAP_SCHEMA is enabled; creating tables for a fresh database without Alembic metadata.")
        Base.metadata.create_all(bind=engine)
        return

    if existing_tables and "alembic_version" not in existing_tables:
        logger.warning(
            "Detected an existing database without Alembic metadata. Applying legacy compatibility patches for missing columns."
        )
        _apply_legacy_compatibility_patches(inspector)


def _apply_legacy_compatibility_patches(inspector) -> None:
    _ensure_columns(
        inspector,
        "chat_history",
        {
            "model": "ALTER TABLE chat_history ADD COLUMN model VARCHAR(100) DEFAULT ''",
            "mode_key": "ALTER TABLE chat_history ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
            "structured_json": "ALTER TABLE chat_history ADD COLUMN structured_json TEXT DEFAULT '{}'",
        },
    )
    _ensure_columns(
        inspector,
        "quiz_sessions",
        {
            "mode_key": "ALTER TABLE quiz_sessions ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
        },
    )
    _ensure_columns(
        inspector,
        "wrong_questions",
        {
            "source_chat_id": "ALTER TABLE wrong_questions ADD COLUMN source_chat_id INTEGER",
            "source_quiz_id": "ALTER TABLE wrong_questions ADD COLUMN source_quiz_id INTEGER",
            "mode_key": "ALTER TABLE wrong_questions ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
            "options_json": "ALTER TABLE wrong_questions ADD COLUMN options_json TEXT DEFAULT '[]'",
            "correct_answer": "ALTER TABLE wrong_questions ADD COLUMN correct_answer VARCHAR(100) DEFAULT ''",
            "mastery_status": "ALTER TABLE wrong_questions ADD COLUMN mastery_status VARCHAR(20) DEFAULT 'unmastered'",
            "review_count": "ALTER TABLE wrong_questions ADD COLUMN review_count INTEGER DEFAULT 0",
            "wrong_count": "ALTER TABLE wrong_questions ADD COLUMN wrong_count INTEGER DEFAULT 1",
            "correct_count": "ALTER TABLE wrong_questions ADD COLUMN correct_count INTEGER DEFAULT 0",
            "last_review_at": "ALTER TABLE wrong_questions ADD COLUMN last_review_at DATETIME",
        },
    )
    _ensure_columns(
        inspector,
        "review_tasks",
        {
            "source_wrong_question_id": "ALTER TABLE review_tasks ADD COLUMN source_wrong_question_id INTEGER",
            "source_chat_id": "ALTER TABLE review_tasks ADD COLUMN source_chat_id INTEGER",
            "mode_key": "ALTER TABLE review_tasks ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
            "reason": "ALTER TABLE review_tasks ADD COLUMN reason TEXT DEFAULT ''",
            "estimated_minutes": "ALTER TABLE review_tasks ADD COLUMN estimated_minutes INTEGER DEFAULT 0",
            "task_date": "ALTER TABLE review_tasks ADD COLUMN task_date DATE",
        },
    )
    _ensure_columns(
        inspector,
        "mindmap_records",
        {
            "source_chat_id": "ALTER TABLE mindmap_records ADD COLUMN source_chat_id INTEGER",
            "mode_key": "ALTER TABLE mindmap_records ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
        },
    )
    _ensure_columns(
        inspector,
        "mindmap_versions",
        {
            "mode_key": "ALTER TABLE mindmap_versions ADD COLUMN mode_key VARCHAR(40) DEFAULT 'general'",
        },
    )
    _ensure_columns(
        inspector,
        "chat_feedbacks",
        {
            "user_id": "ALTER TABLE chat_feedbacks ADD COLUMN user_id INTEGER",
            "chat_id": "ALTER TABLE chat_feedbacks ADD COLUMN chat_id INTEGER",
            "feedback_type": "ALTER TABLE chat_feedbacks ADD COLUMN feedback_type VARCHAR(30)",
            "created_at": "ALTER TABLE chat_feedbacks ADD COLUMN created_at DATETIME",
        },
    )


def _ensure_columns(inspector, table_name: str, statements_by_column: dict[str, str]) -> None:
    if table_name not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns(table_name)}
    statements = [statement for column, statement in statements_by_column.items() if column not in column_names]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
