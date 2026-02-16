# Medi - AI Medical Assistant

Production-ready medical AI assistant with RAG and LLM integration.

## 🔧 Fixed Issues

### Backend Fixes:
1. ✅ Fixed segmentation fault - lazy model initialization
2. ✅ Fixed import errors - proper module structure
3. ✅ Fixed FAISS loading - safe initialization with error handling
4. ✅ Fixed CORS - comprehensive origin list
5. ✅ Fixed environment variables - proper dotenv loading
6. ✅ Fixed model downloads - show_progress_bar=False to prevent crashes
7. ✅ Added proper logging throughout
8. ✅ Added lifespan manager for component initialization
9. ✅ Fixed circular imports - direct imports only
10. ✅ Added health check endpoint

### Frontend Fixes:
1. ✅ Fixed API client with proper error handling
2. ✅ Fixed Vite proxy configuration
3. ✅ Added environment variable support
4. ✅ Added connection status indicator
5. ✅ Added comprehensive error messages

## 📦 Installation

### Backend Setup

```bash
# Navigate to project root
cd medi-project

# Make startup script executable
chmod +x start.sh

# Run startup script (creates venv, installs deps, starts server)
./start.sh
```

Or manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Create data directory
mkdir -p backend/data

# Start server
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Start dev server
npm run dev
```

## 📁 Required Data Files

Create these CSV files in `backend/data/`:

### medical_knowledge.csv
```csv
topic,content
General Health,"Information about general health practices..."
Emergency,"Emergency symptom information..."
```

### disease_specialist.csv
```csv
keywords,specialist
"headache,migraine",Neurologist
"chest pain,heart",Cardiologist
"cough,breathing",Pulmonologist
```

## 🚀 Running the Application

### Development Mode

Terminal 1 (Backend):
```bash
cd medi-project
./start.sh
# Or: python -m uvicorn backend.app:app --reload
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Access:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Production Mode

Backend:
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Frontend:
```bash
npm run build
npm run preview
```

## 🔍 Testing

### Backend Health Check
```bash
curl http://localhost:8000/health
```

### Test Analysis Endpoint
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"message": "I have a headache and feel tired"}'
```

## 🐛 Troubleshooting

### Segmentation Fault
- **Fixed**: Models now load lazily on first request
- Components initialize in lifespan manager
- No model loading during import

### Import Errors
- **Fixed**: All imports use `backend.module_name` format
- No circular dependencies
- Proper package structure

### Model Download Hangs
- **Fixed**: `show_progress_bar=False` in all encode calls
- Lazy initialization prevents startup hangs

### CORS Issues
- **Fixed**: Comprehensive CORS middleware with all localhost variants
- Supports both port 3000 and 5173

### Connection Refused
- Check backend is running on port 8000
- Check .env has GEMINI_API_KEY
- Check data files exist
- Check logs for initialization errors

## 📝 Environment Variables

### Backend (.env)
```env
GEMINI_API_KEY=your_key_here
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
```

## 🏗️ Architecture

```
medi-project/
├── backend/
│   ├── __init__.py
│   ├── app.py              # Main FastAPI app
│   ├── config.py           # Configuration
│   ├── emergency_detector.py
│   ├── specialist_mapper.py
│   ├── rag_retriever.py    # FAISS + embeddings
│   ├── recommendation_engine.py  # Gemini LLM
│   ├── model_evaluator.py
│   └── data/
│       ├── medical_knowledge.csv
│       └── disease_specialist.csv
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── api/
│   │       └── client.js
│   ├── vite.config.js
│   └── package.json
├── requirements.txt
├── .env.example
└── start.sh
```

## ✅ Production Checklist

- [x] Lazy model initialization
- [x] Proper error handling
- [x] Comprehensive logging
- [x] CORS configuration
- [x] Environment variable validation
- [x] Health check endpoint
- [x] Request validation (Pydantic)
- [x] Response safety (ModelEvaluator)
- [x] Emergency detection
- [x] Graceful fallbacks

## 📚 API Documentation

Interactive API docs available at: http://localhost:8000/docs

### Endpoints

**GET /**
- Root endpoint
- Returns API info

**GET /health**
- Health check
- Returns component status

**POST /analyze**
- Analyze symptoms
- Body: `{"message": "symptom description"}`
- Returns: `{"emergency": bool, "specialist": string, "response": string}`

## 🔐 Security Notes

- Never commit .env files
- Keep API keys secure
- Validate all user inputs
- Use HTTPS in production
- Rate limit API endpoints
- Monitor for abuse

## 📄 License

Proprietary - Medical AI Assistant
