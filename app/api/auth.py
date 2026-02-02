# backend/app/api/auth.py

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field, model_validator
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

# Password hashing (shared context)
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
    exp = now_utc() + timedelta(hours=ACCESS_EXPIRE_HOURS)
    payload = {"sub": user_id, "username": username, "role": role, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    return parts[1].strip()

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
    # ✅ Accept BOTH username and email so the frontend can send either one without 422
    username: str | None = None
    email: EmailStr | None = None
    # optional alternate key some frontends use:
    usernameOrEmail: str | None = Field(default=None)
    password: str

    @model_validator(mode="after")
    def validate_identifier(self):
        if not (self.username or self.email or self.usernameOrEmail):
            raise ValueError("Provide username or email")
        return self

class TokenOut(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"
    # ✅ add `token` alias so older frontend code that stores `token` keeps working
    token: str
    user: dict

# -------------------------------------------------------------------
# Auth dependencies (fixes Render ImportError)
# -------------------------------------------------------------------

async def get_current_user(authorization: str = Depends(lambda: None)):
    """
    Usage:
      from app.api.auth import get_current_user
      @router.get("/me")
      async def me(user=Depends(get_current_user)): ...
    """
    # FastAPI can't inject raw headers via lambda(None) reliably,
    # so we instead fetch via request headers in a small wrapper below.
    raise RuntimeError("Use get_current_user_dep (see below)")

from fastapi import Request

async def get_current_user_dep(request: Request):
    token = _extract_bearer_token(request.headers.get("Authorization"))
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await db.users.find_one({"_id": to_object_id(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive. Please activate your account.")

    # normalize id to string
    user["id"] = str(user["_id"])
    user.pop("_id", None)
    user.pop("hashed_password", None)
    return user

async def admin_required(user=Depends(get_current_user_dep)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user

# ✅ Backwards-compatible export so imports like `from app.api.auth import get_current_user` work:
get_current_user = get_current_user_dep

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
    }

@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn):
    identifier = (
        (payload.username or "").strip()
        or (payload.email.lower().strip() if payload.email else "")
        or (payload.usernameOrEmail or "").strip()
    )

    if not identifier:
        raise HTTPException(status_code=422, detail="username/email is required")

    # ✅ allow login via username OR email
    user = await db.users.find_one({"$or": [{"username": identifier}, {"email": identifier.lower()}]})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Please activate your account via the email link.")

    if not verify_password(payload.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    token = create_access_token(
        user_id=str(user["_id"]),
        username=user.get("username", identifier),
        role=user.get("role", "user"),
    )

    user_out = {
        "id": str(user["_id"]),
        "username": user.get("username"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "user"),
    }

    return {
        "success": True,
        "access_token": token,
        "token": token,  # ✅ keeps your localStorage('token') logic working
        "token_type": "bearer",
        "user": user_out,
    }
