import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatHistory, ReviewTask, User, WrongQuestion
from ..services.ai_service import normalize_structured_chat
from ..utils import err, ok

router = APIRouter(prefix="/history", tags=["history"])

MAX_HISTORY_DAYS = 90
STATUS_LABELS = {
    "unmastered": "还不熟",
    "fuzzy": "有点模糊",
    "mastered": "基本掌握",
}
TYPE_LABELS = {
    "chat": "问答",
    "wrong": "错题",
    "review": "复习",
}


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fmt_dt(value: datetime | None) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _snippet(text: str | None, limit: int = 72) -> str:
    content = (text or "").strip().replace("\n", " ")
    if len(content) <= limit:
        return content
    return content[: limit - 1].rstrip() + "…"


def _extract_keywords(structured: dict, subject: str, fallback_text: str = "") -> list[str]:
    keywords: list[str] = []

    topic = str(structured.get("topic", "")).strip()
    if topic:
        keywords.append(topic)

    for item in structured.get("knowledge_tags") or []:
        value = str(item).strip()
        if value and value not in keywords:
            keywords.append(value)

    if not keywords and subject.strip():
        keywords.append(subject.strip())

    if not keywords and fallback_text.strip():
        keywords.append(_snippet(fallback_text, 18))

    return keywords[:5]


def _bump_keyword_bucket(bucket: dict, keywords: list[str], *, weight: int, source_type: str, record_date: str) -> None:
    for keyword in keywords:
        key = keyword.strip()
        if not key:
            continue
        item = bucket.setdefault(
            key,
            {
                "name": key,
                "score": 0,
                "chat_count": 0,
                "wrong_count": 0,
                "review_count": 0,
                "last_seen": record_date,
            },
        )
        item["score"] += weight
        item[f"{source_type}_count"] += 1
        if record_date > item["last_seen"]:
            item["last_seen"] = record_date


def _finalize_keyword_bucket(bucket: dict) -> list[dict]:
    result = list(bucket.values())
    result.sort(key=lambda item: (item["score"], item["last_seen"]), reverse=True)
    return result


def _chat_record(record: ChatHistory) -> tuple[dict, list[str]]:
    structured = normalize_structured_chat(
        question=record.question,
        subject=record.subject,
        answer=record.answer,
        structured=_safe_json_loads(record.structured_json),
    )
    keywords = _extract_keywords(structured, record.subject, record.question)
    return (
        {
            "id": f"chat-{record.id}",
            "type": "chat",
            "type_label": TYPE_LABELS["chat"],
            "title": structured.get("topic", "").strip() or record.subject or "学习问答",
            "summary": _snippet(record.question, 80),
            "meta": _snippet(record.answer, 88),
            "subject": record.subject,
            "created_at": _fmt_dt(record.created_at),
        },
        keywords,
    )


def _wrong_record(record: WrongQuestion, source_chat: ChatHistory | None) -> tuple[dict, list[str]]:
    structured = {}
    if source_chat is not None:
        structured = normalize_structured_chat(
            question=source_chat.question,
            subject=source_chat.subject,
            answer=source_chat.answer,
            structured=_safe_json_loads(source_chat.structured_json),
        )
    keywords = _extract_keywords(structured, record.subject, record.question_text)
    mastery_status = record.mastery_status or "unmastered"
    return (
        {
            "id": f"wrong-{record.id}",
            "type": "wrong",
            "type_label": TYPE_LABELS["wrong"],
            "title": record.subject or "错题记录",
            "summary": _snippet(record.question_text, 88),
            "meta": f"{STATUS_LABELS.get(mastery_status, '还不熟')} · 下次复习 {record.next_review.strftime('%Y-%m-%d')}",
            "subject": record.subject,
            "created_at": _fmt_dt(record.created_at),
        },
        keywords,
    )


def _review_record(task: ReviewTask, wrong: WrongQuestion | None, source_chat: ChatHistory | None) -> tuple[dict, list[str]]:
    structured = {}
    if source_chat is not None:
        structured = normalize_structured_chat(
            question=source_chat.question,
            subject=source_chat.subject,
            answer=source_chat.answer,
            structured=_safe_json_loads(source_chat.structured_json),
        )
    keywords = _extract_keywords(structured, task.subject, task.content or task.title)
    status_text = "已完成" if task.status == "done" else "待完成"
    return (
        {
            "id": f"review-{task.id}",
            "type": "review",
            "type_label": TYPE_LABELS["review"],
            "title": task.title or task.subject or "复习任务",
            "summary": _snippet(task.reason or task.content, 88),
            "meta": f"{status_text} · 预计 {task.estimated_minutes or 0} 分钟",
            "subject": task.subject,
            "created_at": task.task_date.strftime("%Y-%m-%d"),
        },
        keywords,
    )


def _empty_day(day: date) -> dict:
    return {
        "date": day.isoformat(),
        "is_today": day == date.today(),
        "chat_count": 0,
        "wrong_count": 0,
        "review_count": 0,
        "items": [],
        "_weak_bucket": {},
    }


def _build_date_range(start_date: date, end_date: date) -> list[date]:
    total_days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=offset) for offset in range(max(total_days, 0))]


def _build_history_payload(db: Session, user: User, start_date: date, end_date: date) -> dict:
    days = _build_date_range(start_date, end_date)
    day_map = {day.isoformat(): _empty_day(day) for day in days}

    chat_rows = (
        db.query(ChatHistory)
        .filter(
            ChatHistory.user_id == user.id,
            ChatHistory.created_at >= datetime.combine(start_date, datetime.min.time()),
            ChatHistory.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        .order_by(ChatHistory.created_at.asc(), ChatHistory.id.asc())
        .all()
    )
    wrong_rows = (
        db.query(WrongQuestion)
        .filter(
            WrongQuestion.user_id == user.id,
            WrongQuestion.created_at >= datetime.combine(start_date, datetime.min.time()),
            WrongQuestion.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        .order_by(WrongQuestion.created_at.asc(), WrongQuestion.id.asc())
        .all()
    )
    review_rows = (
        db.query(ReviewTask)
        .filter(
            ReviewTask.user_id == user.id,
            ReviewTask.task_date >= start_date,
            ReviewTask.task_date <= end_date,
        )
        .order_by(ReviewTask.task_date.asc(), ReviewTask.created_at.asc(), ReviewTask.id.asc())
        .all()
    )

    chat_ids = {item.id for item in chat_rows}
    chat_ids.update(item.source_chat_id for item in wrong_rows if item.source_chat_id)
    chat_ids.update(item.source_chat_id for item in review_rows if item.source_chat_id)

    wrong_ids = {item.id for item in wrong_rows}
    wrong_ids.update(item.source_wrong_question_id for item in review_rows if item.source_wrong_question_id)

    source_chats: dict[int, ChatHistory] = {}
    if chat_ids:
        for item in db.query(ChatHistory).filter(ChatHistory.user_id == user.id, ChatHistory.id.in_(sorted(chat_ids))).all():
            source_chats[item.id] = item

    source_wrongs: dict[int, WrongQuestion] = {}
    if wrong_ids:
        for item in db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id, WrongQuestion.id.in_(sorted(wrong_ids))).all():
            source_wrongs[item.id] = item

    overall_weak_bucket: dict = {}
    totals = {
        "chat_count": 0,
        "wrong_count": 0,
        "review_count": 0,
    }

    for chat in chat_rows:
        created_date = chat.created_at.date().isoformat()
        item, keywords = _chat_record(chat)
        day = day_map[created_date]
        day["chat_count"] += 1
        totals["chat_count"] += 1
        day["items"].append(item)
        _bump_keyword_bucket(day["_weak_bucket"], keywords, weight=1, source_type="chat", record_date=created_date)
        _bump_keyword_bucket(overall_weak_bucket, keywords, weight=1, source_type="chat", record_date=created_date)

    for wrong in wrong_rows:
        created_date = wrong.created_at.date().isoformat()
        item, keywords = _wrong_record(wrong, source_chats.get(wrong.source_chat_id) if wrong.source_chat_id else None)
        day = day_map[created_date]
        day["wrong_count"] += 1
        totals["wrong_count"] += 1
        day["items"].append(item)
        _bump_keyword_bucket(day["_weak_bucket"], keywords, weight=3, source_type="wrong", record_date=created_date)
        _bump_keyword_bucket(overall_weak_bucket, keywords, weight=3, source_type="wrong", record_date=created_date)

    for task in review_rows:
        task_date = task.task_date.isoformat()
        item, keywords = _review_record(
            task,
            source_wrongs.get(task.source_wrong_question_id),
            source_chats.get(task.source_chat_id) if task.source_chat_id else None,
        )
        day = day_map[task_date]
        day["review_count"] += 1
        totals["review_count"] += 1
        day["items"].append(item)
        _bump_keyword_bucket(day["_weak_bucket"], keywords, weight=2, source_type="review", record_date=task_date)
        _bump_keyword_bucket(overall_weak_bucket, keywords, weight=2, source_type="review", record_date=task_date)

    day_items = []
    for day in day_map.values():
        day["items"].sort(key=lambda item: item["created_at"], reverse=True)
        day["weak_points"] = [item["name"] for item in _finalize_keyword_bucket(day.pop("_weak_bucket"))[:3]]
        day_items.append(day)

    day_items.sort(key=lambda item: item["date"], reverse=True)

    return {
        "range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": len(days),
        },
        "summary": {
            "chat_count": totals["chat_count"],
            "wrong_count": totals["wrong_count"],
            "review_count": totals["review_count"],
        },
        "weak_points": [item["name"] for item in _finalize_keyword_bucket(overall_weak_bucket)[:3]],
        "days": day_items,
    }


@router.get("/daily")
def daily_history(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 14,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if days < 1:
        days = 1
    if days > MAX_HISTORY_DAYS:
        days = MAX_HISTORY_DAYS

    if start_date:
        parsed_start = _parse_date(start_date)
        if parsed_start is None:
            return err(1002, "开始日期格式不正确，请使用 YYYY-MM-DD")
    else:
        parsed_start = None

    if end_date:
        parsed_end = _parse_date(end_date)
        if parsed_end is None:
            return err(1002, "结束日期格式不正确，请使用 YYYY-MM-DD")
    else:
        parsed_end = None

    if parsed_start and parsed_end:
        if parsed_start > parsed_end:
            return err(1002, "开始日期不能晚于结束日期")
        start = parsed_start
        end = parsed_end
    elif parsed_start:
        start = parsed_start
        end = start + timedelta(days=days - 1)
    elif parsed_end:
        end = parsed_end
        start = end - timedelta(days=days - 1)
    else:
        end = date.today()
        start = end - timedelta(days=days - 1)

    if (end - start).days + 1 > MAX_HISTORY_DAYS:
        start = end - timedelta(days=MAX_HISTORY_DAYS - 1)

    return ok(_build_history_payload(db, user, start, end))
