from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ReviewTask, StudyLog, User, WrongQuestion
from ..utils import err, ok

router = APIRouter(prefix="/review", tags=["today-review"])

STATUS_ORDER = {"unmastered": 0, "fuzzy": 1, "mastered": 2}
STATUS_LABEL = {"unmastered": "还不熟", "fuzzy": "有点模糊", "mastered": "基本掌握"}
INTERVAL_DAYS = {"unmastered": 1, "fuzzy": 3, "mastered": 7}


class ReviewCompleteIn(BaseModel):
    remembered: bool = True


def _normalize_status(item: WrongQuestion) -> str:
    if item.mastery_status in STATUS_ORDER:
        return item.mastery_status
    if item.mastery_level <= 1:
        return "unmastered"
    if item.mastery_level <= 3:
        return "fuzzy"
    return "mastered"


def _sync_status(item: WrongQuestion) -> str:
    status = _normalize_status(item)
    item.mastery_status = status
    if status == "unmastered":
        item.mastery_level = 0
    elif status == "fuzzy":
        item.mastery_level = 2
    else:
        item.mastery_level = 4
    return status


def _next_interval_days(item: WrongQuestion, status: str) -> int:
    if status == "mastered":
        if item.correct_count >= 6:
            return 30
        if item.correct_count >= 3:
            return 14
        return 7
    return INTERVAL_DAYS[status]


def _estimated_minutes(item: WrongQuestion, status: str) -> int:
    base = {"unmastered": 12, "fuzzy": 9, "mastered": 6}[status]
    extra = min(max(item.wrong_count - 1, 0), 3) * 2
    return max(5, min(20, base + extra))


def _reason_text(item: WrongQuestion, status: str, today: date) -> str:
    interval = _next_interval_days(item, status)
    overdue_days = max(0, (today - item.next_review).days)
    if status == "unmastered":
        base = f"这部分内容目前还不熟，建议按 {interval} 天的节奏回看。"
    elif status == "fuzzy":
        base = f"这部分内容还不够稳，按 {interval} 天的节奏复习更合适。"
    else:
        base = f"这部分内容基本掌握，但仍需要按 {interval} 天节奏防止遗忘。"
    if overdue_days > 0:
        return f"{base} 当前已经超过计划复习时间 {overdue_days} 天。"
    return base


def _build_task_payload(item: WrongQuestion, today: date) -> dict:
    status = _sync_status(item)
    interval = _next_interval_days(item, status)
    return {
        "source_wrong_question_id": item.id,
        "source_chat_id": item.source_chat_id,
        "subject": item.subject,
        "mode_key": item.mode_key,
        "title": f"复习错题：{item.subject}",
        "question_text": item.question_text,
        "mastery_level": item.mastery_level,
        "mastery_status": status,
        "next_review": item.next_review.strftime("%Y-%m-%d"),
        "reason": _reason_text(item, status, today),
        "estimated_minutes": _estimated_minutes(item, status),
        "priority": "high" if status == "unmastered" else ("medium" if status == "fuzzy" else "low"),
        "due_date": today + timedelta(days=max(interval - 1, 0)),
    }


def _task_to_dict(task: ReviewTask, wrong: WrongQuestion | None) -> dict:
    status = _normalize_status(wrong) if wrong else "unmastered"
    return {
        "id": task.id,
        "subject": task.subject,
        "title": task.title,
        "reason": task.reason,
        "estimated_minutes": task.estimated_minutes,
        "priority": task.priority,
        "status": task.status,
        "task_date": task.task_date.strftime("%Y-%m-%d"),
        "due_date": task.due_date.strftime("%Y-%m-%d"),
        "question_text": task.content,
        "source_wrong_question_id": task.source_wrong_question_id,
        "mode_key": task.mode_key,
        "mastery_status": status,
        "mastery_status_label": STATUS_LABEL.get(status, "还不熟"),
        "next_review": wrong.next_review.strftime("%Y-%m-%d") if wrong else task.due_date.strftime("%Y-%m-%d"),
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _fetch_or_create_today_tasks(db: Session, user: User, today: date) -> list[ReviewTask]:
    existing_tasks = (
        db.query(ReviewTask)
        .filter(ReviewTask.user_id == user.id, ReviewTask.task_date == today)
        .order_by(ReviewTask.created_at.asc())
        .all()
    )
    if existing_tasks:
        return existing_tasks

    wrong_items = (
        db.query(WrongQuestion)
        .filter(WrongQuestion.user_id == user.id)
        .order_by(WrongQuestion.next_review.asc(), WrongQuestion.mastery_level.asc(), WrongQuestion.wrong_count.desc())
        .all()
    )
    due_items = [item for item in wrong_items if item.next_review <= today]
    upcoming_items = [item for item in wrong_items if today < item.next_review <= today + timedelta(days=2)]

    selected_items = due_items[:8]
    if len(selected_items) < 3:
        for item in upcoming_items:
            if item not in selected_items:
                selected_items.append(item)
            if len(selected_items) >= 3:
                break

    created: list[ReviewTask] = []
    for item in selected_items:
        payload = _build_task_payload(item, today)
        task = ReviewTask(
            user_id=user.id,
            source_wrong_question_id=payload["source_wrong_question_id"],
            source_chat_id=payload["source_chat_id"],
            subject=payload["subject"],
            mode_key=payload["mode_key"],
            title=payload["title"],
            reason=payload["reason"],
            content=payload["question_text"],
            estimated_minutes=payload["estimated_minutes"],
            priority=payload["priority"],
            status="pending",
            task_date=today,
            due_date=payload["due_date"],
            updated_at=datetime.utcnow(),
        )
        db.add(task)
        created.append(task)

    if created:
        db.commit()
        for task in created:
            db.refresh(task)
    return created


def _apply_review_result(item: WrongQuestion, remembered: bool) -> None:
    status = _sync_status(item)
    if remembered:
        next_status = {"unmastered": "fuzzy", "fuzzy": "mastered", "mastered": "mastered"}[status]
        item.correct_count += 1
    else:
        next_status = {"mastered": "fuzzy", "fuzzy": "unmastered", "unmastered": "unmastered"}[status]
        item.wrong_count += 1

    item.mastery_status = next_status
    item.mastery_level = {"unmastered": 0, "fuzzy": 2, "mastered": 4}[next_status]
    item.review_count += 1
    item.last_review_at = datetime.utcnow()
    item.next_review = date.today() + timedelta(days=_next_interval_days(item, next_status))


@router.get("/today")
def today_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    tasks = _fetch_or_create_today_tasks(db, user, today)
    items = []
    total_minutes = 0
    for task in tasks:
        wrong = db.query(WrongQuestion).filter(WrongQuestion.id == task.source_wrong_question_id).first()
        item = _task_to_dict(task, wrong)
        items.append(item)
        total_minutes += task.estimated_minutes or 0

    return ok(
        {
            "date": today.strftime("%Y-%m-%d"),
            "summary": {
                "task_count": len(items),
                "total_estimated_minutes": total_minutes,
            },
            "tasks": items,
        }
    )


@router.post("/today/{task_id}/complete")
def complete_today_task(
    task_id: int,
    payload: ReviewCompleteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id, ReviewTask.user_id == user.id).first()
    if not task:
        return err(1002, "任务不存在")

    wrong = (
        db.query(WrongQuestion)
        .filter(WrongQuestion.id == task.source_wrong_question_id, WrongQuestion.user_id == user.id)
        .first()
    )
    if not wrong:
        return err(1002, "错题不存在")

    _apply_review_result(wrong, payload.remembered)
    task.status = "done"
    task.updated_at = datetime.utcnow()
    db.add(StudyLog(user_id=user.id, subject=task.subject, duration=task.estimated_minutes or 5))
    db.commit()

    return ok(
        {
            "task_id": task.id,
            "status": task.status,
            "mastery_level": wrong.mastery_level,
            "mastery_status": wrong.mastery_status,
            "next_review": wrong.next_review.strftime("%Y-%m-%d"),
        },
        "复习已完成",
    )
