"""Symptom -> disease retrieval with FAISS + lexical reranking."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
import pandas as pd

from backend.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiseaseCandidate:
    name: str
    score: float
    description: Optional[str] = None


class SymptomDiseaseIndexer:
    """Indexes symptom rows from CSV and returns ranked disease candidates."""

    _TOKEN_RE = re.compile(r"[\u0531-\u0587a-zA-Z0-9]+", re.UNICODE)

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = None
        self._index: Optional[faiss.IndexFlatIP] = None
        self._ctx_index: Optional[faiss.IndexFlatIP] = None

        self._symptoms: List[str] = []
        self._disease_of_row: List[str] = []
        self._desc_by_disease: Dict[str, str] = {}

        self._ctx_chunks: List[str] = []
        self._ctx_chunk_owner: List[str] = []

        self._initialized = False

    def count(self) -> int:
        return len(self._symptoms)

    def warmup(self) -> None:
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        try:
            logger.info("Loading embedding model: %s", self._settings.embedding_model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._settings.embedding_model_name,
                local_files_only=True,
            )
            self._build_with_embeddings()
        except Exception as e:
            logger.warning("Embedding init failed (%s); using lexical fallback", e)
            self._model = None
            self._build_lexical_only()

        self._initialized = True

    def _read_csv(self, path: Path) -> Optional[pd.DataFrame]:
        for enc in ("utf-8", "utf-8-sig"):
            try:
                return pd.read_csv(path, encoding=enc)
            except Exception:
                pass
        try:
            return pd.read_csv(path, header=None, encoding="utf-8-sig")
        except Exception:
            return None

    def _load_dataset(self) -> Tuple[List[str], List[str], Dict[str, str]]:
        path = self._settings.medical_knowledge_csv
        if not path.exists():
            logger.warning("medical_knowledge.csv not found at %s", path)
            return [], [], {}

        df = self._read_csv(path)
        if df is None or df.shape[1] < 2:
            logger.error("Failed to load valid medical dataset from %s", path)
            return [], [], {}

        # Header vs headerless detection
        if not str(df.columns[0]).isdigit():
            col0 = df.columns[0]
            col1 = df.columns[1]
        else:
            col0 = 0
            col1 = 1

        desc_col = None
        if df.shape[1] >= 3 and not str(df.columns[0]).isdigit():
            lc = [str(c).lower() for c in df.columns]
            if "description" in lc:
                desc_col = df.columns[lc.index("description")]

        symptoms: List[str] = []
        diseases: List[str] = []
        desc_by_disease: Dict[str, str] = {}

        for _, row in df.iterrows():
            symptom = str(row[col0]).strip()
            disease = str(row[col1]).strip()
            if not symptom or not disease:
                continue
            symptom = " ".join(symptom.split())
            symptoms.append(symptom)
            diseases.append(disease)

            if desc_col is not None and pd.notna(row[desc_col]):
                desc = str(row[desc_col]).strip()
                if desc:
                    desc_by_disease[disease] = desc

        logger.info("Loaded %s symptom-disease rows", len(symptoms))
        return symptoms, diseases, desc_by_disease

    def _dataset_fingerprint(self, symptoms: List[str], diseases: List[str]) -> str:
        h = hashlib.sha256()
        h.update(str(len(symptoms)).encode("utf-8"))
        for s, d in zip(symptoms, diseases):
            h.update(s.encode("utf-8", errors="ignore"))
            h.update(b"|")
            h.update(d.encode("utf-8", errors="ignore"))
            h.update(b"\n")
        return h.hexdigest()

    def _cache_paths(self) -> Tuple[Path, Path, Path]:
        base = self._settings.faiss_index_path
        return base, base.with_suffix(".ctx.faiss"), base.with_suffix(".meta.npz")

    def _load_cache(self, fingerprint: str) -> bool:
        base, ctx_path, meta_path = self._cache_paths()
        if not (base.exists() and meta_path.exists()):
            return False
        try:
            meta = np.load(meta_path, allow_pickle=True)
            if str(meta["fingerprint"].item()) != fingerprint:
                return False

            self._index = faiss.read_index(str(base))
            self._symptoms = [str(x) for x in meta["symptoms"].tolist()]
            self._disease_of_row = [str(x) for x in meta["diseases"].tolist()]
            self._ctx_chunks = [str(x) for x in meta["ctx_chunks"].tolist()]
            self._ctx_chunk_owner = [str(x) for x in meta["ctx_owner"].tolist()]

            self._desc_by_disease = {}
            keys = [str(x) for x in meta["desc_keys"].tolist()]
            vals = [str(x) for x in meta["desc_vals"].tolist()]
            for k, v in zip(keys, vals):
                self._desc_by_disease[k] = v

            if ctx_path.exists() and self._ctx_chunks:
                self._ctx_index = faiss.read_index(str(ctx_path))
            else:
                self._ctx_index = None

            logger.info("Loaded FAISS indices from cache")
            return True
        except Exception as e:
            logger.warning("Failed to load cache, rebuilding: %s", e)
            return False

    def _save_cache(self, fingerprint: str) -> None:
        base, ctx_path, meta_path = self._cache_paths()
        try:
            if self._index is not None:
                faiss.write_index(self._index, str(base))
            if self._ctx_index is not None:
                faiss.write_index(self._ctx_index, str(ctx_path))
            np.savez_compressed(
                meta_path,
                fingerprint=np.array(fingerprint, dtype=object),
                symptoms=np.array(self._symptoms, dtype=object),
                diseases=np.array(self._disease_of_row, dtype=object),
                desc_keys=np.array(list(self._desc_by_disease.keys()), dtype=object),
                desc_vals=np.array(list(self._desc_by_disease.values()), dtype=object),
                ctx_chunks=np.array(self._ctx_chunks, dtype=object),
                ctx_owner=np.array(self._ctx_chunk_owner, dtype=object),
            )
            logger.info("Saved FAISS cache")
        except Exception as e:
            logger.warning("Failed to save FAISS cache: %s", e)

    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []
        out: List[str] = []
        i = 0
        while i < len(text):
            j = min(len(text), i + chunk_size)
            out.append(text[i:j])
            if j >= len(text):
                break
            i = max(i + chunk_size - overlap, j)
        return out

    def _build_lexical_only(self) -> None:
        symptoms, diseases, desc = self._load_dataset()
        self._index = None
        self._ctx_index = None
        self._symptoms = symptoms
        self._disease_of_row = diseases
        self._desc_by_disease = desc
        self._ctx_chunks = []
        self._ctx_chunk_owner = []
        logger.info("Lexical mode initialized with %s rows", len(self._symptoms))

    def _build_with_embeddings(self) -> None:
        symptoms, diseases, desc = self._load_dataset()
        if not symptoms:
            self._index = None
            self._ctx_index = None
            return

        fingerprint = self._dataset_fingerprint(symptoms, diseases)
        if self._load_cache(fingerprint):
            return

        emb = self._model.encode(
            symptoms,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        self._index = faiss.IndexFlatIP(emb.shape[1])
        self._index.add(emb)

        self._symptoms = symptoms
        self._disease_of_row = diseases
        self._desc_by_disease = desc

        sample_by_disease: Dict[str, List[str]] = {}
        for s, d in zip(symptoms, diseases):
            sample_by_disease.setdefault(d, []).append(s)

        ctx_docs: List[str] = []
        ctx_owner: List[str] = []
        for disease, examples in sample_by_disease.items():
            body = f"{disease}. "
            if disease in desc and desc[disease]:
                body += desc[disease] + " "
            body += "Օրինակ ախտանշաններ: " + "; ".join(examples[:4])
            for chunk in self._chunk_text(body):
                ctx_docs.append(chunk)
                ctx_owner.append(disease)

        if ctx_docs:
            cemb = self._model.encode(
                ctx_docs,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
            self._ctx_index = faiss.IndexFlatIP(cemb.shape[1])
            self._ctx_index.add(cemb)
            self._ctx_chunks = ctx_docs
            self._ctx_chunk_owner = ctx_owner
        else:
            self._ctx_index = None
            self._ctx_chunks = []
            self._ctx_chunk_owner = []

        self._save_cache(fingerprint)
        logger.info("Built FAISS indices (symptoms=%s, ctx=%s)", len(self._symptoms), len(self._ctx_chunks))

    def _tokenize(self, text: str) -> List[str]:
        return self._TOKEN_RE.findall((text or "").lower())

    def _norm_disease(self, disease: str) -> str:
        return " ".join((disease or "").strip().lower().split())

    def _lexical_similarity(self, query: str, candidate: str) -> float:
        q_tokens = self._tokenize(query)
        c_tokens = self._tokenize(candidate)
        if not q_tokens or not c_tokens:
            return 0.0
        q_set = set(q_tokens)
        c_set = set(c_tokens)
        inter = len(q_set & c_set)
        if inter == 0:
            return 0.0
        jacc = inter / max(1, len(q_set | c_set))
        cov = inter / max(1, len(q_set))
        q_text = " ".join(q_tokens)
        c_text = " ".join(c_tokens)
        phrase_bonus = 0.15 if (q_text in c_text or c_text in q_text) else 0.0
        return float(min(1.0, 0.55 * cov + 0.45 * jacc + phrase_bonus))

    def predict(self, query: str, top_k: int) -> List[DiseaseCandidate]:
        self._ensure_initialized()
        if not query or not self._symptoms:
            return []

        # Lexical fallback mode
        if self._model is None or self._index is None:
            agg: Dict[str, Tuple[str, float]] = {}
            for symptom, disease in zip(self._symptoms, self._disease_of_row):
                score = self._lexical_similarity(query, symptom)
                if score > 0.0:
                    key = self._norm_disease(disease)
                    prev_name, prev_score = agg.get(key, (disease, float("-inf")))
                    keep_name = prev_name if len(prev_name) >= len(disease) else disease
                    agg[key] = (keep_name, max(prev_score, score))
            out = [
                DiseaseCandidate(name=name, score=float(score), description=self._desc_by_disease.get(name))
                for _, (name, score) in sorted(agg.items(), key=lambda x: x[1][1], reverse=True)
            ]
            return out[: max(1, top_k)]

        try:
            q = self._model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)

            search_k = min(max(top_k * 40, 120), len(self._symptoms))
            scores, idxs = self._index.search(q, max(1, search_k))

            agg: Dict[str, Tuple[str, float]] = {}
            for raw_score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
                if not (0 <= idx < len(self._disease_of_row)):
                    continue
                disease = self._disease_of_row[idx]
                symptom = self._symptoms[idx]
                semantic = max(0.0, min(1.0, (float(raw_score) + 1.0) / 2.0))
                lexical = self._lexical_similarity(query, symptom)
                hybrid = 0.75 * semantic + 0.25 * lexical
                key = self._norm_disease(disease)
                prev_name, prev_score = agg.get(key, (disease, float("-inf")))
                keep_name = prev_name if len(prev_name) >= len(disease) else disease
                agg[key] = (keep_name, max(prev_score, hybrid))

            out = [
                DiseaseCandidate(name=name, score=float(score), description=self._desc_by_disease.get(name))
                for _, (name, score) in sorted(agg.items(), key=lambda x: x[1][1], reverse=True)
            ]
            return out[: max(1, top_k)]
        except Exception as e:
            logger.error("Disease prediction failed: %s", e)
            return []

    def retrieve_context(self, query: str, top_k: int, max_chars: int) -> str:
        self._ensure_initialized()
        if not query or not self._ctx_chunks or self._ctx_index is None or self._model is None:
            return ""
        try:
            q = self._model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
            k = max(1, min(top_k, len(self._ctx_chunks)))
            _, idxs = self._ctx_index.search(q, k)
            out: List[str] = []
            total = 0
            for idx in idxs[0].tolist():
                if not (0 <= idx < len(self._ctx_chunks)):
                    continue
                ch = self._ctx_chunks[idx]
                if total + len(ch) + 2 > max_chars:
                    break
                out.append(ch)
                total += len(ch) + 2
            return "\n\n".join(out)
        except Exception as e:
            logger.error("Context retrieval failed: %s", e)
            return ""
