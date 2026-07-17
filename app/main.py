from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import engine

app = FastAPI(
    title="FastAPI Payment API",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {
        "message": "FastAPI Payment API"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    return {
        "database": "connected"
    }