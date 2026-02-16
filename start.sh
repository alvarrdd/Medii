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

# Install dependencies
echo "📚 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

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
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
