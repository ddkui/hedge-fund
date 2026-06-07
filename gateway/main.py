# gateway/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from gateway import deps
from gateway.routers import portfolio, signals, agents, backtests, trades, chat, prices, auth as auth_router, kronos as kronos_router, analytics as analytics_router, brokers as brokers_router, intelligence as intelligence_router, compliance as compliance_router
from gateway.routers.metrics import router as metrics_router
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
    # HSTS — safe because traffic always arrives via Caddy (TLS termination)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(prices.router, prefix="/prices", tags=["prices"])
app.include_router(kronos_router.router, prefix="/kronos", tags=["kronos"])
app.include_router(analytics_router.router, prefix="/analytics", tags=["analytics"])
app.include_router(compliance_router.router)
app.include_router(metrics_router)
app.include_router(brokers_router.router, prefix="/brokers", tags=["brokers"])
app.include_router(intelligence_router.router, prefix="/intelligence", tags=["intelligence"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
