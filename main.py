import sys
import os

# Add backend directory to Python path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import app from backend/main.py
try:
    from backend.main import app
except ImportError:
    # Fallback for different environment structures
    from main import app

@app.get("/api/root-check")
def root_check():
    return {"source": "root-main-v2"}

__all__ = ["app"]
