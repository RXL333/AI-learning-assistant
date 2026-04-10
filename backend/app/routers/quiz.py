import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import QuizSession, StudyLog, User, WrongQuestion
from ..services.ai_service import generate_quiz as ai_generate_quiz
from ..utils import err, ok

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizGenerateIn(BaseModel):
    subject: str
    topic: str
    count: int = 5
    mode_key: str = "general"


class QuizSubmitIn(BaseModel):
    quiz_id: int
    answers: list[str]


@router.post("/generate")
async def generate_quiz(payload: QuizGenerateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = max(1, min(payload.count, 20))
    questions = await ai_generate_quiz(payload.subject, payload.topic, count, payload.mode_key)
    session = QuizSession(
        user_id=user.id,
        subject=payload.subject,
        mode_key=payload.mode_key,
        topic=payload.topic,
        questions_json=json.dumps(questions, ensure_ascii=False),
    )
    db.add(session)
    db.add(StudyLog(user_id=user.id, subject=payload.subject, duration=2))
    db.commit()
    db.refresh(session)
    return ok({"quiz_id": session.id, "questions": questions})


@router.get("/history")
def quiz_history(page: int = 1, page_size: int = 10, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user.id)
        .order_by(QuizSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = [
        {
            "id": item.id,
            "subject": item.subject,
            "mode_key": item.mode_key,
            "topic": item.topic,
            "score": item.score,
            "correct_rate": item.correct_rate,
            "question_count": len(json.loads(item.questions_json)),
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed": item.score is not None,
        }
        for item in items
    ]
    return ok(data)


@router.get("/{quiz_id}")
def quiz_detail(quiz_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(QuizSession).filter(QuizSession.id == quiz_id, QuizSession.user_id == user.id).first()
    if not item:
        return err(1002, "试卷不存在")
    return ok(
        {
            "id": item.id,
            "subject": item.subject,
            "mode_key": item.mode_key,
            "topic": item.topic,
            "score": item.score,
            "correct_rate": item.correct_rate,
            "questions": json.loads(item.questions_json),
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@router.delete("/{quiz_id}")
def delete_quiz(quiz_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(QuizSession).filter(QuizSession.id == quiz_id, QuizSession.user_id == user.id).first()
    if not item:
        return err(1002, "试卷不存在")
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id, WrongQuestion.source_quiz_id == quiz_id).update(
        {WrongQuestion.source_quiz_id: None},
        synchronize_session=False,
    )
    db.delete(item)
    db.commit()
    return ok({}, "试卷已删除")


@router.post("/submit")
def submit_quiz(payload: QuizSubmitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(QuizSession).filter(QuizSession.id == payload.quiz_id, QuizSession.user_id == user.id).first()
    if not session:
        return err(1002, "试卷不存在")

    questions = json.loads(session.questions_json)
    total = len(questions)
    if total == 0:
        return err(1002, "试卷为空")

    correct = 0
    wrong_added = 0
    for i, q in enumerate(questions):
        if i < len(payload.answers) and payload.answers[i].upper() == str(q.get("answer", "")).upper():
            correct += 1
        else:
            options = q.get("options")
            if not isinstance(options, list):
                options = []
            db.add(
                WrongQuestion(
                    user_id=user.id,
                    source_quiz_id=session.id,
                    subject=session.subject,
                    mode_key=session.mode_key,
                    question_text=q.get("question", "未命名题目"),
                    options_json=json.dumps([str(option).strip() for option in options if str(option).strip()], ensure_ascii=False),
                    correct_answer=str(q.get("answer", "")).strip(),
                    ai_analysis=q.get("analysis", ""),
                    mastery_level=0,
                    mastery_status="unmastered",
                    review_count=0,
                    wrong_count=1,
                    correct_count=0,
                )
            )
            wrong_added += 1

    correct_rate = correct / total
    score = int(correct_rate * 100)
    session.score = score
    session.correct_rate = correct_rate
    db.add(StudyLog(user_id=user.id, subject=session.subject, duration=max(1, total)))
    db.commit()
    return ok({"score": score, "correct_rate": round(correct_rate, 2), "wrong_added": wrong_added})
