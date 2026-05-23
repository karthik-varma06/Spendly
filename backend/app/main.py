import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.routes.chat import router as chat_router
from app.api.routes.auth import router as auth_router
from app.api.routes.budgets import router as budgets_router
from app.api.routes.categories import router as categories_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.expenses import router as expenses_router
from app.api.routes.health import router as health_router
from app.api.routes.income import router as income_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.settings import router as settings_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.export import router as export_router
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

app = FastAPI(title="AI Financial / Expense Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    print("[startup] Checking database...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[startup] Database connected")
    except Exception as exc:
        print("[startup] Database unavailable or misconfigured:", exc)

    print(f"[startup] OpenRouter configured: {bool(settings.openrouter_api_key.strip())}")
    print(f"[startup] Tesseract path: {settings.tesseract_cmd or 'Not set in env'}")


@app.get("/")
def root():
    return {"message": "AI Financial / Expense Tracker API is running"}


app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(expenses_router, prefix="/api")
app.include_router(income_router, prefix="/api")
app.include_router(budgets_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")