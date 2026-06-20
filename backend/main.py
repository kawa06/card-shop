from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
import asyncio
from contextlib import asynccontextmanager
from database import Base, engine, SessionLocal
from services.shipping_rates import background_shipping_update_task, refresh_all_rates

from routes.auth import router as auth_router
from routes.cards import router as cards_router
from routes.cart import router as cart_router
from routes.orders import router as orders_router
from routes.admin import router as admin_router
from routes.translate import router as translate_router
from routes.exchange import router as exchange_router
from routes.shipping import router as shipping_router

# Create all tables on startup (new columns added if not exists via ALTER)
Base.metadata.create_all(bind=engine)

# Apply missing column migrations for SQLite (More robust PRAGMA check)
from sqlalchemy import text

def add_columns_if_missing():
    with engine.connect() as conn:
        # Helper to get existing columns
        def get_existing_columns(table_name):
            try:
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                return [row[1] for row in result.fetchall()]
            except Exception:
                return []

        # Cards table migrations
        existing_cards = get_existing_columns("cards")
        for col, definition in [
            ("image_urls", "TEXT"),
            ("condition", "VARCHAR(10)"),
            ("rarity", "VARCHAR(50)"),
            ("set_name", "VARCHAR(100)"),
            ("allowed_shipping_methods", "TEXT"),
        ]:
            if col not in existing_cards:
                try:
                    conn.execute(text(f"ALTER TABLE cards ADD COLUMN {col} {definition}"))
                except Exception: pass
        
        # Users table migrations
        existing_users = get_existing_columns("users")
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
            if col not in existing_users:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
                except Exception: pass

        # Orders table migrations
        existing_orders = get_existing_columns("orders")
        for col, definition in [
            ("postal_code", "VARCHAR(20)"),
            ("country", "VARCHAR(100)"),
            ("region", "VARCHAR(100)"),
            ("city", "VARCHAR(100)"),
            ("address_line1", "TEXT"),
            ("address_line2", "TEXT"),
            ("shipping_address", "TEXT"),
            ("shipping_method", "VARCHAR(50)"),
            ("shipping_fee", "INTEGER DEFAULT 0"),
        ]:
            if col not in existing_orders:
                try:
                    conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col} {definition}"))
                except Exception: pass

        # Shipping rates migrations
        existing_rates = get_existing_columns("shipping_rates")
        for col, definition in [
            ("carrier", "VARCHAR(50)"),
        ]:
            if col not in existing_rates:
                try:
                    conn.execute(text(f"ALTER TABLE shipping_rates ADD COLUMN {col} {definition}"))
                except Exception: pass
        
        conn.commit()

add_columns_if_missing()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initial refresh on startup
    try:
        with SessionLocal() as db:
            await refresh_all_rates(db)
    except Exception as e:
        print(f"Initial shipping rates refresh failed: {e}")
    
    # Start background task
    update_task = asyncio.create_task(background_shipping_update_task(SessionLocal))
    
    yield
    
    update_task.cancel()
    try:
        await update_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
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
app.include_router(shipping_router, prefix="/api")


# Deploy Fix 2026-06-20-v16 (Emergency Fix: Migration & Router)
@app.get("/api/health", summary="Health Check V16")
def health():
    return {"status": "ok", "version": "deployed-fixed-v16"}
# Deploy Fix 2026-06-20-v16
