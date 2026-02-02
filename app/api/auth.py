# backend/app/api/auth.py
# Mongo (motor) via app.core.database.db
# Email activation + JWT login + dependency helpers (get_current_user)

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import os
import logging
from typing import Optional, Any, Dict

from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials

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
    # If value is already an ObjectId, keep it
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))

def now_utc():
    return datetime.now(timezone.utc)

# Password hashing (keep simple; replace with your existing utils if you already have them elsewhere)
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)

# -------------------------------------------------------------------
# JWT config
# -------------------------------------------------------------------

JWT_SECRET = settings.SECRET_KEY
JWT_ALG = "HS256"

ACCESS_EXPIRE_HOURS = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_HOURS", 24) or 24)

ACTIVATE_SECRET = settings.SECRET_KEY
ACTIVATE_ALG = "HS256"
EXPIRE_HOURS = int(os.getenv("ACTIVATION_TOKEN_EXPIRE_HOURS", "24"))

FRONTEND_URL = (
    (getattr(settings, "FRONTEND_URL", "") or os.getenv("FRONTEND_URL", "")) or ""
).rstrip("/")

def create_access_token(user_id: str, username: str, role: str = "user") -> str:
    exp = now_utc() + timedelta(hours=ACCESS_EXPIRE_HOURS)
    payload = {"type": "access", "sub": user_id, "username": username, "role": role, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

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

# -------------------------------------------------------------------
# Auth dependencies (IMPORTANT: fixes Render crash)
# -------------------------------------------------------------------

# Works with Swagger "Authorize" for OAuth2 password bearer style
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Also supports Authorization: Bearer <token> robustly (some clients prefer this)
http_bearer = HTTPBearer(auto_error=False)

async def _extract_token(
    oauth_token: str = Depends(oauth2_scheme),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> str:
    """
    Prefer explicit Authorization header if present; otherwise use oauth2 token.
    """
    if bearer and bearer.scheme.lower() == "bearer" and bearer.credentials:
        return bearer.credentials
    if oauth_token:
        return oauth_token
    raise HTTPException(status_code=401, detail="Not authenticated")

async def get_current_user(token: str = Depends(_extract_token)) -> Dict[str, Any]:
    """
    ✅ This is the function other routers import.
    Returns the DB user document (dict).
    """
    data = decode_access_token(token)
    user_id = data.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await db.users.find_one({"_id": to_object_id(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # attach token claims (useful for debugging/role checks)
    user["_token"] = data
    return user

async def get_current_active_user(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account not activated.")
    return user

def require_admin(user: Dict[str, Any] = Depends(get_current_active_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class SignupIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    company: Optional[str] = None

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

    if not username or not email or not full_name:
        raise HTTPException(status_code=400, detail="Missing required fields")

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
        "is_active": False,   # MUST activate via email
        "created_at": now_utc(),
    }

    ins = await db.users.insert_one(user_doc)
    user_id = str(ins.inserted_id)

    token = make_activation_token(user_id=user_id, email=email)
    activation_link = f"{FRONTEND_URL}/activate?token={token}" if FRONTEND_URL else f"/activate?token={token}"

    activation_link_return = None
    try:
        # If your service is async, change to: await send_activation_email(...)
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
        # OPTIONAL auto login:
        # "auto_login_token": create_access_token(user_id=str(user["_id"]), username=user["username"], role=user.get("role", "user")),
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

    token = create_access_token(
        user_id=str(user["_id"]),
        username=user.get("username", ""),
        role=user.get("role", "user"),
    )

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

# -------------------------------------------------------------------
# Optional: current user endpoint (useful for frontend debug)
# -------------------------------------------------------------------
@router.get("/me")
async def me(user: Dict[str, Any] = Depends(get_current_active_user)):
    return {
        "success": True,
        "user": {
            "id": str(user["_id"]),
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "role": user.get("role", "user"),
            "company": user.get("company", ""),
        },
    }
