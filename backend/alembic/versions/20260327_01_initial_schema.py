"""initial schema

Revision ID: 20260327_01
Revises:
Create Date: 2026-03-27 14:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "chat_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_history_id", "chat_history", ["id"], unique=False)
    op.create_index("ix_chat_history_user_id", "chat_history", ["user_id"], unique=False)
    op.create_index("ix_chat_history_created_at", "chat_history", ["created_at"], unique=False)

    op.create_table(
        "wrong_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_image", sa.String(length=500), nullable=True),
        sa.Column("ai_analysis", sa.Text(), nullable=False),
        sa.Column("mastery_level", sa.Integer(), nullable=False),
        sa.Column("next_review", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_wrong_questions_id", "wrong_questions", ["id"], unique=False)
    op.create_index("ix_wrong_questions_user_id", "wrong_questions", ["user_id"], unique=False)
    op.create_index("ix_wrong_questions_next_review", "wrong_questions", ["next_review"], unique=False)
    op.create_index("ix_wrong_questions_created_at", "wrong_questions", ["created_at"], unique=False)

    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("questions_json", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("correct_rate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_quiz_sessions_id", "quiz_sessions", ["id"], unique=False)
    op.create_index("ix_quiz_sessions_user_id", "quiz_sessions", ["user_id"], unique=False)
    op.create_index("ix_quiz_sessions_created_at", "quiz_sessions", ["created_at"], unique=False)

    op.create_table(
        "study_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("study_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_study_logs_id", "study_logs", ["id"], unique=False)
    op.create_index("ix_study_logs_user_id", "study_logs", ["user_id"], unique=False)
    op.create_index("ix_study_logs_study_date", "study_logs", ["study_date"], unique=False)
    op.create_index("ix_study_logs_created_at", "study_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_study_logs_created_at", table_name="study_logs")
    op.drop_index("ix_study_logs_study_date", table_name="study_logs")
    op.drop_index("ix_study_logs_user_id", table_name="study_logs")
    op.drop_index("ix_study_logs_id", table_name="study_logs")
    op.drop_table("study_logs")

    op.drop_index("ix_quiz_sessions_created_at", table_name="quiz_sessions")
    op.drop_index("ix_quiz_sessions_user_id", table_name="quiz_sessions")
    op.drop_index("ix_quiz_sessions_id", table_name="quiz_sessions")
    op.drop_table("quiz_sessions")

    op.drop_index("ix_wrong_questions_created_at", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_next_review", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_user_id", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_id", table_name="wrong_questions")
    op.drop_table("wrong_questions")

    op.drop_index("ix_chat_history_created_at", table_name="chat_history")
    op.drop_index("ix_chat_history_user_id", table_name="chat_history")
    op.drop_index("ix_chat_history_id", table_name="chat_history")
    op.drop_table("chat_history")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
