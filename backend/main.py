from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
import asyncio
from contextlib import asynccontextmanager
from database import Base, engine, SessionLocal
from services.shipping_rates import background_shipping_update_task, refresh_all_rates
from services.order_expiry_task import background_order_expiry_task
from services.db_migrate import run_schema_upgrades
from services.db_persist import database_info
from services.image_upload import get_upload_dir

from routes.auth import router as auth_router
from routes.cards import router as cards_router
from routes.cart import router as cart_router
from routes.orders import router as orders_router
from routes.admin import router as admin_router
from routes.translate import router as translate_router
from routes.exchange import router as exchange_router
from routes.shipping import router as shipping_router
from routes.favorites import router as favorites_router
from routes.payments import router as payments_router
from routes.inquiries import router as inquiries_router
from routes.admin_inquiries import router as admin_inquiries_router
from routes.admin_buyback import router as admin_buyback_router
from routes.buyback import router as buyback_router

from sqlalchemy import text, inspect

# Apply missing column migrations for SQLite (More robust check using SQLAlchemy Inspector)

def add_columns_if_missing():
    print("Running database migrations (checking for missing columns)...")
    inspector = inspect(engine)
    
    # Define tables and their expected columns
    tables_to_migrate = {
        "cards": [
            ("name_en", "VARCHAR(200)"),
            ("image_urls", "TEXT"),
            ("condition", "VARCHAR(10)"),
            ("rarity", "VARCHAR(50)"),
            ("set_name", "VARCHAR(100)"),
            ("allowed_shipping_methods", "TEXT"),
            ("pack_id", "INTEGER"),
        ],
        "users": [
            ("is_verified", "BOOLEAN DEFAULT 0"),
            ("verification_token", "VARCHAR(255)"),
            ("postal_code", "VARCHAR(20)"),
            ("country", "VARCHAR(100)"),
            ("region", "VARCHAR(100)"),
            ("city", "VARCHAR(100)"),
            ("address_line1", "VARCHAR(255)"),
            ("address_line2", "VARCHAR(255)"),
            ("address", "TEXT"),
            ("phone_number", "VARCHAR(20)"),
            ("phone_verified", "BOOLEAN DEFAULT 0"),
        ],
        "orders": [
            ("postal_code", "VARCHAR(20)"),
            ("country", "VARCHAR(100)"),
            ("region", "VARCHAR(100)"),
            ("city", "VARCHAR(100)"),
            ("address_line1", "VARCHAR(255)"),
            ("address_line2", "VARCHAR(255)"),
            ("shipping_address", "TEXT"),
            ("shipping_method", "VARCHAR(50)"),
            ("shipping_fee", "INTEGER DEFAULT 0"),
            ("payment_method", "VARCHAR(50)"),
            ("payment_status", "VARCHAR(50) DEFAULT 'pending'"),
            ("stripe_checkout_session_id", "VARCHAR(255)"),
            ("click_post_csv_exported_at", "DATETIME"),
            ("payment_deadline", "DATETIME"),
            ("stock_reserved", "BOOLEAN DEFAULT 0"),
            ("paid_at", "DATETIME"),
            ("order_number", "VARCHAR(32)"),
            ("stripe_payment_intent_id", "VARCHAR(255)"),
            ("stripe_event_id", "VARCHAR(255)"),
            ("shipping_status", "VARCHAR(32) DEFAULT 'unshipped'"),
            ("shipping_carrier", "VARCHAR(100)"),
            ("tracking_number", "VARCHAR(100)"),
            ("shipped_at", "DATETIME"),
            ("purchase_email_sent_at", "DATETIME"),
            ("shipping_email_sent_at", "DATETIME"),
            ("email_send_status", "VARCHAR(50)"),
            ("admin_note", "TEXT"),
            ("discount_amount", "INTEGER DEFAULT 0"),
            ("coupon_code", "VARCHAR(64)"),
            ("coupon_name", "VARCHAR(128)"),
            ("payment_fee", "INTEGER DEFAULT 0"),
            ("packaging_fee", "INTEGER DEFAULT 0"),
            ("buyer_note", "TEXT"),
            ("buyer_phone", "VARCHAR(20)"),
            ("updated_at", "DATETIME"),
        ],
        "shipping_rates": [
            ("carrier", "VARCHAR(50)"),
            ("is_individual_available", "BOOLEAN DEFAULT 1"),
            ("is_international_available", "BOOLEAN DEFAULT 0"),
            ("international_zones", "TEXT"),
            ("max_weight_international", "FLOAT"),
            ("insurance_max_amount", "INTEGER"),
            ("insurance_url", "VARCHAR(500)"),
            ("estimated_delivery_min_days", "INTEGER"),
            ("estimated_delivery_max_days", "INTEGER"),
            ("is_recommended", "BOOLEAN DEFAULT 0"),
        ]
    }

    with engine.connect() as conn:
        for table_name, columns in tables_to_migrate.items():
            print(f"--- Checking table: {table_name} ---")
            try:
                # Get existing columns for this table
                existing_columns = [c["name"] for c in inspector.get_columns(table_name)]
                print(f"Existing columns in {table_name}: {existing_columns}")
            except Exception as e:
                print(f"Could not inspect table {table_name} (it might not exist yet): {e}")
                continue

            for col_name, col_def in columns:
                if col_name not in existing_columns:
                    print(f"Adding missing column {table_name}.{col_name} ({col_def})")
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
                        conn.commit()  # Commit each change individually
                        print(f"Successfully added {table_name}.{col_name}")
                    except Exception as e:
                        print(f"ERROR: Failed to add {table_name}.{col_name}: {e}")
                else:
                    # Optional: Log that it already exists for confirmation
                    pass
        
    print("Database migrations completed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and migrations
    # create_all only creates MISSING tables — never drops or truncates existing data.
    try:
        Base.metadata.create_all(bind=engine)
        add_columns_if_missing()
        run_schema_upgrades()
        db_info = database_info()
        if not db_info["persistent"]:
            print(f"WARNING: {db_info['warning']}")
    except Exception as e:
        print(f"Database initialization failed: {e}")

    # Initial refresh on startup
    try:
        with SessionLocal() as db:
            await refresh_all_rates(db)
    except Exception as e:
        print(f"Initial shipping rates refresh failed: {e}")
    
    # Start background tasks
    update_task = asyncio.create_task(background_shipping_update_task(SessionLocal))
    expiry_task = asyncio.create_task(background_order_expiry_task(SessionLocal))
    
    yield
    
    update_task.cancel()
    expiry_task.cancel()
    try:
        await update_task
    except asyncio.CancelledError:
        pass
    try:
        await expiry_task
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

upload_dir = get_upload_dir()
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/media/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Routers (Explicit Import 2026-06-20)
app.include_router(auth_router)
app.include_router(cards_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(admin_router)
app.include_router(translate_router)
app.include_router(exchange_router)
app.include_router(shipping_router)
app.include_router(favorites_router)
app.include_router(payments_router)
app.include_router(inquiries_router)
app.include_router(admin_inquiries_router)
app.include_router(admin_buyback_router)
app.include_router(buyback_router)


# Deploy Fix 2026-06-21-v20 (Implement automatic migrations in lifespan)
@app.get("/api/health", summary="Health Check V20")
def health():
    db = database_info()
    return {
        "status": "ok",
        "version": "deployed-fixed-v21",
        "database": db,
    }

@app.get("/api/health20")
def health20():
    return {"status": "ok", "version": "v20-direct"}
# Deploy Fix 2026-06-21-v20
