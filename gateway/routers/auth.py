# gateway/routers/auth.py
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from shared.config import settings
from gateway.auth import create_access_token

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


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    if body.password != settings.dashboard_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me():
    return {"user": "dashboard", "authenticated": True}
