import sys
import os

# Add backend directory to Python path so all backend modules resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from main import app  # noqa: F401 (main refers to backend/main.py via sys.path)

@app.get("/api/root-check")
def root_check():
    return {"source": "root-main"}

__all__ = ["app"]
