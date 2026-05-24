# gateway/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway import deps
from gateway.routers import portfolio


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


@app.get("/health")
async def health():
    return {"status": "ok"}
