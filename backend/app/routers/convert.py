import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatHistory, LearningAsset, MindMapRecord, ReviewTask, StudyLog, User, WrongQuestion
from ..services.ai_service import build_text_tree, normalize_structured_chat, structured_to_mindmap
from ..services.behavior_modes import normalize_mode_key
from ..utils import err, ok

router = APIRouter(prefix="/convert", tags=["convert"])


class ConvertIn(BaseModel):
    chat_id: int


def _get_chat_or_none(db: Session, user: User, chat_id: int) -> ChatHistory | None:
    return db.query(ChatHistory).filter(ChatHistory.id == chat_id, ChatHistory.user_id == user.id).first()


def _load_structured(chat: ChatHistory) -> dict:
    try:
        parsed = json.loads(chat.structured_json or "{}")
    except json.JSONDecodeError:
        parsed = {}
    return normalize_structured_chat(
        question=chat.question,
        subject=chat.subject,
        answer=chat.answer,
        structured=parsed,
    )


def _asset_refs(db: Session, user_id: int, chat_id: int, asset_type: str) -> list[int]:
    rows = (
        db.query(LearningAsset.asset_ref_id)
        .filter(
            LearningAsset.user_id == user_id,
            LearningAsset.chat_id == chat_id,
            LearningAsset.asset_type == asset_type,
            LearningAsset.status == "active",
        )
        .all()
    )
    return [row[0] for row in rows]


def _create_asset(db: Session, *, user_id: int, chat_id: int, asset_type: str, asset_ref_id: int) -> None:
    db.add(
        LearningAsset(
            user_id=user_id,
            chat_id=chat_id,
            asset_type=asset_type,
            asset_ref_id=asset_ref_id,
            status="active",
        )
    )


def _create_or_get_seed_wrong_question(
    db: Session,
    *,
    user: User,
    chat: ChatHistory,
    mode_key: str,
    structured: dict,
) -> WrongQuestion:
    existing = (
        db.query(WrongQuestion)
        .filter(WrongQuestion.user_id == user.id, WrongQuestion.source_chat_id == chat.id)
        .order_by(WrongQuestion.created_at.asc(), WrongQuestion.id.asc())
        .first()
    )
    if existing:
        return existing

    example = structured.get("example") if isinstance(structured.get("example"), dict) else {}
    question_text = str(example.get("question", "")).strip() or chat.question
    analysis = str(example.get("analysis", "")).strip() or str(structured.get("explanation", "")).strip() or "来自 AI 问答转换"

    item = WrongQuestion(
        user_id=user.id,
        source_chat_id=chat.id,
        subject=chat.subject,
        mode_key=mode_key,
        question_text=question_text,
        ai_analysis=analysis,
        mastery_level=0,
        mastery_status="unmastered",
        review_count=0,
        wrong_count=1,
        correct_count=0,
        next_review=date.today() + timedelta(days=1),
    )
    db.add(item)
    db.flush()
    return item


@router.post("/to-wrong-question")
def to_wrong_question(payload: ConvertIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat = _get_chat_or_none(db, user, payload.chat_id)
    if not chat:
        return err(1002, "聊天记录不存在")

    existing_ids = _asset_refs(db, user.id, chat.id, "wrong_question")
    if existing_ids:
        return ok({"created_count": 0, "wrong_question_ids": existing_ids, "existing": True}, "该问答已加入错题本")

    structured = _load_structured(chat)
    example = structured.get("example") if isinstance(structured.get("example"), dict) else {}
    pitfalls = structured.get("pitfalls") if isinstance(structured.get("pitfalls"), list) else []
    mode_key = normalize_mode_key(getattr(chat, "mode_key", "general"))

    created_ids: list[int] = []
    base_analysis = str(example.get("analysis", "")).strip() or str(structured.get("explanation", "")).strip()

    main_question = str(example.get("question", "")).strip() or chat.question
    if main_question:
        item = WrongQuestion(
            user_id=user.id,
            source_chat_id=chat.id,
            subject=chat.subject,
            mode_key=mode_key,
            question_text=main_question,
            ai_analysis=base_analysis or "来自 AI 问答转换",
            mastery_level=0,
            mastery_status="unmastered",
            review_count=0,
            wrong_count=1,
            correct_count=0,
            next_review=date.today() + timedelta(days=1),
        )
        db.add(item)
        db.flush()
        _create_asset(db, user_id=user.id, chat_id=chat.id, asset_type="wrong_question", asset_ref_id=item.id)
        created_ids.append(item.id)

    for pitfall in pitfalls[:2]:
        text = str(pitfall).strip()
        if not text:
            continue
        item = WrongQuestion(
            user_id=user.id,
            source_chat_id=chat.id,
            subject=chat.subject,
            mode_key=mode_key,
            question_text=f"易错点复盘：{text}",
            ai_analysis=base_analysis or "来自 AI 问答转换",
            mastery_level=0,
            mastery_status="unmastered",
            review_count=0,
            wrong_count=1,
            correct_count=0,
            next_review=date.today() + timedelta(days=1),
        )
        db.add(item)
        db.flush()
        _create_asset(db, user_id=user.id, chat_id=chat.id, asset_type="wrong_question", asset_ref_id=item.id)
        created_ids.append(item.id)

    db.add(StudyLog(user_id=user.id, subject=chat.subject, duration=2))
    db.commit()
    return ok({"created_count": len(created_ids), "wrong_question_ids": created_ids, "existing": False}, "已加入错题本")


@router.post("/to-review")
def to_review(payload: ConvertIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat = _get_chat_or_none(db, user, payload.chat_id)
    if not chat:
        return err(1002, "聊天记录不存在")

    existing_ids = _asset_refs(db, user.id, chat.id, "review_task")
    if existing_ids:
        return ok({"created_count": 0, "review_task_ids": existing_ids, "existing": True}, "该问答已加入复习计划")

    structured = _load_structured(chat)
    pitfalls = structured.get("pitfalls") if isinstance(structured.get("pitfalls"), list) else []
    conclusion = str(structured.get("conclusion", "")).strip() or "请先回顾本次问答的核心结论。"
    mode_key = normalize_mode_key(getattr(chat, "mode_key", "general"))
    seed_wrong = _create_or_get_seed_wrong_question(db, user=user, chat=chat, mode_key=mode_key, structured=structured)

    created_ids: list[int] = []
    seeds = pitfalls[:3] if pitfalls else [conclusion]
    for idx, seed in enumerate(seeds, start=1):
        task = ReviewTask(
            user_id=user.id,
            source_wrong_question_id=seed_wrong.id,
            source_chat_id=chat.id,
            subject=chat.subject,
            mode_key=mode_key,
            title=f"复习任务 {idx}：{chat.subject}",
            reason="来自 AI 问答内容的重点回顾",
            content=str(seed).strip() or conclusion,
            estimated_minutes=8 if idx == 1 else 6,
            priority="high" if idx == 1 else "medium",
            status="pending",
            task_date=date.today(),
            due_date=date.today(),
            updated_at=datetime.utcnow(),
        )
        db.add(task)
        db.flush()
        _create_asset(db, user_id=user.id, chat_id=chat.id, asset_type="review_task", asset_ref_id=task.id)
        created_ids.append(task.id)

    db.add(StudyLog(user_id=user.id, subject=chat.subject, duration=1))
    db.commit()
    return ok({"created_count": len(created_ids), "review_task_ids": created_ids, "existing": False}, "已加入复习计划")


@router.post("/to-mindmap")
def to_mindmap(payload: ConvertIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat = _get_chat_or_none(db, user, payload.chat_id)
    if not chat:
        return err(1002, "聊天记录不存在")

    existing_ids = _asset_refs(db, user.id, chat.id, "mindmap")
    if existing_ids:
        latest = (
            db.query(MindMapRecord)
            .filter(MindMapRecord.id == existing_ids[0], MindMapRecord.user_id == user.id)
            .first()
        )
        if latest:
            return ok({"created": False, "mindmap_id": latest.id, "topic": latest.topic}, "该问答已生成思维导图")

    structured = _load_structured(chat)
    tree = structured_to_mindmap(structured)
    mode_key = normalize_mode_key(getattr(chat, "mode_key", "general"))

    record = MindMapRecord(
        user_id=user.id,
        source_chat_id=chat.id,
        mode_key=mode_key,
        topic=str(tree.get("topic", "")).strip() or chat.subject,
        text_tree=build_text_tree(tree),
        nodes_json=json.dumps(tree.get("nodes") or [], ensure_ascii=False),
        updated_at=datetime.utcnow(),
    )
    db.add(record)
    db.flush()

    _create_asset(db, user_id=user.id, chat_id=chat.id, asset_type="mindmap", asset_ref_id=record.id)
    db.add(StudyLog(user_id=user.id, subject=chat.subject, duration=2))
    db.commit()
    return ok(
        {
            "created": True,
            "mindmap_id": record.id,
            "topic": record.topic,
            "text_tree": record.text_tree,
        },
        "思维导图已生成",
    )
