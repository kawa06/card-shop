from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os

from config import settings
from database import Base, engine
from routes import auth, cards, cart, orders, admin

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS - allow all origins for simplicity
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


# Serve Next.js static export (SPA fallback)
static_dir = os.path.join(os.path.dirname(__file__), "frontend/dist")
static_dir = os.path.abspath(static_dir)

@app.get("/{rest_of_path:path}")
async def serve_frontend(rest_of_path: str):
    # Don't intercept API paths
    if rest_of_path.startswith("api/"):
        return Response(status_code=404)
    
    # Try to serve actual file
    file_path = os.path.join(static_dir, rest_of_path)
    if rest_of_path and os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # SPA fallback
    return FileResponse(os.path.join(static_dir, "index.html"))
