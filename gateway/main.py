# gateway/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway import deps
from gateway.routers import portfolio, signals, agents, backtests, trades, chat
from gateway.ws_manager import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await deps.startup()
    yield
    await deps.shutdown()


app = FastAPI(title="Hedge Fund Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
