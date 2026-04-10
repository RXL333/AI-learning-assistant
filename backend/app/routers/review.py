from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatHistory, QuizSession, StudyLog, User, WrongQuestion
from ..utils import err, ok

router = APIRouter(prefix="/review", tags=["review"])


class ReviewCompleteIn(BaseModel):
    review_id: int


def _safe_date_text(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _level_gap(level: int) -> int:
    return max(0, 5 - level)


def _build_ai_prompt(subject: str, question_text: str, analysis: str) -> str:
    analysis_text = analysis or "暂无讲解"
    return "\n".join(
        [
            f"请带着我继续复习这道 {subject} 题。",
            f"题目：{question_text}",
            f"已有讲解：{analysis_text}",
            "请按下面 3 点回答：",
            "1. 这题为什么容易错",
            "2. 我现在最该先补哪一步",
            "3. 最后给我一个一分钟自测问题",
        ]
    )


def _build_subject_priority(subject: str, stats: dict) -> dict:
    due_count = stats["due_count"]
    wrong_count = stats["wrong_count"]
    avg_mastery = round(stats["mastery_total"] / wrong_count, 1) if wrong_count else 0
    recent_asks = stats["recent_asks"]
    low_score_quizzes = stats["low_score_quizzes"]
    priority_score = due_count * 4 + wrong_count * 2 + low_score_quizzes * 3 + max(0, 3 - avg_mastery)

    if due_count >= 3 or avg_mastery <= 1.5:
        priority = "高"
    elif due_count >= 1 or low_score_quizzes >= 1:
        priority = "中"
    else:
        priority = "低"

    if due_count >= 3:
        reason = f"{subject} 当前有 {due_count} 项内容已经到复习时间，短期遗忘风险最高。"
    elif low_score_quizzes >= 1:
        reason = f"{subject} 最近练习分数偏低，建议先补方法再继续刷题。"
    elif recent_asks >= 3:
        reason = f"{subject} 最近提问较多，说明这部分理解链路还不够稳。"
    else:
        reason = f"{subject} 还有 {wrong_count} 条错题沉淀，建议继续巩固。"

    return {
        "subject": subject,
        "priority": priority,
        "priority_score": priority_score,
        "reason": reason,
        "wrong_count": wrong_count,
        "due_count": due_count,
        "avg_mastery": avg_mastery,
        "recent_asks": recent_asks,
        "low_score_quizzes": low_score_quizzes,
    }


@router.get("")
def get_review_center(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    week_end = today + timedelta(days=6)
    recent_7 = today - timedelta(days=6)
    recent_14 = today - timedelta(days=13)

    wrong_items = (
        db.query(WrongQuestion)
        .filter(WrongQuestion.user_id == user.id)
        .order_by(WrongQuestion.next_review.asc(), WrongQuestion.mastery_level.asc(), WrongQuestion.created_at.desc())
        .all()
    )
    due_items = [item for item in wrong_items if item.next_review <= today]
    upcoming_items = [item for item in wrong_items if today < item.next_review <= week_end]

    chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id, func.date(ChatHistory.created_at) >= recent_14.isoformat())
        .order_by(ChatHistory.created_at.desc())
        .all()
    )
    quizzes = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user.id)
        .order_by(QuizSession.created_at.desc())
        .limit(20)
        .all()
    )
    study_logs = (
        db.query(StudyLog)
        .filter(StudyLog.user_id == user.id, StudyLog.study_date >= recent_7)
        .order_by(StudyLog.study_date.desc())
        .all()
    )

    subject_stats: dict[str, dict] = defaultdict(
        lambda: {
            "wrong_count": 0,
            "due_count": 0,
            "mastery_total": 0,
            "recent_asks": 0,
            "low_score_quizzes": 0,
        }
    )

    for item in wrong_items:
        subject = item.subject or "通用"
        subject_stats[subject]["wrong_count"] += 1
        subject_stats[subject]["mastery_total"] += item.mastery_level
        if item.next_review <= today:
            subject_stats[subject]["due_count"] += 1

    for item in chats:
        subject = item.subject or "通用"
        subject_stats[subject]["recent_asks"] += 1

    for item in quizzes:
        subject = item.subject or "通用"
        if item.score is None or item.score < 70:
            subject_stats[subject]["low_score_quizzes"] += 1

    weak_spots = sorted(
        [_build_subject_priority(subject, stats) for subject, stats in subject_stats.items()],
        key=lambda item: item["priority_score"],
        reverse=True,
    )[:3]

    primary_subject = weak_spots[0]["subject"] if weak_spots else (wrong_items[0].subject if wrong_items else "通用")
    study_minutes_7d = int(sum(item.duration for item in study_logs))

    today_tasks = []
    for index, item in enumerate(due_items[:5], start=1):
        priority_label = "立即复习" if item.next_review < today or item.mastery_level <= 1 else "今天完成"
        today_tasks.append(
            {
                "id": item.id,
                "title": f"任务 {index}：先补 {item.subject}",
                "subject": item.subject,
                "priority": priority_label,
                "reason": (
                    f"这道题安排在 { _safe_date_text(item.next_review) } 复习，"
                    f"当前掌握度 {item.mastery_level}/5。"
                ),
                "question_text": item.question_text,
                "explanation": item.ai_analysis or "当前暂无讲解。",
                "mastery_level": item.mastery_level,
                "next_review": _safe_date_text(item.next_review),
                "eta_minutes": 8 + _level_gap(item.mastery_level) * 2,
                "can_complete": True,
                "ai_prompt": _build_ai_prompt(item.subject, item.question_text, item.ai_analysis),
            }
        )

    if not today_tasks and weak_spots:
        focus = weak_spots[0]
        today_tasks.append(
            {
                "id": None,
                "title": f"今天先做 {focus['subject']} 的概念回补",
                "subject": focus["subject"],
                "priority": "建议优先",
                "reason": focus["reason"],
                "question_text": f"先回顾 {focus['subject']} 的核心概念，再做 1 道代表题。",
                "explanation": "建议先回顾定义和易错点，再找一道代表题验证是否真正理解。",
                "mastery_level": None,
                "next_review": _safe_date_text(today),
                "eta_minutes": 15,
                "can_complete": False,
                "ai_prompt": "\n".join(
                    [
                        f"请带着我复习今天的 {focus['subject']}。",
                        f"当前问题：{focus['reason']}",
                        "请告诉我先看什么、怎么练、怎么做快速自测。",
                    ]
                ),
            }
        )

    week_route = []
    route_subjects = [item["subject"] for item in weak_spots] or [primary_subject]
    for offset in range(min(5, len(route_subjects) + 2)):
        day = today + timedelta(days=offset)
        subject = route_subjects[offset % len(route_subjects)]
        if offset == 0:
            theme = "先补到期内容"
        elif offset in (1, 2):
            theme = "补概念再做变式"
        else:
            theme = "做一次小测检查"
        week_route.append(
            {
                "date": _safe_date_text(day),
                "label": "今天" if offset == 0 else f"第 {offset + 1} 天",
                "subject": subject,
                "theme": theme,
                "task_count": max(1, min(3, len([item for item in upcoming_items + due_items if item.subject == subject]) or 1)),
            }
        )

    summary = {
        "today_focus": primary_subject,
        "today_task_count": len(today_tasks),
        "due_now_count": len(due_items),
        "study_minutes_7d": study_minutes_7d,
        "weak_subject_count": len(weak_spots),
    }

    return ok(
        {
            "generated_at": _safe_date_text(today),
            "summary": summary,
            "today_tasks": today_tasks,
            "week_route": week_route,
            "weak_spots": weak_spots,
        }
    )


@router.post("/complete")
def complete_review(payload: ReviewCompleteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(WrongQuestion).filter(WrongQuestion.id == payload.review_id, WrongQuestion.user_id == user.id).first()
    if not item:
        return err(1002, "复习任务不存在")

    item.mastery_level = min(item.mastery_level + 1, 5)
    item.mastery_status = "mastered" if item.mastery_level >= 4 else ("fuzzy" if item.mastery_level >= 2 else "unmastered")
    item.review_count += 1
    item.correct_count += 1
    item.last_review_at = datetime.utcnow()
    item.next_review = date.today() + timedelta(days={1: 1, 2: 3, 3: 7, 4: 14, 5: 30}.get(item.mastery_level, 1))
    db.add(StudyLog(user_id=user.id, subject=item.subject, duration=2))
    db.commit()
    return ok({"level": item.mastery_level, "next_review": item.next_review.strftime("%Y-%m-%d")}, "完成复习")
