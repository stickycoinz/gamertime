"""
Party Game Platform - Main FastAPI Application
"""
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Add the project root to sys.path for proper imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.routers import lobby_routes, ws_routes

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Party Game Platform",
    description="Real-time multiplayer party games",
    version="1.0.0"
)

# Include routers
app.include_router(lobby_routes.router, prefix="/api", tags=["lobbies"])
app.include_router(ws_routes.router, tags=["websocket"])

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Serve the main game interface"""
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
