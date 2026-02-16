"""Main FastAPI application for Medi - matches frontend API expectations."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.emergency_detector import EmergencyDetector
from backend.model_evaluator import ModelEvaluator
from backend.recommendation_engine import RecommendationEngine
from backend.specialist_mapper import SpecialistMapper
from backend.preprocessor import SymptomPreprocessor
from backend.faiss_search import SymptomDiseaseIndexer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Request/Response Models matching frontend expectations
class SymptomRequest(BaseModel):
    """Request model for /api/recommend endpoint."""
    symptoms: str = Field(..., min_length=1, max_length=5000)


class DiseaseInfo(BaseModel):
    """Disease information."""
    name_hy: str
    description: str | None = None
    match_score: float


class SpecialistInfo(BaseModel):
    """Specialist information."""
    name_hy: str
    description_hy: str | None = None
    diseases: list[DiseaseInfo] = []
    match_score: float
    recommended_action: str | None = None
    urgency_note: str | None = None


class RecommendationResponse(BaseModel):
    """Response model for /api/recommend endpoint."""
    specialists: list[SpecialistInfo]
    urgency_level: str  # critical, high, medium, low
    confidence: float
    emergency_symptoms: list[str]
    reasoning: str


# Global component instances
components = {
    "settings": None,
    "preprocessor": None,
    "emergency_detector": None,
    "sdi": None,
    "specialist_mapper": None,
    "recommendation_engine": None,
    "model_evaluator": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Medi backend...")
    
    try:
        settings = get_settings()
        components["settings"] = settings
        logger.info("Settings loaded")
        
        # Initialize components
        components["preprocessor"] = SymptomPreprocessor()
        logger.info("Preprocessor initialized")
        
        components["emergency_detector"] = EmergencyDetector.default()
        logger.info("Emergency detector initialized")
        
        components["specialist_mapper"] = SpecialistMapper.from_csv(
            settings.disease_specialist_csv
        )
        logger.info("Specialist mapper initialized")
        
        components["sdi"] = SymptomDiseaseIndexer(settings)
        logger.info("Symptom→Disease indexer initialized")
        
        # ✅ FIXED: Pass specialist_mapper as third argument
        components["recommendation_engine"] = RecommendationEngine(
            settings=settings,
            retriever=None,
            specialist_mapper=components["specialist_mapper"]
        )
        logger.info("Recommendation engine initialized")
        
        # ✅ FIXED: Pass settings to ModelEvaluator
        components["model_evaluator"] = ModelEvaluator(settings)
        logger.info("Model evaluator initialized")
        
        logger.info("✅ All components initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}")
        raise
    
    yield
    
    logger.info("Shutting down Medi backend...")


# Create FastAPI app
app = FastAPI(
    title="Medi — AI Medical Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Medi API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "emergency_detector": components["emergency_detector"] is not None,
            "symptom_disease_indexer": components["sdi"] is not None,
            "specialist_mapper": components["specialist_mapper"] is not None,
            "recommendation_engine": components["recommendation_engine"] is not None,
            "model_evaluator": components["model_evaluator"] is not None,
        }
    }


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(payload: SymptomRequest) -> RecommendationResponse:
    """
    Analyze symptoms and provide specialist recommendations.
    
    This endpoint matches the frontend's expected API structure.
    """
    try:
        symptoms = payload.symptoms.strip()
        
        if not symptoms:
            raise HTTPException(status_code=400, detail="Symptoms cannot be empty")

        # 1. Emergency detection
        emergency_symptoms = []
        urgency_level = "low"
        
        if components["emergency_detector"].is_emergency(symptoms):
            emergency_symptoms = ["Հայտնաբերված են վտանգավոր ախտանիշներ"]
            urgency_level = "critical"

        # 2. Preprocess symptoms
        cleaned, symptom_list = components["preprocessor"].preprocess(symptoms)

        # 3. Retrieve candidate diseases using FAISS symptom→disease indexer
        settings = components["settings"]
        preds = components["sdi"].predict(cleaned, top_k=settings.rag_top_k)

        diseases_model = []
        for p in preds:
            diseases_model.append(
                DiseaseInfo(
                    name_hy=p.name,
                    description=p.description,
                    match_score=float(max(0.0, min(1.0, p.score))),
                )
            )

        disease_names = [d.name_hy for d in diseases_model]
        if not disease_names:
            diseases_text = "Չկան համապատասխան արդյունքներ"
        else:
            diseases_text = "\n".join([f"- {d.name_hy} (համապատասխանություն՝ {d.match_score:.2f})" for d in diseases_model])

        # 4. Map diseases to specialist
        specialist_name = components["specialist_mapper"].recommend(disease_names)
        
        # 5. Retrieve RAG context from FAISS context index built from CSV
        context = components["sdi"].retrieve_context(
            query=cleaned,
            top_k=settings.rag_top_k,
            max_chars=settings.max_context_chars,
        )

        # 6. Generate AI response with retrieved context
        raw_response = components["recommendation_engine"].generate(symptoms, cleaned, diseases_text, specialist_name, context)
        safe_response = components["model_evaluator"].enforce(raw_response)

        # 7. Build specialist info
        top_score = diseases_model[0].match_score if diseases_model else 0.6
        specialists = [
            SpecialistInfo(
                name_hy=specialist_name,
                description_hy=f"Խորհուրդ է տրվում այցելել {specialist_name}",
                diseases=diseases_model,
                match_score=float(top_score),
                recommended_action=(
                    "Խնդրում ենք անմիջապես դիմել շտապ օգնության" if urgency_level == "critical" else "Խնդրում ենք պլանավորել այցելություն մոտակա ժամանակ"
                ),
                urgency_note="Շտապ բժշկական օգնության կարիք" if urgency_level == "critical" else None
            )
        ]

        return RecommendationResponse(
            specialists=specialists,
            urgency_level=urgency_level,
            confidence=float(top_score),
            emergency_symptoms=emergency_symptoms,
            reasoning=safe_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /api/recommend endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )