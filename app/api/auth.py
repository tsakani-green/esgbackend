# backend/app/api/auth.py
# Email sending TEMPORARILY DISABLED for debugging

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import os
import logging

from app.core.config import settings
from app.core.database import db
# ❌ EMAIL DISABLED
# from app.services.email_service import send_activation_email

try:
    from bson import ObjectId
except Exception:
    ObjectId = None

logger = logging.getLogger(__name__)
router = APIRouter()

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def to_object_id(value: str):
    if ObjectId is None:
        raise RuntimeError("bson.ObjectId not available")
    return ObjectId(value)

def now_utc():
    return datetime.now(timezone.utc)

# Password hashing
from passlib.context import CryptContext
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return hashed and _pwd_context.verify(plain, hashed)

# JWT config
JWT_SECRET = settings.SECRET_KEY
JWT_ALG = "HS256"
ACCESS_EXPIRE_HOURS = int(settings.ACCESS_TOKEN_EXPIRE_HOURS or 24)

def create_access_token(user_id: str, username: str, role: str):
    exp = now_utc() + timedelta(hours=ACCESS_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# -------------------------------------------------------------------
# Dependency
# -------------------------------------------------------------------
async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth.split(" ", 1)[1]
    payload = decode_access_token(token)

    user = await db.users.find_one({"_id": to_object_id(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
        "is_active": user.get("is_active", False),
        "company": user.get("company", ""),
    }

# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------
class SignupIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    company: str | None = None

class LoginIn(BaseModel):
    username: str
    password: str

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@router.post("/signup")
async def signup(payload: SignupIn):
    username = payload.username.strip()
    email = payload.email.lower().strip()

    existing = await db.users.find_one({
        "$or": [{"username": username}, {"email": email}]
    })
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_doc = {
        "username": username,
        "email": email,
        "full_name": payload.full_name.strip(),
        "company": (payload.company or "").strip(),
        "hashed_password": hash_password(payload.password),
        "role": "user",
        "is_active": True,  # ✅ AUTO-ACTIVATE
        "created_at": now_utc(),
    }

    await db.users.insert_one(user_doc)

    # ❌ EMAIL DISABLED
    # send_activation_email(...)

    return {
        "success": True,
        "message": "Account created (email temporarily disabled). You can log in.",
    }

@router.post("/login")
async def login(request: Request):
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
    else:
        form = await request.form()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    user = await db.users.find_one({"username": username})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account inactive")

    token = create_access_token(
        user_id=str(user["_id"]),
        username=user["username"],
        role=user.get("role", "user"),
    )

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "role": user.get("role"),
        },
    }

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
