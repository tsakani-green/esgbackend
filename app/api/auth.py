# backend/app/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from typing import Optional
from bson import ObjectId

from app.core.config import settings
from app.core.database import get_db

import secrets
import hashlib
import asyncio

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
JWT_ALGORITHM = "HS256"


# ---------------- Models ----------------
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str


class User(BaseModel):
    id: Optional[str] = None
    username: str
    email: str
    full_name: str
    role: str
    company: Optional[str] = None
    disabled: bool = False
    portfolio_access: Optional[list] = []
    status: Optional[str] = "active"


class UserInDB(User):
    hashed_password: str
    id: str
    portfolio_access: Optional[list] = []


class UserPublic(BaseModel):
    id: Optional[str] = None
    username: str
    email: str
    full_name: str
    role: str
    company: Optional[str] = None
    disabled: bool = False
    portfolio_access: Optional[list] = []
    status: Optional[str] = "active"


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    company: Optional[str] = None
    portfolio_access: Optional[list] = []
    status: Optional[str] = "active"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: str


# ---------------- Token helpers ----------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


async def send_password_reset_email(email: str, reset_token: str) -> bool:
    try:
        reset_link = f"{(settings.FRONTEND_URL or '').rstrip('/')}/reset-password?token={reset_token}"
        print(f"Password reset link for {email}: {reset_link}")
        return True
    except Exception as e:
        print(f"Error sending reset email: {str(e)}")
        return False


# ---------------- Auth helpers ----------------
async def authenticate_user(db, username: str, password: str):
    try:
        try:
            user = await asyncio.wait_for(
                db.users.find_one({"$or": [{"username": username}, {"email": username}]}),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("database-timeout")

        if user is None:
            return False

        stored = user.get("hashed_password", "") or ""
        verified = False

        try:
            if stored.startswith("$2") or stored.startswith("$argon") or stored.startswith("$pbkdf2$"):
                verified = pwd_context.verify(password, stored)
            else:
                from string import hexdigits

                if len(stored) == 64 and all(c in hexdigits for c in stored.lower()):
                    verified = hashlib.sha256(password.encode()).hexdigest() == stored
                else:
                    verified = password == stored
        except Exception as e:
            print(f"Password verification error for {username}: {e}")
            verified = False

        if not verified:
            return False

        user_dict = dict(user)
        user_dict["id"] = str(user["_id"])
        user_dict["portfolio_access"] = user_dict.get("portfolio_access", [])
        user_dict["company"] = user_dict.get("company", None)
        user_dict["disabled"] = user_dict.get("disabled", False)
        user_dict["status"] = user_dict.get("status", "active")

        return UserInDB(**user_dict)

    except RuntimeError as re:
        print(f"authenticate_user: database error: {re}")
        raise
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False


async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.users.find_one({"$or": [{"username": username}, {"email": username}]})
    if user is None:
        raise credentials_exception

    user_dict = dict(user)
    user_dict["id"] = str(user["_id"])
    user_dict["portfolio_access"] = user_dict.get("portfolio_access", [])
    user_dict["company"] = user_dict.get("company", None)
    user_dict["disabled"] = user_dict.get("disabled", False)
    user_dict["status"] = user_dict.get("status", "active")

    return UserInDB(**user_dict)


# ---------------- /me ----------------
@router.get("/me", response_model=UserPublic)
async def me(current_user: UserInDB = Depends(get_current_user)):
    return UserPublic(**current_user.model_dump(exclude={"hashed_password"}))


# ---------------- Signup / Login ----------------
@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db=Depends(get_db)):
    existing_user = await db.users.find_one(
        {"$or": [{"username": user_data.username}, {"email": user_data.email}]}
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    hashed_password = hashlib.sha256(user_data.password.encode()).hexdigest()

    user_dict = {
        "username": user_data.username,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": hashed_password,
        "role": "client",
        "company": user_data.company,
        "portfolio_access": user_data.portfolio_access or [],
        "disabled": False,
        "status": "active",
        "created_at": datetime.utcnow(),
        "activated_at": datetime.utcnow(),
    }

    result = await db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user_data.username, "role": "client"},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id,
        "role": "client",
    }


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    try:
        user = await asyncio.wait_for(
            authenticate_user(db, form_data.username, form_data.password),
            timeout=6.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="Database timeout; try again later")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database unavailable; try again later")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role,
    }


# ---------------- Password reset ----------------
@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest, db=Depends(get_db)):
    user = await db.users.find_one({"email": request.email})
    if not user:
        return {"message": "If the email exists, a reset link has been sent"}

    reset_token = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)

    reset_token_data = {
        "token": reset_token,
        "user_id": str(user["_id"]),
        "email": request.email,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow(),
    }
    await db.password_reset_tokens.insert_one(reset_token_data)

    email_sent = await send_password_reset_email(request.email, reset_token)
    if email_sent:
        return {"message": "Password reset link sent (check server logs)"}

    raise HTTPException(status_code=500, detail="Failed to send reset email")


@router.post("/reset-password")
async def reset_password(request: PasswordReset, db=Depends(get_db)):
    reset_token_data = await db.password_reset_tokens.find_one(
        {"token": request.token, "used": False, "expires_at": {"$gt": datetime.utcnow()}}
    )
    if not reset_token_data:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = await db.users.find_one({"_id": ObjectId(reset_token_data["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = hashlib.sha256(request.new_password.encode()).hexdigest()

    await db.users.update_one(
        {"_id": ObjectId(reset_token_data["user_id"])},
        {"$set": {"hashed_password": hashed_password}},
    )
    await db.password_reset_tokens.update_one(
        {"_id": reset_token_data["_id"]},
        {"$set": {"used": True}},
    )

    return {"message": "Password reset successful"}
