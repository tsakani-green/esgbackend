# backend/app/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core.config import settings
from app.core.database import get_db
from bson import ObjectId
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import asyncio
import time
from pathlib import Path

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# IMPORTANT: tokenUrl should match your router prefix + endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# -------------------------------------------------------------------
# Email sending function
# -------------------------------------------------------------------
async def send_activation_email(to_email: str, user_name: str, activation_link: str):
    try:
        subject = "Welcome to AfricaESG.AI - Activate Your Account"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
          <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2E7D32;">🌍 Welcome to AfricaESG.AI</h1>
            <p style="font-size: 16px;">Hello {user_name},</p>
            <p style="font-size: 16px;">Activate your account:</p>
            <p><a href="{activation_link}">{activation_link}</a></p>
          </div>
        </body>
        </html>
        """

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        message["To"] = to_email

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        # If SMTP creds are not configured, write the email to disk for local/dev testing
        if not settings.EMAIL_USERNAME or not settings.EMAIL_PASSWORD:
            try:
                dump_dir = Path(settings.UPLOAD_DIR) / "sent_emails"
                dump_dir.mkdir(parents=True, exist_ok=True)
                filename = dump_dir / f"activation-{to_email.replace('@', '_at_')}-{int(time.time())}.html"
                with open(filename, "w", encoding="utf-8") as fh:
                    fh.write(html_content)
                print(f"Email credentials not set; activation email written to: {filename}")
                return True
            except Exception as e:
                print(f"Failed to write activation email to disk: {e}")
                return False

        # Send email via SMTP
        try:
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
            server.starttls()
            server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
            server.send_message(message)
            server.quit()

            print(f"Activation email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"Error sending activation email: {str(e)}")
            # In development, don't raise; surface the failure via logs
            if settings.ENVIRONMENT == "development":
                return False
            raise

    except Exception as e:
        print(f"send_activation_email failed: {e}")
        if settings.ENVIRONMENT == "development":
            return False
        raise


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


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


# -------------------------------------------------------------------
# Token helpers
# -------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_reset_token():
    return secrets.token_urlsafe(32)


async def send_password_reset_email(email: str, reset_token: str):
    try:
        # IMPORTANT: use FRONTEND_URL (Render static site) not localhost
        reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"
        print(f"Password reset link for {email}: {reset_link}")

        # If you want to send email for real, configure EMAIL_USERNAME/PASSWORD in Render
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


# -------------------------------------------------------------------
# Auth helpers
# -------------------------------------------------------------------
async def authenticate_user(db, username: str, password: str):
    """
    Authenticate against MongoDB. Supports both legacy sha256 hashes (dev seed)
    and bcrypt/passlib hashes (production). Returns UserInDB on success, False
    on invalid credentials. Raises on database connectivity errors so callers
    can decide whether to fall back to demo behavior.
    """
    try:
        # Prefer a real DB lookup; surface DB connectivity errors explicitly
        try:
            user = await asyncio.wait_for(
                db.users.find_one({"$or": [{"username": username}, {"email": username}]}),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            # timed out talking to the DB (treat as unavailable)
            raise RuntimeError("database-timeout")

        if user is None:
            # No DB record found — allow demo fallback only when DB is reachable but user missing
            demo_users = {
                "admin": {
                    "password": "admin123",
                    "email": "admin@example.com",
                    "full_name": "Administrator",
                    "role": "admin",
                    "company": "AfricaESG.AI",
                    "portfolio_access": ["dube-trade-port", "bertha-house"],
                },
            }
            demo = demo_users.get(username)
            if demo and hashlib.sha256(password.encode()).hexdigest() == hashlib.sha256(demo["password"].encode()).hexdigest():
                return UserInDB(
                    id=f"demo-{username}",
                    username=username,
                    email=demo["email"],
                    full_name=demo["full_name"],
                    role=demo["role"],
                    hashed_password=hashlib.sha256(demo["password"].encode()).hexdigest(),
                    company=demo["company"],
                    portfolio_access=demo["portfolio_access"],
                    disabled=False,
                )
            return False

        # At this point we have a DB user — verify password with best-effort detection
        stored = user.get("hashed_password", "") or ""

        verified = False
        try:
            # bcrypt / passlib encoded (starts with $2b$ or $2a$ etc.)
            if stored.startswith("$2") or stored.startswith("$argon") or stored.startswith("$pbkdf2$"):
                verified = pwd_context.verify(password, stored)
                print(f"authenticate_user: used passlib verify for {username}")
            else:
                # fallback: legacy sha256 hex digest
                from string import hexdigits
                if len(stored) == 64 and all(c in hexdigits for c in stored.lower()):
                    verified = hashlib.sha256(password.encode()).hexdigest() == stored
                    print(f"authenticate_user: used sha256 verify for {username}")
                else:
                    # last-resort: direct comparison (not recommended)
                    verified = password == stored
                    print(f"authenticate_user: used direct-string-compare for {username}")
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

        return UserInDB(**user_dict)

    except RuntimeError as re:
        # Surface DB connectivity as a distinct error
        print(f"authenticate_user: database error: {re}")
        raise
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False


async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    if not settings.AUTH_ENABLED:
        return UserInDB(
            id="test-user",
            username="test-user",
            email="test@example.com",
            full_name="Test User",
            role="client",
            hashed_password="dummy",
            disabled=False,
            portfolio_access=["dube-trade-port", "bertha-house"],
        )

    # IMPORTANT: oauth2_scheme returns the *raw Authorization value* only if using OAuth2PasswordBearer.
    # With auto_error=False, token may be None (good).
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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception

    try:
        user = await db.users.find_one({"$or": [{"username": token_data.username}, {"email": token_data.username}]})
    except Exception as e:
        print(f"Database lookup failed in get_current_user: {e}")
        if getattr(settings, "ENVIRONMENT", "production") == "development":
            demo_map = {
                "admin": {
                    "role": "admin",
                    "full_name": "Administrator",
                    "email": "admin@example.com",
                    "portfolio_access": ["dube-trade-port", "bertha-house"],
                },
            }
            info = demo_map.get(token_data.username)
            if info or token_data.username.startswith("demo-") or token_data.username == "test-user":
                info = info or {
                    "role": "client",
                    "full_name": token_data.username,
                    "email": f"{token_data.username}@example.com",
                    "portfolio_access": [],
                }
                return UserInDB(
                    id=f"demo-{token_data.username}",
                    username=token_data.username,
                    email=info.get("email"),
                    full_name=info.get("full_name"),
                    role=info.get("role", "client"),
                    hashed_password="",
                    disabled=False,
                    portfolio_access=info.get("portfolio_access", []),
                )
        raise HTTPException(status_code=503, detail="Database unavailable; try again later")

    if user is None:
        raise credentials_exception

    user_dict = dict(user)
    user_dict["id"] = str(user["_id"])
    user_dict["portfolio_access"] = user_dict.get("portfolio_access", [])
    user_dict["company"] = user_dict.get("company", None)
    user_dict["disabled"] = user_dict.get("disabled", False)

    return UserInDB(**user_dict)


# -------------------------------------------------------------------
# /me endpoint (returns current user) - use DI so token is injected correctly
# -------------------------------------------------------------------
@router.get("/me")
async def me(current_user: UserInDB = Depends(get_current_user)):
    """Return the authenticated user's profile (401 when not authenticated)."""
    return current_user


# -------------------------------------------------------------------
# Optional debug helper
# -------------------------------------------------------------------
@router.get("/auth-enabled")
async def auth_enabled():
    return {
        "AUTH_ENABLED": getattr(settings, "AUTH_ENABLED", True),
        "ENVIRONMENT": getattr(settings, "ENVIRONMENT", "production"),
    }


@router.get('/debug-token')
async def debug_token(token: str = Depends(oauth2_scheme)):
    """Development-only helper: decode the incoming bearer token and return its payload.
    Returns 403 outside development to avoid exposing token internals in production.
    """
    if getattr(settings, 'ENVIRONMENT', '') != 'development':
        raise HTTPException(status_code=403, detail='Not allowed')
    if not token:
        raise HTTPException(status_code=401, detail='No token provided')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return { 'payload': payload }
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {e}')


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db=Depends(get_db)):
    try:
        print(f"Signup attempt for username: {user_data.username}, email: {user_data.email}")

        existing_user = await db.users.find_one(
            {"$or": [{"username": user_data.username}, {"email": user_data.email}]}
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered",
            )

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
            "status": user_data.status or "active",
            "created_at": datetime.utcnow(),
        }

        result = await db.users.insert_one(user_dict)
        user_id = str(result.inserted_id)

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_data.username, "role": "client"},
            expires_delta=access_token_expires,
        )

        activation_link = f"{settings.FRONTEND_URL.rstrip('/')}/activate?token={access_token}"
        try:
            await send_activation_email(user_data.email, user_data.full_name, activation_link)
            print(f"Activation email sent to: {user_data.email}")
        except Exception as email_error:
            print(f"Failed to send activation email: {str(email_error)}")

        response = {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "role": "client",
            "message": f"Welcome {user_data.full_name}! Your account has been created. Please check your email for activation link.",
        }

        if getattr(settings, "ENVIRONMENT", "production") == "development":
            response["activation_link"] = activation_link

        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    try:
        try:
            user = await asyncio.wait_for(
                authenticate_user(db, form_data.username, form_data.password),
                timeout=4.0,
            )
        except asyncio.TimeoutError:
            # Treat as DB timeout — surface as service unavailable
            raise HTTPException(status_code=503, detail="Database timeout; try again later")
        except RuntimeError as re:
            # Raised by authenticate_user when DB is unreachable
            raise HTTPException(status_code=503, detail="Database unavailable; try again later")

        if not user:
            # IMPORTANT: invalid creds should be 401, not 500
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role},
            expires_delta=access_token_expires,
        )

        # Helpful debug log in development to diagnose token / secret mismatches
        if getattr(settings, 'ENVIRONMENT', '') == 'development':
            try:
                payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                print(f"login: issued token for user={user.username} payload_sub={payload.get('sub')} exp={payload.get('exp')}")
            except Exception as _:
                print("login: issued token could not be decoded with current SECRET_KEY (possible mismatch)")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(user.id) if hasattr(user, "id") else "",
            "role": user.role,
        }

    except HTTPException:
        raise
    except Exception as e:
        # If anything unexpected happens, surface detail in dev
        detail = f"Internal server error: {str(e)}" if getattr(settings, "ENVIRONMENT", "production") == "development" else "Internal server error"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest, db=Depends(get_db)):
    try:
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
            return {"message": "Password reset link sent to your email"}

        raise HTTPException(status_code=500, detail="Failed to send reset email")

    except HTTPException:
        raise
    except Exception as e:
        detail = f"Internal server error: {str(e)}" if getattr(settings, "ENVIRONMENT", "production") == "development" else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)


@router.post("/reset-password")
async def reset_password(request: PasswordReset, db=Depends(get_db)):
    try:
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

    except HTTPException:
        raise
    except Exception as e:
        detail = f"Internal server error: {str(e)}" if getattr(settings, "ENVIRONMENT", "production") == "development" else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)
