from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import create_access_token, hash_password, verify_password
from ..utils import err, ok

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str
    password: str
    email: EmailStr


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.strip().lower()
    password = payload.password

    if not username or not password.strip():
        return err(1002, "用户名和密码不能为空")

    exists = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if exists:
        return err(1002, "用户名或邮箱已存在")

    user = User(username=username, password_hash=hash_password(password), email=email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return err(1002, "用户名或邮箱已存在")

    db.refresh(user)
    return ok({"user_id": user.id, "created_at": date.today().isoformat()}, "注册成功")


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password

    if not username or not password:
        return err(1002, "用户名或密码错误")

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return err(1002, "用户名或密码错误")

    token = create_access_token(user.id)
    return ok(
        {
            "token": token,
            "user": {"id": user.id, "username": user.username},
        },
        "登录成功",
    )
