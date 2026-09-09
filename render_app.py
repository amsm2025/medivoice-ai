import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Reuse the Phase 0.2 API without changing the local Docker Compose layout.
sys.path.insert(0, "/app/backend")
from app.main import app as api_app  # noqa: E402

app = FastAPI(title="MediVoice AI Render Host")
app.mount("/api", api_app)
app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="frontend")
