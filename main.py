import sys
import os

# Add backend directory to Python path to allow imports from within backend/
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

print("Starting Root Main App...")
from backend.main import app
print("Backend App Loaded Successfully.")

@app.get("/api/test-deploy")
def test_deploy():
    return {"status": "deployed-v16-test"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
