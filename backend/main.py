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

# Apply missing column migrations for SQLite (More robust check using SQLAlchemy Inspector)
from sqlalchemy import text, inspect

def add_columns_if_missing():
    print("Running database migrations (checking for missing columns)...")
    inspector = inspect(engine)
    
    # Define tables and their expected columns
    tables_to_migrate = {
        "cards": [
            ("image_urls", "TEXT"),
            ("condition", "VARCHAR(10)"),
            ("rarity", "VARCHAR(50)"),
            ("set_name", "VARCHAR(100)"),
            ("allowed_shipping_methods", "TEXT"),
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
        ],
        "shipping_rates": [
            ("carrier", "VARCHAR(50)"),
            ("is_individual_available", "BOOLEAN DEFAULT 1"),
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
    try:
        Base.metadata.create_all(bind=engine)
        add_columns_if_missing()
    except Exception as e:
        print(f"Database initialization failed: {e}")

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
app.include_router(auth_router)
app.include_router(cards_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(admin_router)
app.include_router(translate_router)
app.include_router(exchange_router)
app.include_router(shipping_router)


# Deploy Fix 2026-06-21-v20 (Implement automatic migrations in lifespan)
@app.get("/api/health", summary="Health Check V20")
def health():
    return {"status": "ok", "version": "deployed-fixed-v20"}
# Deploy Fix 2026-06-21-v20
