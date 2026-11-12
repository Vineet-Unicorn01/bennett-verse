import os
import secrets
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, EmailStr
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Text, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bennett_verse.db")
JWT_SECRET = os.getenv("JWT_SECRET", "replace-this-with-a-long-random-secret")
JWT_ALGORITHM = "HS256"
JWT_HOURS = int(os.getenv("JWT_HOURS", "24"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-this-demo-token")
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "bennett.edu.in").lower().strip()
OTP_MINUTES = int(os.getenv("OTP_MINUTES", "10"))
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
DEV_SHOW_OTP = os.getenv("DEV_SHOW_OTP", "false").lower() == "true"

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(500))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EmailCode(Base):
    __tablename__ = "email_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    code_hash: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Story(Base):
    __tablename__ = "stories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contributor: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)
# Small additive migration for existing SQLite development databases.
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "stories" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("stories")}
        if "featured" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE stories ADD COLUMN featured BOOLEAN NOT NULL DEFAULT 0"))
app = FastAPI(title="Bennett Verse API", version="2.0.0",
              description="Independent student-led university newsroom API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)

class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class StoryCreate(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    summary: str = Field(min_length=20, max_length=1000)
    source_url: Optional[str] = Field(default=None, max_length=500)

class StoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=5, max_length=120)
    category: Optional[str] = Field(default=None, min_length=2, max_length=40)
    summary: Optional[str] = Field(default=None, min_length=20, max_length=1000)
    source_url: Optional[str] = Field(default=None, max_length=500)
    featured: Optional[bool] = None

class StoryOut(BaseModel):
    id: int
    title: str
    category: str
    summary: str
    source_url: Optional[str]
    contributor: str
    approved: bool
    featured: bool = False
    created_at: datetime
    class Config:
        from_attributes = True

def send_verification_email(to_email: str, code: str):
    if not RESEND_API_KEY or not EMAIL_FROM:
        if DEV_SHOW_OTP:
            print(f"[DEVELOPMENT ONLY] Bennett Verse verification code for {to_email}: {code}")
            return
        raise HTTPException(status_code=503, detail="Email delivery is not configured. Please contact the site administrator.")

    payload = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": "Verify your Bennett Verse account",
        "text": (
            f"Your Bennett Verse verification code is {code}.\\n\\n"
            f"It expires in {OTP_MINUTES} minutes. If you did not request this, ignore this email.\\n\\n"
            "Bennett Verse is an independent student-led media platform and is not an official university service."
        ),
    }
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise HTTPException(status_code=502, detail="Email provider rejected the verification email.")
    except urllib.error.HTTPError:
        raise HTTPException(status_code=502, detail="Email provider could not send the verification email.")
    except urllib.error.URLError:
        raise HTTPException(status_code=502, detail="Could not reach the email provider.")

def create_access_token(user: User):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "email": user.email, "name": user.full_name,
               "iat": now, "exp": now + timedelta(hours=JWT_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                     db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Please sign in again.")
    user = db.get(User, user_id)
    if not user or not user.email_verified:
        raise HTTPException(status_code=401, detail="Account not found or email not verified.")
    return user

def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid editorial admin token.")
    return True

@app.get("/")
def root():
    return {"name": "Bennett Verse API", "version": "2.0.0", "status": "running", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    domain = email.rsplit("@", 1)[-1]
    if ALLOWED_EMAIL_DOMAIN and domain != ALLOWED_EMAIL_DOMAIN:
        raise HTTPException(status_code=400, detail=f"Please use your @{ALLOWED_EMAIL_DOMAIN} email address.")
    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please sign in.")
    if existing:
        existing.full_name = payload.full_name.strip()
        existing.password_hash = password_hash.hash(payload.password)
        user = existing
    else:
        user = User(email=email, full_name=payload.full_name.strip(),
                    password_hash=password_hash.hash(payload.password), email_verified=False)
        db.add(user)
    # Invalidate older codes and limit the active code to one per email.
    db.query(EmailCode).filter(EmailCode.email == email).delete()
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(email=email, code_hash=password_hash.hash(code),
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_MINUTES), attempts=0))
    db.commit()
    send_verification_email(email, code)
    return {"message": "Verification code sent. Check your inbox.", "email": email,
            "expires_in_minutes": OTP_MINUTES, "development_code": code if DEV_SHOW_OTP else None}

@app.post("/api/auth/verify")
def verify_email(payload: VerifyIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    record = db.query(EmailCode).filter(EmailCode.email == email).order_by(EmailCode.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=400, detail="No active verification code. Register again.")
    now = datetime.now(timezone.utc)
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        db.delete(record); db.commit()
        raise HTTPException(status_code=400, detail="Verification code expired. Register again.")
    if record.attempts >= 5:
        db.delete(record); db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts. Register again for a new code.")
    record.attempts += 1
    if not password_hash.verify(payload.code, record.code_hash):
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code.")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Registration not found. Please register again.")
    user.email_verified = True
    db.delete(record)
    db.commit()
    return {"message": "Email verified. You can now sign in."}

@app.post("/api/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not password_hash.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")
    return {"access_token": create_access_token(user), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}

@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "email_verified": user.email_verified}

@app.get("/api/stories", response_model=list[StoryOut])
def published_stories(category: Optional[str] = None, q: Optional[str] = None,
                      db: Session = Depends(get_db)):
    query = db.query(Story).filter(Story.approved.is_(True))
    if category and category.lower() != "all":
        query = query.filter(Story.category == category)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter((Story.title.ilike(term)) | (Story.summary.ilike(term)))
    return query.order_by(Story.featured.desc(), Story.created_at.desc()).all()

@app.post("/api/stories", response_model=StoryOut, status_code=201)
def submit_story(payload: StoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    story = Story(**payload.model_dump(), contributor=user.full_name, user_id=user.id, approved=False)
    db.add(story); db.commit(); db.refresh(story)
    return story

@app.get("/api/admin/pending", response_model=list[StoryOut])
def pending_stories(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(Story).filter(Story.approved.is_(False)).order_by(Story.created_at.desc()).all()

@app.get("/api/admin/stats")
def editorial_stats(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    total = db.query(Story).count()
    published = db.query(Story).filter(Story.approved.is_(True)).count()
    pending = db.query(Story).filter(Story.approved.is_(False)).count()
    featured = db.query(Story).filter(Story.approved.is_(True), Story.featured.is_(True)).count()
    contributors = db.query(User).count()
    return {"total_stories": total, "published_stories": published,
            "pending_stories": pending, "featured_stories": featured,
            "registered_contributors": contributors}

@app.get("/api/admin/stories", response_model=list[StoryOut])
def editorial_stories(status: str = "all", _: bool = Depends(require_admin),
                      db: Session = Depends(get_db)):
    query = db.query(Story)
    if status == "published":
        query = query.filter(Story.approved.is_(True))
    elif status == "pending":
        query = query.filter(Story.approved.is_(False))
    return query.order_by(Story.created_at.desc()).all()

@app.get("/api/admin/contributors")
def editorial_contributors(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for user in users:
        count = db.query(Story).filter(Story.user_id == user.id).count()
        result.append({"id": user.id, "full_name": user.full_name, "email": user.email,
                       "email_verified": user.email_verified, "story_count": count,
                       "joined_at": user.created_at})
    return result

@app.patch("/api/admin/stories/{story_id}", response_model=StoryOut)
def update_story(story_id: int, payload: StoryUpdate,
                 _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(story, key, value)
    db.commit()
    db.refresh(story)
    return story

@app.post("/api/admin/stories/{story_id}/feature", response_model=StoryOut)
def toggle_feature(story_id: int, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.approved:
        raise HTTPException(status_code=400, detail="Approve a story before featuring it.")
    story.featured = not story.featured
    db.commit()
    db.refresh(story)
    return story

@app.post("/api/admin/stories/{story_id}/approve", response_model=StoryOut)
def approve_story(story_id: int, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story: raise HTTPException(status_code=404, detail="Story not found")
    story.approved = True; db.commit(); db.refresh(story)
    return story

@app.delete("/api/admin/stories/{story_id}", status_code=204)
def reject_story(story_id: int, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if not story: raise HTTPException(status_code=404, detail="Story not found")
    db.delete(story); db.commit()
