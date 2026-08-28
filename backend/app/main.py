from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import User, Session as DBSession, Usage, Chat
from .security import hash_password, verify_password, create_session, current_user, COOKIE
from .config import (
    SESSION_SECRET, ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD,
    FRONTEND_ORIGIN, SESSION_HOURS, COOKIE_SECURE
)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

class Register(Credentials):
    name: str = Field(min_length=1, max_length=120)

class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    role: str | None = None
    disabled: bool | None = None

class ChatPayload(BaseModel):
    title: str = Field(default="New Chat", max_length=200)
    data: str = Field(default="{}", max_length=500000)

def iso(dt):
    return dt.isoformat() if dt else None

def require_admin(request: Request, db: Session):
    u, s = current_user(request, db)
    if u.role != "admin":
        raise HTTPException(403, "Admin access required")
    return u, s

def set_cookie(response: Response, session):
    seconds = max(1, int((session.expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        COOKIE, session.id, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", max_age=seconds, path="/"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = next(get_db())
    try:
        # Create the configured admin only when all required credentials are supplied.
        if ADMIN_EMAIL and ADMIN_PASSWORD:
            admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
            if not admin:
                db.add(User(
                    name=ADMIN_USERNAME, email=ADMIN_EMAIL,
                    password_hash=hash_password(ADMIN_PASSWORD), role="admin"
                ))
                db.commit()
            elif admin.role != "admin":
                admin.role = "admin"
                db.commit()
    finally:
        db.close()
    yield

app = FastAPI(title="TANMAY GenAI Pro Max API", version="2.0.0", lifespan=lifespan)

origins = ["*"] if FRONTEND_ORIGIN == "*" else [
    x.strip() for x in FRONTEND_ORIGIN.split(",") if x.strip()
]
app.add_middleware(
    CORSMiddleware, allow_origins=origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

@app.get("/")
def root():
    return {"service": "TANMAY GenAI Pro Max API", "version": "2.0.0", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {"ok": True, "service": "TANMAY GenAI Pro Max", "version": "2.0.0"}

@app.post("/api/auth/register")
def register(body: Register, response: Response, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    u = User(name=name, email=email, password_hash=hash_password(body.password), role="user")
    db.add(u); db.commit(); db.refresh(u)
    s = create_session(db, u); set_cookie(response, s)
    return {"user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role},
            "session": {"expires_at": iso(s.expires_at)}}

@app.post("/api/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    u = db.scalar(select(User).where(User.email == email))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if u.disabled:
        raise HTTPException(403, "Account disabled")
    s = create_session(db, u); set_cookie(response, s)
    return {"user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role},
            "session": {"expires_at": iso(s.expires_at)}}

@app.get("/api/auth/me")
def me(request: Request, db: Session = Depends(get_db)):
    u, s = current_user(request, db)
    return {"user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role},
            "session": {"expires_at": iso(s.expires_at)}}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    sid = request.cookies.get(COOKIE)
    if sid:
        s = db.get(DBSession, sid)
        if s:
            s.revoked = True
            db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}

@app.get("/api/admin/me")
def admin_me(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    return {"ok": True}

@app.get("/api/admin/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    now = datetime.now(timezone.utc)
    total = db.scalar(select(func.count(User.id))) or 0
    active = db.scalar(select(func.count(DBSession.id)).where(
        DBSession.revoked == False, DBSession.expires_at > now
    )) or 0
    chats = db.scalar(select(func.count(Chat.id))) or 0
    requests = db.scalar(select(func.count(Usage.id))) or 0
    disabled = db.scalar(select(func.count(User.id)).where(User.disabled == True)) or 0
    admins = db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0
    users = db.scalars(select(User).order_by(User.id.desc())).all()
    rows = []
    for x in users:
        ac = db.scalar(select(func.count(DBSession.id)).where(
            DBSession.user_id == x.id, DBSession.revoked == False,
            DBSession.expires_at > now
        )) or 0
        rows.append({
            "id": x.id, "name": x.name, "email": x.email, "role": x.role,
            "disabled": x.disabled, "created_at": iso(x.created_at),
            "active_sessions": ac
        })
    return {
        "stats": {"users": total, "active_sessions": active, "chats": chats,
                  "api_requests": requests, "disabled_users": disabled, "admins": admins},
        "users": rows
    }

@app.patch("/api/admin/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, db: Session = Depends(get_db)):
    admin, _ = require_admin(request, db)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id and body.disabled is True:
        raise HTTPException(400, "You cannot disable your own account")
    if body.role is not None:
        if body.role not in {"user", "admin"}:
            raise HTTPException(400, "Role must be user or admin")
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(400, "You cannot remove your own admin role")
        u.role = body.role
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Name cannot be empty")
        u.name = name
    if body.disabled is not None:
        u.disabled = body.disabled
        if body.disabled:
            db.query(DBSession).filter(DBSession.user_id == u.id).update({"revoked": True})
    db.commit()
    return {"ok": True}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin, _ = require_admin(request, db)
    if user_id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    db.delete(u); db.commit()
    return {"ok": True}

@app.post("/api/admin/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    count = db.query(DBSession).filter(DBSession.user_id == user_id, DBSession.revoked == False).update({"revoked": True})
    db.commit()
    return {"ok": True, "revoked": count}

@app.get("/api/admin/usage")
def admin_usage(request: Request, db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=500)):
    require_admin(request, db)
    rows = db.execute(
        select(Usage, User.email).join(User, User.id == Usage.user_id)
        .order_by(Usage.id.desc()).limit(limit)
    ).all()
    return [{"id": u.id, "user_id": u.user_id, "email": email, "kind": u.kind,
             "latency_ms": u.latency_ms, "created_at": iso(u.created_at)}
            for u, email in rows]

@app.post("/api/usage")
def usage(kind: str = Query(..., min_length=1, max_length=40),
          request: Request = None, db: Session = Depends(get_db)):
    u, _ = current_user(request, db)
    db.add(Usage(user_id=u.id, kind=kind))
    db.commit()
    return {"ok": True}

@app.get("/api/chats")
def chats(request: Request, db: Session = Depends(get_db)):
    u, _ = current_user(request, db)
    return [{"id": c.id, "title": c.title, "data": c.data, "updated_at": iso(c.updated_at)}
            for c in db.scalars(select(Chat).where(Chat.user_id == u.id).order_by(Chat.updated_at.desc())).all()]

@app.post("/api/chats")
def create_chat(body: ChatPayload, request: Request, db: Session = Depends(get_db)):
    u, _ = current_user(request, db)
    c = Chat(user_id=u.id, title=body.title.strip() or "New Chat", data=body.data)
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "title": c.title, "data": c.data, "updated_at": iso(c.updated_at)}

@app.put("/api/chats/{chat_id}")
def update_chat(chat_id: int, body: ChatPayload, request: Request, db: Session = Depends(get_db)):
    u, _ = current_user(request, db)
    c = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == u.id))
    if not c:
        raise HTTPException(404, "Chat not found")
    c.title = body.title.strip() or "New Chat"
    c.data = body.data
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, request: Request, db: Session = Depends(get_db)):
    u, _ = current_user(request, db)
    c = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == u.id))
    if not c:
        raise HTTPException(404, "Chat not found")
    db.delete(c); db.commit()
    return {"ok": True}
