# gateway/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from gateway import deps
from gateway.routers import portfolio, signals, agents, backtests, trades, chat, prices, auth as auth_router
from gateway.ws_manager import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await deps.startup()
    yield
    await deps.shutdown()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Hedge Fund Gateway", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Only add HSTS when running behind TLS
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(prices.router, prefix="/prices", tags=["prices"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
