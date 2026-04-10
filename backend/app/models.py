from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chats = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    wrong_questions = relationship("WrongQuestion", back_populates="user", cascade="all, delete-orphan")
    quizzes = relationship("QuizSession", back_populates="user", cascade="all, delete-orphan")
    study_logs = relationship("StudyLog", back_populates="user", cascade="all, delete-orphan")
    mindmaps = relationship("MindMapRecord", back_populates="user", cascade="all, delete-orphan")
    mindmap_versions = relationship("MindMapVersion", back_populates="user", cascade="all, delete-orphan")
    review_tasks = relationship("ReviewTask", back_populates="user", cascade="all, delete-orphan")
    chat_feedbacks = relationship("ChatFeedback", back_populates="user", cascade="all, delete-orphan")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(50), default="通用")
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    model: Mapped[str] = mapped_column(String(100), default="")
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="chats")
    feedbacks = relationship("ChatFeedback", back_populates="chat", cascade="all, delete-orphan")


class ChatFeedback(Base):
    __tablename__ = "chat_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_history.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="chat_feedbacks")
    chat = relationship("ChatHistory", back_populates="feedbacks")


class WrongQuestion(Base):
    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_chat_id: Mapped[int | None] = mapped_column(ForeignKey("chat_history.id"), nullable=True, index=True)
    source_quiz_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_sessions.id"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(50), default="通用")
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    question_text: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    correct_answer: Mapped[str] = mapped_column(String(100), default="")
    question_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_analysis: Mapped[str] = mapped_column(Text, default="")
    mastery_level: Mapped[int] = mapped_column(Integer, default=0)
    mastery_status: Mapped[str] = mapped_column(String(20), default="unmastered", index=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="wrong_questions")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(50))
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    topic: Mapped[str] = mapped_column(String(100))
    questions_json: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="quizzes")


class StudyLog(Base):
    __tablename__ = "study_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(50), default="通用")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    study_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="study_logs")


class MindMapRecord(Base):
    __tablename__ = "mindmap_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_chat_id: Mapped[int | None] = mapped_column(ForeignKey("chat_history.id"), nullable=True, index=True)
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    topic: Mapped[str] = mapped_column(String(100), default="思维导图")
    text_tree: Mapped[str] = mapped_column(Text, default="")
    nodes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="mindmaps")


class MindMapVersion(Base):
    __tablename__ = "mindmap_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mindmap_key: Mapped[str] = mapped_column(String(120), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, index=True)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("mindmap_versions.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="topic", index=True)
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    source_ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_chat_id: Mapped[int | None] = mapped_column(ForeignKey("chat_history.id"), nullable=True, index=True)
    source_wrong_question_id: Mapped[int | None] = mapped_column(ForeignKey("wrong_questions.id"), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(100), default="思维导图")
    nodes_json: Mapped[str] = mapped_column(Text, default="[]")
    text_tree: Mapped[str] = mapped_column(Text, default="")
    source_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    change_type: Mapped[str] = mapped_column(String(30), default="generate", index=True)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="mindmap_versions")
    parent_version = relationship("MindMapVersion", remote_side=[id], uselist=False)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_wrong_question_id: Mapped[int] = mapped_column(ForeignKey("wrong_questions.id"), index=True)
    source_chat_id: Mapped[int | None] = mapped_column(ForeignKey("chat_history.id"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(50), default="通用")
    mode_key: Mapped[str] = mapped_column(String(40), default="general", index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    task_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    due_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="review_tasks")


class LearningAsset(Base):
    __tablename__ = "learning_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_history.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(30), index=True)
    asset_ref_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
