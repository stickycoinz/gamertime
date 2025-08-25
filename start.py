#!/usr/bin/env python3
"""
Startup script that handles environment variables properly for deployment.
"""
import os
import sys
from pathlib import Path
import uvicorn

# Add the project root to sys.path for proper imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info"
    )
