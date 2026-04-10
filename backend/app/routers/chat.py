import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import ChatFeedback, ChatHistory, LearningAsset, MindMapRecord, MindMapVersion, ReviewTask, StudyLog, User, WrongQuestion
from ..services.ai_service import ask_ai, normalize_structured_chat, stream_ai
from ..services.behavior_modes import list_mode_profiles, normalize_mode_key
from ..utils import err, ok

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    question: str
    subject: str = "General"
    mode_key: str = "general"
    chat_id: int | None = None


class ChatFeedbackIn(BaseModel):
    feedback_type: str


def _serialize_record(record: ChatHistory, db: Session | None = None) -> dict:
    try:
        structured = json.loads(record.structured_json or "{}")
    except json.JSONDecodeError:
        structured = {}

    structured = normalize_structured_chat(
        question=record.question,
        subject=record.subject,
        answer=record.answer,
        structured=structured,
    )

    feedback_type = ""
    if db is not None:
        feedback = (
            db.query(ChatFeedback)
            .filter(ChatFeedback.chat_id == record.id)
            .order_by(ChatFeedback.created_at.desc(), ChatFeedback.id.desc())
            .first()
        )
        feedback_type = feedback.feedback_type if feedback else ""

    return {
        "id": record.id,
        "answer": record.answer,
        "raw_answer": record.answer,
        "structured": structured,
        "follow_ups": structured.get("follow_ups", []),
        "structured_quality": "ok" if record.structured_json and record.structured_json != "{}" else "fallback",
        "related_topics": [],
        "subject": record.subject,
        "mode_key": getattr(record, "mode_key", "general"),
        "model": record.model or "",
        "question": record.question,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "feedback_type": feedback_type,
    }


def _save_chat_record(
    db: Session,
    user: User,
    subject: str,
    mode_key: str,
    question: str,
    answer: str,
    structured: dict,
) -> ChatHistory:
    record = ChatHistory(
        user_id=user.id,
        subject=subject,
        mode_key=normalize_mode_key(mode_key),
        model=settings.openai_model,
        question=question,
        answer=answer,
        structured_json=json.dumps(structured, ensure_ascii=False),
    )
    db.add(record)
    db.add(StudyLog(user_id=user.id, subject=subject, duration=3))
    db.commit()
    db.refresh(record)
    return record


def _cleanup_chat_dependencies(db: Session, user_id: int, chat_ids: list[int]) -> None:
    if not chat_ids:
        return

    db.query(ChatFeedback).filter(ChatFeedback.user_id == user_id, ChatFeedback.chat_id.in_(chat_ids)).delete(
        synchronize_session=False
    )
    db.query(LearningAsset).filter(LearningAsset.user_id == user_id, LearningAsset.chat_id.in_(chat_ids)).delete(
        synchronize_session=False
    )
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user_id, WrongQuestion.source_chat_id.in_(chat_ids)).update(
        {WrongQuestion.source_chat_id: None},
        synchronize_session=False,
    )
    db.query(MindMapRecord).filter(MindMapRecord.user_id == user_id, MindMapRecord.source_chat_id.in_(chat_ids)).update(
        {MindMapRecord.source_chat_id: None},
        synchronize_session=False,
    )
    db.query(MindMapVersion).filter(MindMapVersion.user_id == user_id, MindMapVersion.source_chat_id.in_(chat_ids)).update(
        {MindMapVersion.source_chat_id: None},
        synchronize_session=False,
    )
    db.query(ReviewTask).filter(ReviewTask.user_id == user_id, ReviewTask.source_chat_id.in_(chat_ids)).update(
        {ReviewTask.source_chat_id: None},
        synchronize_session=False,
    )


def _sse_payload(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/meta")
def chat_meta(user: User = Depends(get_current_user)):
    return ok(
        {
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
            "default_mode": "general",
            "modes": list_mode_profiles(),
        }
    )


@router.post("")
async def send_question(payload: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mode_key = normalize_mode_key(payload.mode_key)
    answer, structured, structured_quality, related_topics, is_error = await ask_ai(payload.question, payload.subject, mode_key)
    if is_error:
        return err(2001, answer)

    record = _save_chat_record(db, user, payload.subject, mode_key, payload.question, answer, structured)
    data = _serialize_record(record, db)
    data["related_topics"] = related_topics
    data["structured_quality"] = structured_quality
    data["follow_ups"] = structured.get("follow_ups", [])
    data["mode_key"] = mode_key
    return ok(data)


@router.post("/stream")
async def send_question_stream(payload: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mode_key = normalize_mode_key(payload.mode_key)

    async def event_stream():
        answer_parts: list[str] = []

        async for event in stream_ai(payload.question, payload.subject, mode_key):
            event_type = event.get("type")
            if event_type == "delta":
                content = event.get("content", "")
                if content:
                    answer_parts.append(content)
                    yield _sse_payload("delta", {"content": content})
                continue

            if event_type == "error":
                yield _sse_payload("error", {"message": event.get("message", "AI 服务暂时不可用，请稍后重试。")})
                return

            if event_type == "done":
                answer = event.get("answer") or "".join(answer_parts).strip()
                if not answer:
                    yield _sse_payload("error", {"message": "AI 没有返回可显示的内容。"})
                    return
                structured = event.get("structured") or normalize_structured_chat(
                    question=payload.question,
                    subject=payload.subject,
                    answer=answer,
                )
                record = _save_chat_record(db, user, payload.subject, mode_key, payload.question, answer, structured)
                data = _serialize_record(record, db)
                data["related_topics"] = event.get("related_topics") or []
                data["structured_quality"] = event.get("structured_quality") or "fallback"
                data["follow_ups"] = structured.get("follow_ups", [])
                data["mode_key"] = mode_key
                yield _sse_payload("done", data)
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
def chat_history(
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = max(page - 1, 0) * page_size
    items = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return ok([_serialize_record(item, db) for item in items])


@router.post("/{chat_id}/feedback")
def chat_feedback(
    chat_id: int,
    payload: ChatFeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(ChatHistory).filter(ChatHistory.id == chat_id, ChatHistory.user_id == user.id).first()
    if not item:
        return err(1002, "记录不存在")

    feedback_type = payload.feedback_type.strip()
    if feedback_type not in {"useful", "confusing"}:
        return err(1002, "反馈类型无效")

    existing = (
        db.query(ChatFeedback)
        .filter(ChatFeedback.user_id == user.id, ChatFeedback.chat_id == chat_id, ChatFeedback.feedback_type == feedback_type)
        .first()
    )
    if existing:
        return ok({"feedback_type": feedback_type}, "已记录")

    db.add(ChatFeedback(user_id=user.id, chat_id=chat_id, feedback_type=feedback_type))
    db.commit()
    return ok({"feedback_type": feedback_type}, "记录成功")


@router.delete("/clear")
def clear_chat_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat_ids = [chat_id for (chat_id,) in db.query(ChatHistory.id).filter(ChatHistory.user_id == user.id).all()]
    _cleanup_chat_dependencies(db, user.id, chat_ids)
    db.query(ChatHistory).filter(ChatHistory.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return ok({}, "已清空")


@router.delete("/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(ChatHistory).filter(ChatHistory.id == chat_id, ChatHistory.user_id == user.id).first()
    if not item:
        return err(1002, "记录不存在")

    _cleanup_chat_dependencies(db, user.id, [chat_id])
    db.delete(item)
    db.commit()
    return ok({}, "已删除")
