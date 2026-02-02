# backend/app/api/auth.py
# NOTE: This file assumes you are using Mongo (motor) via app.core.database.db
# and that you have password hashing available. If your hashing utilities differ,
# replace hash_password / verify_password with your existing functions.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import os
import logging

from app.core.config import settings
from app.core.database import db
from app.services.email_service import send_activation_email

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
        raise RuntimeError("bson.ObjectId not available. Install pymongo/bson.")
    return ObjectId(value)

def now_utc():
    return datetime.now(timezone.utc)

# Replace these with your existing hashing utils if you already have them
def hash_password(password: str) -> str:
    # If you already use passlib CryptContext elsewhere, import and use it here.
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain, hashed)

# Activation token config
ACTIVATE_SECRET = settings.SECRET_KEY
ACTIVATE_ALG = "HS256"
EXPIRE_HOURS = int(os.getenv("ACTIVATION_TOKEN_EXPIRE_HOURS", "24"))
FRONTEND_URL = ((getattr(settings, "FRONTEND_URL", "") or os.getenv("FRONTEND_URL", "")) or "").rstrip("/")

def make_activation_token(user_id: str, email: str) -> str:
    exp = now_utc() + timedelta(hours=EXPIRE_HOURS)
    payload = {
        "type": "email_activation",
        "sub": user_id,
        "email": email,
        "exp": exp,
    }
    return jwt.encode(payload, ACTIVATE_SECRET, algorithm=ACTIVATE_ALG)

def verify_activation_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, ACTIVATE_SECRET, algorithms=[ACTIVATE_ALG])
        if payload.get("type") != "email_activation":
            raise HTTPException(status_code=400, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired activation token")

def create_access_token(user_id: str, username: str, role: str = "user") -> str:
    # If you already have JWT issuance elsewhere, swap this out.
    exp = now_utc() + timedelta(hours=int(getattr(settings, "ACCESS_TOKEN_EXPIRE_HOURS", 24) or 24))
    payload = {"sub": user_id, "username": username, "role": role, "exp": exp}
    return jwt.encode(payload, ACTIVATE_SECRET, algorithm=ACTIVATE_ALG)

# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class SignupIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    company: str | None = None

class ActivateIn(BaseModel):
    token: str

class LoginIn(BaseModel):
    username: str
    password: str

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.post("/signup")
async def signup(payload: SignupIn):
    # basic normalization
    username = payload.username.strip()
    email = payload.email.strip().lower()
    full_name = payload.full_name.strip()
    company = (payload.company or "").strip()

    existing = await db.users.find_one({"$or": [{"email": email}, {"username": username}]})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_doc = {
        "username": username,
        "email": email,
        "full_name": full_name,
        "company": company,
        "hashed_password": hash_password(payload.password),
        "role": "user",
        "is_active": False,               # MUST activate via email
        "created_at": now_utc(),
    }

    ins = await db.users.insert_one(user_doc)
    user_id = str(ins.inserted_id)

    token = make_activation_token(user_id=user_id, email=email)
    activation_link = f"{FRONTEND_URL}/activate?token={token}" if FRONTEND_URL else f"/activate?token={token}"

    activation_link_return = None
    try:
        send_activation_email(email, full_name, activation_link)
    except Exception as e:
        # Dev fallback: return activation link so you can still activate without SMTP
        logger.warning(f"Activation email not sent (fallback to activation_link): {e}")
        activation_link_return = activation_link

    return {
        "success": True,
        "message": "Account created. Please check your email to activate your account.",
        "activation_link": activation_link_return,
    }

@router.post("/activate")
async def activate(body: ActivateIn):
    data = verify_activation_token(body.token)
    user_id = data["sub"]

    user = await db.users.find_one({"_id": to_object_id(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("is_active") is True:
        return {
            "success": True,
            "message": "Account already activated.",
            "user": {
                "username": user.get("username"),
                "email": user.get("email"),
                "full_name": user.get("full_name"),
            },
        }

    await db.users.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"is_active": True, "activated_at": now_utc()}},
    )

    user = await db.users.find_one({"_id": to_object_id(user_id)})

    return {
        "success": True,
        "message": "Account activated successfully. You can now log in.",
        "user": {
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
        },
        # OPTIONAL: if you want auto-login after activation:
        # "auto_login_token": create_access_token(user_id=str(user["_id"]), username=user["username"], role=user.get("role","user")),
    }

@router.post("/login")
async def login(payload: LoginIn):
    username = payload.username.strip()

    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Please activate your account via the email link.")

    if not verify_password(payload.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user_id=str(user["_id"]), username=user["username"], role=user.get("role", "user"))

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "role": user.get("role", "user"),
        },
    }
