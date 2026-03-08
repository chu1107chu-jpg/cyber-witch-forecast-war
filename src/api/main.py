"""Точка входа FastAPI — /api/v1"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.api.routes import forecast, data, wallet, games, nft, spin, snake, admin
from src.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up…")
    yield
    logger.info("Shutting down…")


app = FastAPI(
    title="Предсказания — Market Forecast API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # сузить в prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(forecast.router, prefix=PREFIX + "/forecast", tags=["forecast"])
app.include_router(data.router,     prefix=PREFIX + "/data",     tags=["data"])
app.include_router(wallet.router,   prefix=PREFIX + "/wallet",   tags=["wallet"])
app.include_router(games.router,    prefix=PREFIX + "/games",    tags=["games"])
app.include_router(nft.router,      prefix=PREFIX + "/nft",      tags=["nft"])
app.include_router(spin.router,     prefix=PREFIX + "/spin",     tags=["spin"])
app.include_router(snake.router,    prefix=PREFIX + "/snake",    tags=["snake"])
app.include_router(admin.router,    prefix=PREFIX + "/admin",    tags=["admin"])


@app.get("/health")
def health():
    return {"status": "ok"}
