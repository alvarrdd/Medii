"""Symptom → Disease FAISS indexer using medical_knowledge.csv."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from backend.config import Settings

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DiseaseCandidate:
    name: str
    score: float
    description: Optional[str] = None

class SymptomDiseaseIndexer:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: Optional[SentenceTransformer] = None
        # Primary FAISS index over symptom texts (for disease ranking)
        self._index: Optional[faiss.IndexFlatIP] = None
        # Secondary FAISS index over context chunks (for RAG context)
        self._ctx_index: Optional[faiss.IndexFlatIP] = None
        self._symptoms: List[str] = []
        self._disease_of_row: List[str] = []
        self._desc_by_disease: Dict[str, str] = {}

        # Context chunks and owners
        self._ctx_chunks: List[str] = []
        self._ctx_chunk_owner: List[str] = []  # disease owning the chunk

        self._initialized = False

    def count(self) -> int:
        """Number of symptom rows indexed."""
        return len(self._symptoms)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            logger.info(f"Loading embedding model: {self._settings.embedding_model_name}")
            self._model = SentenceTransformer(self._settings.embedding_model_name)
            self._build_index()
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize SymptomDiseaseIndexer: {e}")
            raise

    def _load_dataset(self) -> Tuple[List[str], List[str], Dict[str, str]]:
        path = self._settings.medical_knowledge_csv
        if not path.exists():
            logger.warning(f"medical_knowledge.csv not found at {path}")
            return [], [], {}
        
        try:
            # ✅ Handle headerless Armenian CSVs
            read_ok = False
            for enc in ("utf-8", "utf-8-sig"):
                try:
                    # Try with headers first
                    df = pd.read_csv(path, encoding=enc)
                    read_ok = True
                    break
                except Exception:
                    continue
            
            if not read_ok:
                # Force headerless read
                try:
                    df = pd.read_csv(path, header=None, encoding='utf-8-sig')
                    read_ok = True
                except Exception:
                    pass
            
            if not read_ok:
                logger.error(f"Failed to read CSV: {path}")
                return [], [], {}

            # Determine columns (handle both headered and headerless)
            if df.shape[1] >= 2 and not str(df.columns[0]).isdigit():
                # Has headers - detect by name
                lc = [str(c).lower() for c in df.columns]
                if "symptom" in lc and "disease" in lc:
                    symptom_col = df.columns[lc.index("symptom")]
                    disease_col = df.columns[lc.index("disease")]
                else:
                    symptom_col = df.columns[0]
                    disease_col = df.columns[1]
                    logger.warning("Using first two columns as (symptom,disease)")
            else:
                # Headerless - use indices 0 and 1
                symptom_col = 0
                disease_col = 1

            desc_col: Optional[str] = None
            if df.shape[1] >= 3 and not str(df.columns[0]).isdigit():
                lc = [str(c).lower() for c in df.columns]
                if "description" in lc:
                    desc_col = df.columns[lc.index("description")]

            symptoms: List[str] = []
            diseases_of_row: List[str] = []
            desc_by_disease: Dict[str, str] = {}
            for _, row in df.iterrows():
                s = str(row[symptom_col]).strip()
                d = str(row[disease_col]).strip()
                if not s or not d:
                    continue
                # normalize whitespace/punctuation lightly
                s = " ".join(s.split())
                symptoms.append(s)
                diseases_of_row.append(d)
                if desc_col is not None and pd.notna(row[desc_col]):
                    dd = str(row[desc_col]).strip()
                    if dd:
                        desc_by_disease[d] = dd
                elif df.shape[1] >= 3 and not str(df.columns[0]).isdigit():
                    # Headerless with 3 columns - assume index 2 is description
                    if pd.notna(row[2]):
                        dd = str(row[2]).strip()
                        if dd:
                            desc_by_disease[d] = dd
            
            logger.info(f"Loaded {len(symptoms)} symptom-disease pairs")
            return symptoms, diseases_of_row, desc_by_disease
            
        except Exception as e:
            logger.error(f"Error reading medical_knowledge.csv: {e}")
            return [], [], {}

    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + chunk_size)
            chunks.append(text[start:end])
            if end == n:
                break
            start = max(start + chunk_size - overlap, end)
        return chunks

    def _build_index(self) -> None:
        symptoms, diseases_of_row, desc_by_disease = self._load_dataset()
        if not symptoms:
            logger.warning("No rows to build FAISS index from")
            self._index = None
            self._ctx_index = None
            self._symptoms = []
            self._disease_of_row = []
            self._desc_by_disease = {}
            self._ctx_chunks = []
            self._ctx_chunk_owner = []
            return
        
        try:
            # 1) Symptom index (for disease ranking)
            emb = self._model.encode(symptoms, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            emb = emb.astype(np.float32)
            dim = emb.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(emb)
            self._index = index
            self._symptoms = symptoms
            self._disease_of_row = diseases_of_row
            self._desc_by_disease = desc_by_disease
            logger.info(f"Built symptom→disease FAISS index with {len(symptoms)} rows")

            # 2) Context index (for RAG context retrieval)
            ctx_docs: List[str] = []
            ctx_owner: List[str] = []
            # Build a per-disease context combining description + sample symptoms
            sample_by_disease: Dict[str, List[str]] = {}
            for s, d in zip(symptoms, diseases_of_row):
                sample_by_disease.setdefault(d, []).append(s)

            for disease, desc in desc_by_disease.items():
                base = f"{disease}. {desc}".strip()
                # attach up to 3 example symptom rows
                examples = sample_by_disease.get(disease, [])[:3]
                if examples:
                    base += "\nՕրինակ ախտանշաններ: " + "; ".join(examples)
                # chunk
                for ch in self._chunk_text(base, 600, 100):
                    ctx_docs.append(ch)
                    ctx_owner.append(disease)

            # fallback: if a disease has no description, use only examples
            for disease, examples in sample_by_disease.items():
                if disease not in desc_by_disease:
                    base = f"{disease}. Օրինակ ախտանշաններ: " + "; ".join(examples[:5])
                    for ch in self._chunk_text(base, 600, 100):
                        ctx_docs.append(ch)
                        ctx_owner.append(disease)

            if ctx_docs:
                ctx_emb = self._model.encode(ctx_docs, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
                ctx_emb = ctx_emb.astype(np.float32)
                ctx_dim = ctx_emb.shape[1]
                ctx_index = faiss.IndexFlatIP(ctx_dim)
                ctx_index.add(ctx_emb)
                self._ctx_index = ctx_index
                self._ctx_chunks = ctx_docs
                self._ctx_chunk_owner = ctx_owner
                logger.info(f"Built context FAISS index with {len(ctx_docs)} chunks")
            else:
                self._ctx_index = None
                self._ctx_chunks = []
                self._ctx_chunk_owner = []
                logger.warning("No context chunks built (missing descriptions and examples)")

        except Exception as e:
            logger.error(f"Failed building FAISS indices: {e}")
            self._index = None
            self._ctx_index = None
            self._symptoms = []
            self._disease_of_row = []
            self._desc_by_disease = {}
            self._ctx_chunks = []
            self._ctx_chunk_owner = []

    def predict(self, query: str, top_k: int) -> List[DiseaseCandidate]:
        self._ensure_initialized()
        if not query or self._index is None or not self._symptoms:
            return []
        
        try:
            q = self._model.encode([query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            q = q.astype(np.float32)
            k = max(1, min(top_k, len(self._symptoms)))
            scores, idxs = self._index.search(q, k)

            # Aggregate by disease using max score
            agg: Dict[str, float] = {}
            for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
                if 0 <= idx < len(self._disease_of_row):
                    disease = self._disease_of_row[idx]
                    agg[disease] = max(agg.get(disease, float("-inf")), float(score))

            # Sort and build candidates
            out: List[DiseaseCandidate] = []
            for disease, s in sorted(agg.items(), key=lambda x: x[1], reverse=True):
                out.append(DiseaseCandidate(name=disease, score=float(s), description=self._desc_by_disease.get(disease)))
            return out[:top_k]
            
        except Exception as e:
            logger.error(f"Disease prediction failed: {e}")
            return []

    def retrieve_context(self, query: str, top_k: int, max_chars: int) -> str:
        """Retrieve context chunks relevant to the query and fit within max_chars."""
        self._ensure_initialized()
        if not query or self._ctx_index is None or not self._ctx_chunks:
            return ""
        
        try:
            q = self._model.encode([query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            q = q.astype(np.float32)
            k = max(1, min(top_k, len(self._ctx_chunks)))
            scores, idxs = self._ctx_index.search(q, k)
            
            parts: List[str] = []
            total = 0
            for idx in idxs[0].tolist():
                if 0 <= idx < len(self._ctx_chunks):
                    chunk = self._ctx_chunks[idx]
                    if total + len(chunk) + 2 > max_chars:
                        break
                    parts.append(chunk)
                    total += len(chunk) + 2
            return "\n\n".join(parts)
            
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return ""