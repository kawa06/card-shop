from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, engine
from routes.auth import router as auth_router
from routes.cards import router as cards_router
from routes.cart import router as cart_router
from routes.orders import router as orders_router
from routes.admin import router as admin_router
from routes.translate import router as translate_router
from routes.exchange import router as exchange_router

# Create all tables on startup (new columns added if not exists via ALTER)
Base.metadata.create_all(bind=engine)

# Apply missing column migrations for SQLite
from sqlalchemy import text
with engine.connect() as conn:
    # Cards table migrations
    for col, definition in [
        ("image_urls", "TEXT"),
        ("condition", "VARCHAR(10)"),
    ]:
        try:
            conn.execute(text(f"ALTER TABLE cards ADD COLUMN {col} {definition}"))
            conn.commit()
        except Exception:
            pass  # column already exists

    # Users table migrations
    for col, definition in [
        ("is_verified", "BOOLEAN DEFAULT 0"),
        ("verification_token", "VARCHAR(255)"),
        ("postal_code", "VARCHAR(20)"),
        ("country", "VARCHAR(100)"),
        ("region", "VARCHAR(100)"),
        ("city", "VARCHAR(100)"),
        ("address_line1", "TEXT"),
        ("address_line2", "TEXT"),
        ("address", "TEXT"),
        ("phone_number", "VARCHAR(20)"),
        ("phone_verified", "BOOLEAN DEFAULT 0"),
    ]:
        try:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
            conn.commit()
        except Exception:
            pass  # column already exists

    # Orders table migrations
    for col, definition in [
        ("shipping_method", "VARCHAR(50)"),
        ("shipping_fee", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col} {definition}"))
            conn.commit()
        except Exception:
            pass  # column already exists

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (Explicit Import 2026-06-20)
app.include_router(auth_router, prefix="/api")
app.include_router(cards_router, prefix="/api")
app.include_router(cart_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(translate_router, prefix="/api")
app.include_router(exchange_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "deployed-fixed-v6"}
# Deploy Fix 2026-06-20-v5
