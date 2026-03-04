#!/bin/bash

# Medi Backend Startup Script

echo "🚀 Starting Medi Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies only when needed (works better on limited/offline networks)
need_install=0
python - <<'PY' >/dev/null 2>&1
import fastapi, uvicorn, pandas, numpy, dotenv  # noqa: F401
import sentence_transformers  # noqa: F401
from huggingface_hub import cached_download  # noqa: F401
import google.generativeai  # noqa: F401
PY
if [ $? -ne 0 ]; then
    need_install=1
fi

if [ "${MEDI_INSTALL_DEPS:-0}" = "1" ] || [ $need_install -eq 1 ]; then
    echo "📚 Installing dependencies..."
    pip install --upgrade pip || true
    pip install -r requirements.txt || {
        echo "❌ Dependency installation failed."
        echo "If you are offline, run again later or reuse an existing working venv."
        exit 1
    }
else
    echo "✅ Dependencies already available (skipping reinstall)."
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your GEMINI_API_KEY"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p backend/data

# Start the server
echo "✅ Starting FastAPI server..."
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
