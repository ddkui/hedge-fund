# gateway/routers/auth.py
import random
import smtplib
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from shared.config import settings
from gateway.auth import create_access_token
from gateway.deps import get_bus
from shared.bus import RedisBus

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("password must not be empty")
        if len(v) > 128:
            raise ValueError("password too long")
        return v


class GoogleLogin(BaseModel):
    credential: str   # Google ID token from the Sign in with Google button


class OtpRequest(BaseModel):
    email: str


class OtpVerify(BaseModel):
    email: str
    otp: str


def _send_otp_email(recipient: str, otp: str) -> None:
    msg = MIMEText(
        f"Your AI Hedge Fund login code is:\n\n  {otp}\n\nExpires in 10 minutes. Do not share this code."
    )
    msg["Subject"] = "[HedgeFund] Your login code"
    msg["From"] = settings.gmail_sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(settings.gmail_sender, settings.gmail_app_password)
        server.send_message(msg)


def _verify_google_token(credential: str) -> dict:
    """Verify a Google ID token and return its payload. Raises on failure."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )


@router.post("/google")
async def google_login(body: GoogleLogin):
    try:
        payload = _verify_google_token(body.credential)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    email = (payload.get("email") or "").lower()
    if not email or not payload.get("email_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email not verified")

    allowed = [e.strip().lower() for e in settings.allowed_login_emails.split(",") if e.strip()]
    if allowed and email not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not authorised")

    token = create_access_token()
    return {"access_token": token, "token_type": "bearer", "email": email}


@router.get("/config")
async def auth_config():
    """Public: lets the login page know which Google client ID to use."""
    return {"google_client_id": settings.google_client_id}


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    if body.password != settings.dashboard_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.post("/request-otp")
async def request_otp(body: OtpRequest, bus: RedisBus = Depends(get_bus)):
    allowed = [e.strip() for e in settings.allowed_login_emails.split(",") if e.strip()]
    if allowed and body.email not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not authorised")

    otp = str(random.randint(100000, 999999))
    await bus.set(f"otp:{body.email}", {"otp": otp, "email": body.email},
                  ex=settings.otp_expiry_seconds)
    try:
        _send_otp_email(body.email, otp)
    except Exception:
        pass  # OTP still stored; email failure is silent in dev

    return {"message": "OTP sent"}


@router.post("/verify-otp")
async def verify_otp(body: OtpVerify, bus: RedisBus = Depends(get_bus)):
    stored = await bus.get(f"otp:{body.email}")
    if not stored or stored.get("otp") != body.otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP")

    await bus.delete(f"otp:{body.email}")
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me():
    return {"user": "dashboard", "authenticated": True}
