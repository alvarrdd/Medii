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
from backend.doctor_directory import DoctorDirectory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _merge_predictions(pred_lists, top_k: int):
    merged = {}
    for preds in pred_lists:
        for p in preds or []:
            prev = merged.get(p.name)
            if prev is None or float(p.score) > float(prev.score):
                merged[p.name] = p
    return sorted(merged.values(), key=lambda x: float(x.score), reverse=True)[:top_k]


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
    doctors: list["DoctorInfo"] = []


class DoctorInfo(BaseModel):
    """Doctor profile shown to end users."""
    name: str
    clinic: str | None = None
    phone: str | None = None
    specialty: str | None = None


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
    "doctor_directory": None,
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

        components["doctor_directory"] = DoctorDirectory.from_csv(
            settings.doctors_csv
        )
        logger.info("Doctor directory initialized")
        
        components["sdi"] = SymptomDiseaseIndexer(settings)
        logger.info("Symptom→Disease indexer initialized")
        try:
            components["sdi"].warmup()
            logger.info("Symptom→Disease indexer warmed up")
        except Exception as e:
            logger.warning(f"Indexer warmup failed, lazy init will be used: {e}")
        
        components["recommendation_engine"] = RecommendationEngine(
            gemini_model_name=settings.gemini_model_name,
            gemini_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            specialist_mapper=components["specialist_mapper"],
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

        # 3. Retrieve candidate diseases using multiple query variants
        settings = components["settings"]
        query_variants = [symptoms]
        if cleaned and cleaned != symptoms:
            query_variants.append(cleaned)
        if symptom_list:
            joined = " ".join(symptom_list).strip()
            if joined and joined not in query_variants:
                query_variants.append(joined)
        candidate_pool_k = max(settings.rag_top_k * 3, 12)
        pred_lists = [components["sdi"].predict(q, top_k=candidate_pool_k) for q in query_variants]
        preds = _merge_predictions(pred_lists, top_k=max(1, settings.rag_top_k))
        min_score = float(max(0.0, min(1.0, settings.similarity_threshold)))
        strong_preds = [p for p in preds if float(p.score) >= min_score]
        if strong_preds:
            preds = strong_preds

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

        # 4. Map diseases to specialist (weighted by disease scores)
        specialist_name = "Թերապևտ / Ընտանեկան բժիշկ"
        if disease_names:
            top_disease = diseases_model[0]
            if float(top_disease.match_score) >= 0.42:
                specialist_name = components["specialist_mapper"].recommend_all([top_disease.name_hy]).get(
                    top_disease.name_hy,
                    specialist_name,
                )
        
        # 5. Retrieve RAG context from FAISS context index built from CSV
        context = ""
        for q in query_variants:
            context = components["sdi"].retrieve_context(
                query=q,
                top_k=settings.rag_top_k,
                max_chars=settings.max_context_chars,
            )
            if context:
                break

        # 6. Generate AI response with retrieved context
        raw_response = components["recommendation_engine"].generate(symptoms, cleaned, diseases_text, specialist_name, context)
        safe_response = components["model_evaluator"].enforce(raw_response)

        # 7. Build specialist info
        top_score = diseases_model[0].match_score if diseases_model else 0.0
        specialists = [
            SpecialistInfo(
                name_hy=specialist_name,
                description_hy=f"Խորհուրդ է տրվում այցելել {specialist_name}",
                diseases=diseases_model,
                match_score=float(top_score),
                recommended_action=(
                    "Խնդրում ենք անմիջապես դիմել շտապ օգնության" if urgency_level == "critical" else "Խնդրում ենք պլանավորել այցելություն մոտակա ժամանակ"
                ),
                urgency_note="Շտապ բժշկական օգնության կարիք" if urgency_level == "critical" else None,
                doctors=[
                    DoctorInfo(
                        name=doc.name,
                        clinic=doc.clinic,
                        phone=doc.phone,
                        specialty=doc.specialty,
                    )
                    for doc in components["doctor_directory"].find_by_specialist(specialist_name, limit=4)
                ],
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
        logger.exception(f"Error in /api/recommend endpoint: {e}")
        return RecommendationResponse(
            specialists=[
                SpecialistInfo(
                    name_hy="Թերապևտ / Ընտանեկան բժիշկ",
                    description_hy="Ժամանակավոր տեխնիկական խնդիր է առաջացել։",
                    diseases=[],
                    match_score=0.0,
                    recommended_action="Եթե վիճակը վատթարանում է, դիմեք շտապ օգնության",
                    urgency_note=None,
                    doctors=[],
                )
            ],
            urgency_level="low",
            confidence=0.0,
            emergency_symptoms=[],
            reasoning=(
                "Ժամանակավոր տեխնիկական խնդիր է առաջացել տվյալների մշակման ընթացքում, "
                "բայց խորհուրդ է տրվում դիմել համապատասխան մասնագետի։"
            ),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
