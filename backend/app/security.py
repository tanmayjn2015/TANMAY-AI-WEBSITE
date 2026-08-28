from datetime import datetime, timezone, timedelta
import secrets
from passlib.context import CryptContext
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from .models import Session as DBSession, User
from .config import SESSION_HOURS

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
COOKIE = "chaya_session"

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd.verify(password, password_hash)
    except Exception:
        return False

def create_session(db: Session, user: User):
    sid = secrets.token_urlsafe(32)
    created = datetime.now(timezone.utc)
    # Admin sessions are longer, but still revocable from the admin panel.
    hours = 24 * 30 if user.role == "admin" else SESSION_HOURS
    s = DBSession(
        id=sid, user_id=user.id, created_at=created,
        expires_at=created + timedelta(hours=hours), revoked=False
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

def current_user(request: Request, db: Session):
    sid = request.cookies.get(COOKIE)
    if not sid:
        raise HTTPException(401, "Authentication required")
    s = db.get(DBSession, sid)
    if not s or s.revoked:
        raise HTTPException(401, "Session expired")
    if s.expires_at <= datetime.now(timezone.utc):
        s.revoked = True
        db.commit()
        raise HTTPException(401, "Session expired")
    u = db.get(User, s.user_id)
    if not u or u.disabled:
        raise HTTPException(403, "Account disabled")
    return u, s
