"""Semantic symptom-to-disease matcher backed by FAISS."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Protocol

import faiss
import numpy as np


class EmbedderProtocol(Protocol):
    """Protocol for embedders used by SymptomMatcher."""

    def encode(
        self,
        texts: List[str],
        *,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Encode a list of texts into vectors."""


class SymptomMatcher:
    """
    Match free-text symptoms to likely diseases using semantic similarity.

    The class:
    - reads a CSV mapping symptom text to disease name
    - embeds symptom rows with SentenceTransformers (or injected embedder)
    - builds a FAISS inner-product index
    - returns top-k disease names for a query
    """

    def __init__(
        self,
        csv_path: str | Path,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        symptom_column: str = "symptom",
        disease_column: str = "disease",
        has_header: bool = True,
        embedder: EmbedderProtocol | None = None,
    ) -> None:
        self._csv_path = Path(csv_path)
        self._model_name = model_name
        self._symptom_column = symptom_column
        self._disease_column = disease_column
        self._has_header = has_header
        self._embedder = embedder
        self._index: faiss.IndexFlatIP | None = None
        self._symptoms: List[str] = []
        self._diseases: List[str] = []

        self._load_rows()
        self._build_index()

    def _get_embedder(self) -> EmbedderProtocol:
        if self._embedder is not None:
            return self._embedder
        # Local import keeps module import lightweight and test-friendly.
        from sentence_transformers import SentenceTransformer

        self._embedder = SentenceTransformer(self._model_name)
        return self._embedder

    def _load_rows(self) -> None:
        if not self._csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self._csv_path}")

        symptoms: List[str] = []
        diseases: List[str] = []

        try:
            with self._csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                if self._has_header:
                    reader = csv.DictReader(handle)
                    if reader.fieldnames is None:
                        raise ValueError("CSV header is missing")
                    for row in reader:
                        symptom = (row.get(self._symptom_column) or "").strip()
                        disease = (row.get(self._disease_column) or "").strip()
                        if symptom and disease:
                            symptoms.append(symptom)
                            diseases.append(disease)
                else:
                    reader = csv.reader(handle)
                    for row in reader:
                        if len(row) < 2:
                            continue
                        symptom = (row[0] or "").strip()
                        disease = (row[1] or "").strip()
                        if symptom and disease:
                            symptoms.append(symptom)
                            diseases.append(disease)
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode CSV: {self._csv_path}") from exc
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV format: {self._csv_path}") from exc

        if not symptoms:
            raise ValueError("CSV contains no valid symptom->disease rows")

        self._symptoms = symptoms
        self._diseases = diseases

    def _build_index(self) -> None:
        embedder = self._get_embedder()
        try:
            embeddings = embedder.encode(
                self._symptoms,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise RuntimeError("Failed to create symptom embeddings") from exc

        if not isinstance(embeddings, np.ndarray):
            embeddings = np.asarray(embeddings)
        if embeddings.ndim != 2 or embeddings.shape[0] != len(self._symptoms):
            raise ValueError("Embedder returned invalid shape")
        if embeddings.shape[1] == 0:
            raise ValueError("Embedder returned zero-dimensional vectors")

        vectors = embeddings.astype(np.float32)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        self._index = index

    def find_top_k(self, symptoms: str, k: int) -> List[str]:
        """
        Return top-k semantically similar diseases for the given symptom text.

        Args:
            symptoms: Free-text symptom description.
            k: Number of disease names to return.
        """
        if not isinstance(k, int) or k <= 0:
            raise ValueError("k must be a positive integer")
        query = (symptoms or "").strip()
        if not query:
            raise ValueError("symptoms must be a non-empty string")
        if self._index is None:
            raise RuntimeError("FAISS index is not initialized")

        embedder = self._get_embedder()
        try:
            query_vec = embedder.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise RuntimeError("Failed to encode query symptoms") from exc

        if not isinstance(query_vec, np.ndarray):
            query_vec = np.asarray(query_vec)
        if query_vec.ndim != 2 or query_vec.shape[0] != 1:
            raise ValueError("Query embedding shape is invalid")

        query_vec = query_vec.astype(np.float32)
        search_k = min(max(k * 8, k), len(self._symptoms))
        scores, indices = self._index.search(query_vec, search_k)

        best_by_disease: dict[str, float] = {}
        for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
            if 0 <= idx < len(self._diseases):
                disease = self._diseases[idx]
                prev = best_by_disease.get(disease, float("-inf"))
                if score > prev:
                    best_by_disease[disease] = float(score)

        ranked = sorted(best_by_disease.items(), key=lambda item: item[1], reverse=True)
        return [name for name, _ in ranked[:k]]
