from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.db.session import engine


app = FastAPI(
    title="FastAPI Payment API",
    version="1.0.0",
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "FastAPI Payment API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    return {"database": "connected"}