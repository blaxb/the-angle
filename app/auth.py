from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi import Request
from sqlmodel import Session, select
from .models import User
from .settings import settings

# Prefer argon2 (no 72-byte bcrypt limit, modern default)
pwd = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

serializer = URLSafeTimedSerializer(settings.app_secret)

COOKIE_NAME = "theangle_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days

def hash_password(p: str) -> str:
    # Argon2 handles long passwords fine
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def make_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})

def read_session_token(token: str) -> int | None:
    try:
        data = serializer.loads(token, max_age=MAX_AGE_SECONDS)
        return int(data["user_id"])
    except (BadSignature, Exception):
        return None

def get_current_user(request: Request, session: Session) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if not user_id:
        return None
    return session.exec(select(User).where(User.id == user_id)).first()

