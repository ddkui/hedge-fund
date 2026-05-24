# gateway/routers/auth.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from shared.config import settings
from gateway.auth import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    if body.password != settings.dashboard_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me():
    return {"user": "dashboard", "authenticated": True}
