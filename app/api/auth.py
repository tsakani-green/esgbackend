# backend/app/api/auth.py
# NOTE: Uses Mongo (motor) via app.core.database.db
# Provides: /signup, /activate, /login, /me
# Login accepts BOTH:
#  - application/x-www-form-urlencoded (OAuth2 style)
#  - application/json: { "username": "...", "password": "..." }

from fastapi import APIRouter, HTTPException, Request, Depends
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

# Password hashing (reuse a single context)
from passlib.context import CryptContext
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return _pwd_context.verify(plain, hashed)

# JWT config
JWT_SECRET = settings.SECRET_KEY
JWT_ALG = "HS256"

ACCESS_EXPIRE_HOURS = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_HOURS", 24) or 24)

# Activation token config
ACTIVATION_EXPIRE_HOURS = int(os.getenv("ACTIVATION_TOKEN_EXPIRE_HOURS", "24"))
FRONTEND_URL = ((getattr(settings, "FRONTEND_URL", "") or os.getenv("FRONTEND_URL", "")) or "").rstrip("/")

def make_activation_token(user_id: str, email: str) -> str:
    exp = now_utc() + timedelta(hours=ACTIVATION_EXPIRE_HOURS)
    payload = {
        "type": "email_activation",
        "sub": user_id,
        "email": email,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def verify_activation_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "email_activation":
            raise HTTPException(status_code=400, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired activation token")

def create_access_token(user_id: str, username: str, role: str = "user") -> str:
    exp = now_utc() + timedelta(hours=ACCESS_EXPIRE_HOURS)
    payload = {"sub": user_id, "username": username, "role": role, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def _normalize_user(user: dict) -> dict:
    """Return a consistent user shape for frontend consumption."""
    return {
        "id": str(user.get("_id")) if user.get("_id") is not None else None,
        "username": user.get("username"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
        "is_active": user.get("is_active", False),
        "company": user.get("company", ""),
        "created_at": user.get("created_at"),
    }

def _get_bearer_token_from_request(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    auth = auth.strip()
    if not auth:
        return ""
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""

# -------------------------------------------------------------------
# Auth Dependency (FIXES Render import error)
# -------------------------------------------------------------------

async def get_current_user(request: Request) -> dict:
    """
    Dependency used across routes to authenticate a user via JWT:
      Authorization: Bearer <token>
    Returns the Mongo user document (dict).
    """
    token = _get_bearer_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # fetch user
    try:
        user = await db.users.find_one({"_id": to_object_id(user_id)})
    except Exception:
        user = None

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account not active")

    return user

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
        "is_active": False,
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
        # OPTIONAL:
        # "auto_login_token": create_access_token(user_id=str(user["_id"]), username=user["username"], role=user.get("role","user")),
    }

@router.post("/login")
async def login(request: Request):
    """
    Accepts BOTH:
      - Form encoded: username=...&password=...
      - JSON: { "username": "...", "password": "..." }
    """
    content_type = (request.headers.get("content-type") or "").lower()

    username = None
    password = None

    # 1) Form (OAuth2 style)
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = (form.get("username") or "").strip()
        password = (form.get("password") or "")

    # 2) JSON
    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "")

    # 3) Fallback attempt
    else:
        try:
            body = await request.json()
            username = (body.get("username") or "").strip()
            password = (body.get("password") or "")
        except Exception:
            try:
                form = await request.form()
                username = (form.get("username") or "").strip()
                password = (form.get("password") or "")
            except Exception:
                username = ""
                password = ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Please activate your account via the email link.")

    if not verify_password(password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(
        user_id=str(user["_id"]),
        username=user.get("username", username),
        role=user.get("role", "user"),
    )

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": _normalize_user(user),
    }

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """
    Frontend calls this endpoint to fetch user profile.
    """
    return _normalize_user(current_user)
