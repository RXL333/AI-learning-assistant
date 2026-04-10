from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatHistory, StudyLog, User, WrongQuestion
from ..utils import err, ok

router = APIRouter(prefix="/user", tags=["user"])


class UserUpdateIn(BaseModel):
    username: str | None = None
    email: EmailStr | None = None


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return ok(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.strftime("%Y-%m-%d"),
        }
    )


@router.put("/profile")
def update_profile(payload: UserUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.username is not None:
        username = payload.username.strip()
        if not username:
            return err(1002, "用户名不能为空")
        exists = db.query(User).filter(User.username == username, User.id != user.id).first()
        if exists:
            return err(1002, "用户名已存在")
        user.username = username

    if payload.email is not None:
        email = payload.email.strip().lower()
        exists = db.query(User).filter(User.email == email, User.id != user.id).first()
        if exists:
            return err(1002, "邮箱已存在")
        user.email = email

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return err(1002, "用户名或邮箱已存在")
    return ok({"username": user.username, "email": user.email}, "更新成功")


@router.get("/stats")
def user_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    study_time = db.query(func.coalesce(func.sum(StudyLog.duration), 0)).filter(StudyLog.user_id == user.id).scalar() or 0
    question_count = db.query(func.count(ChatHistory.id)).filter(ChatHistory.user_id == user.id).scalar() or 0
    wrong_count = db.query(func.count(WrongQuestion.id)).filter(WrongQuestion.user_id == user.id).scalar() or 0
    today_question_count = (
        db.query(func.count(ChatHistory.id))
        .filter(ChatHistory.user_id == user.id, func.date(ChatHistory.created_at) == date.today().isoformat())
        .scalar()
        or 0
    )
    return ok(
        {
            "study_time": int(study_time),
            "question_count": int(question_count),
            "wrong_count": int(wrong_count),
            "today_question_count": int(today_question_count),
        }
    )


@router.get("/activity-calendar")
def activity_calendar(month: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if month:
        current = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    else:
        current = date.today().replace(day=1)

    next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    rows = (
        db.query(ChatHistory.created_at)
        .filter(
            ChatHistory.user_id == user.id,
            ChatHistory.created_at >= datetime.combine(current, datetime.min.time()),
            ChatHistory.created_at < datetime.combine(next_month, datetime.min.time()),
        )
        .all()
    )

    counts = defaultdict(int)
    for (created_at,) in rows:
        counts[created_at.date().isoformat()] += 1

    total_days = (next_month - current).days
    days = []
    for offset in range(total_days):
        day = current + timedelta(days=offset)
        days.append({"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)})

    return ok(
        {
            "month": current.strftime("%Y-%m"),
            "days": days,
        }
    )
