import sys
import os

# Add backend directory to Python path to allow imports from within backend/
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.main import app

@app.get("/api/test-deploy")
def test_deploy():
    return {"status": "deployed-7e86c09"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
