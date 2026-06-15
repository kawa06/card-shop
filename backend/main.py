from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, engine
from routes import auth, cards, cart, orders, admin

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
    ]:
        try:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
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

# Routers
app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
