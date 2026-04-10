import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import StudyLog, User, WrongQuestion
from ..services.ai_service import analyze_wrong_question
from ..services.behavior_modes import normalize_mode_key
from ..utils import err, ok

router = APIRouter(prefix="/wrong-book", tags=["wrong-book"])

STATUS_BY_LEVEL = {
    0: "unmastered",
    1: "unmastered",
    2: "fuzzy",
    3: "fuzzy",
    4: "mastered",
    5: "mastered",
}

INTERVAL_BY_STATUS = {
    "unmastered": 1,
    "fuzzy": 3,
    "mastered": 7,
}


class WrongBookCreateIn(BaseModel):
    subject: str = "General"
    question_text: str
    question_image: str | None = None
    mode_key: str = "general"
    options: list[str] | None = None
    correct_answer: str | None = None
    source_quiz_id: int | None = None


class WrongBookUpdateIn(BaseModel):
    mastery_level: int


def _normalize_level(level: int) -> int:
    return max(0, min(5, level))


def _status_from_level(level: int) -> str:
    return STATUS_BY_LEVEL[_normalize_level(level)]


def _next_review(level: int) -> date:
    status = _status_from_level(level)
    return date.today() + timedelta(days=INTERVAL_BY_STATUS[status])


def _serialize_item(item: WrongQuestion) -> dict:
    try:
        options = json.loads(item.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    if not isinstance(options, list):
        options = []
    return {
        "id": item.id,
        "subject": item.subject,
        "mode_key": item.mode_key,
        "question_text": item.question_text,
        "options": [str(option).strip() for option in options if str(option).strip()],
        "correct_answer": item.correct_answer or "",
        "analysis": item.ai_analysis,
        "mastery_level": item.mastery_level,
        "mastery_status": item.mastery_status,
        "next_review": item.next_review.strftime("%Y-%m-%d"),
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.post("")
async def create_wrong_question(
    payload: WrongBookCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mode_key = normalize_mode_key(payload.mode_key)
    analysis = await analyze_wrong_question(payload.subject, payload.question_text, mode_key)
    item = WrongQuestion(
        user_id=user.id,
        subject=payload.subject,
        mode_key=mode_key,
        question_text=payload.question_text,
        options_json=json.dumps(payload.options or [], ensure_ascii=False),
        correct_answer=(payload.correct_answer or "").strip(),
        source_quiz_id=payload.source_quiz_id,
        question_image=payload.question_image,
        ai_analysis=analysis,
        mastery_level=0,
        mastery_status="unmastered",
        review_count=0,
        wrong_count=1,
        correct_count=0,
        next_review=_next_review(0),
    )
    db.add(item)
    db.add(StudyLog(user_id=user.id, subject=payload.subject, duration=2))
    db.commit()
    db.refresh(item)
    return ok({"id": item.id, "analysis": item.ai_analysis}, "已加入错题本")


@router.get("")
def get_wrong_questions(
    subject: str | None = None,
    keyword: str | None = None,
    mastery_level: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id)
    if subject:
        q = q.filter(WrongQuestion.subject == subject)
    if keyword:
        q = q.filter(WrongQuestion.question_text.ilike(f"%{keyword.strip()}%"))
    if mastery_level is not None and 0 <= mastery_level <= 5:
        q = q.filter(WrongQuestion.mastery_level == mastery_level)

    items = q.order_by(WrongQuestion.created_at.desc()).all()
    subject_options = [
        row[0]
        for row in db.query(WrongQuestion.subject)
        .filter(WrongQuestion.user_id == user.id)
        .distinct()
        .order_by(WrongQuestion.subject.asc())
        .all()
    ]
    return ok({"items": [_serialize_item(x) for x in items], "subject_options": subject_options})


@router.get("/{item_id}")
def get_wrong_question(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(WrongQuestion).filter(WrongQuestion.id == item_id, WrongQuestion.user_id == user.id).first()
    if not item:
        return err(1002, "错题不存在")
    return ok(
        {
            "question_text": item.question_text,
            "options": _serialize_item(item)["options"],
            "correct_answer": item.correct_answer or "",
            "analysis": item.ai_analysis,
            "mastery_level": item.mastery_level,
            "mastery_status": item.mastery_status,
            "next_review": item.next_review.strftime("%Y-%m-%d"),
        }
    )


@router.put("/{item_id}")
def update_wrong_question(
    item_id: int,
    payload: WrongBookUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(WrongQuestion).filter(WrongQuestion.id == item_id, WrongQuestion.user_id == user.id).first()
    if not item:
        return err(1002, "错题不存在")

    level = _normalize_level(payload.mastery_level)
    status = _status_from_level(level)
    item.mastery_level = level
    item.mastery_status = status
    item.next_review = _next_review(level)
    item.review_count += 1
    if status == "mastered":
        item.correct_count += 1
    db.commit()
    return ok(
        {
            "mastery_level": item.mastery_level,
            "mastery_status": item.mastery_status,
            "next_review": item.next_review.strftime("%Y-%m-%d"),
        },
        "掌握度已更新",
    )


@router.delete("/{item_id}")
def delete_wrong_question(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(WrongQuestion).filter(WrongQuestion.id == item_id, WrongQuestion.user_id == user.id).first()
    if not item:
        return err(1002, "错题不存在")
    db.delete(item)
    db.commit()
    return ok({}, "错题已删除")
