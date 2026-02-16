"""RAG retrieval module with FAISS indexing."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List
import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from backend.config import Settings

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class RetrievedChunk:
    """Retrieved knowledge chunk."""
    topic: str
    content: str
    score: float

class RAGRetriever:
    """
    Retrieval-Augmented Generation component.
    Indexes medical knowledge and retrieves relevant context.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: SentenceTransformer | None = None
        self._index: faiss.IndexFlatIP | None = None
        self._chunks: List[RetrievedChunk] = []
        
        # Lazy initialization to avoid segfaults on import
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Initialize model and index on first use."""
        if self._initialized:
            return
            
        try:
            logger.info(f"Loading embedding model: {self._settings.embedding_model_name}")
            self._model = SentenceTransformer(self._settings.embedding_model_name)
            logger.info("Embedding model loaded successfully")
            
            self._build_index()
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG retriever: {e}")
            raise

    def _load_corpus(self) -> List[RetrievedChunk]:
        """Load medical knowledge from CSV."""
        csv_path = self._settings.medical_knowledge_csv
        
        if not csv_path.exists():
            logger.warning(f"Medical knowledge CSV not found at {csv_path}")
            return []

        try:
            # ✅ Handle headerless Armenian CSVs
            read_ok = False
            for enc in ("utf-8", "utf-8-sig"):
                try:
                    # Try with headers first
                    df = pd.read_csv(csv_path, encoding=enc)
                    read_ok = True
                    break
                except Exception:
                    continue
            
            if not read_ok:
                # Force headerless read
                try:
                    df = pd.read_csv(csv_path, header=None, encoding='utf-8-sig')
                    read_ok = True
                except Exception:
                    pass
            
            if not read_ok:
                logger.error(f"Failed to read CSV: {csv_path}")
                return []

            # Determine columns (handle both headered and headerless)
            if df.shape[1] >= 2 and not str(df.columns[0]).isdigit():
                # Has headers - detect by name
                lower_cols = [str(c).lower() for c in df.columns]

                # Common variants
                candidates = [
                    ("topic", "content"),
                    ("disease", "description"),
                    ("section", "text"),
                    ("heading", "body"),
                ]
                topic_col = None
                content_col = None
                for tcol, ccol in candidates:
                    if tcol in lower_cols and ccol in lower_cols:
                        topic_col = df.columns[lower_cols.index(tcol)]
                        content_col = df.columns[lower_cols.index(ccol)]
                        break

                # If not found, fallback to first two columns
                if topic_col is None or content_col is None:
                    if len(df.columns) >= 2:
                        topic_col = df.columns[0]
                        content_col = df.columns[1]
                        logger.warning("Using first two columns as (topic, content)")
                    else:
                        logger.error("CSV missing required columns and cannot infer schema")
                        return []
            else:
                # Headerless - use indices 0 and 1
                topic_col = 0
                content_col = 1

            rows: List[RetrievedChunk] = []
            for _, row in df.iterrows():
                topic = str(row[topic_col]).strip()
                content = str(row[content_col]).strip()
                if content:
                    rows.append(
                        RetrievedChunk(
                            topic=topic or "general",
                            content=content,
                            score=0.0
                        )
                    )

            logger.info(f"Loaded {len(rows)} knowledge chunks")
            return rows

        except Exception as e:
            logger.error(f"Error loading medical knowledge CSV: {e}")
            return []

    def _build_index(self) -> None:
        """Build FAISS index from corpus."""
        chunks = self._load_corpus()
        
        if not chunks:
            logger.warning("No chunks to index")
            self._chunks = []
            return
            
        texts = [c.content for c in chunks]

        try:
            logger.info("Encoding corpus...")
            embeddings = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            embeddings = embeddings.astype(np.float32)

            dim = embeddings.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(embeddings)

            self._chunks = chunks
            self._index = index
            logger.info(f"FAISS index built with {len(chunks)} vectors")
            
        except Exception as e:
            logger.error(f"Error building FAISS index: {e}")
            self._chunks = []
            self._index = None

    def retrieve(self, query: str, top_k: int | None = None) -> List[RetrievedChunk]:
        """
        Retrieve most relevant chunks for query.
        
        Args:
            query: User query
            top_k: Number of results to return
            
        Returns:
            List of retrieved chunks with scores
        """
        self._ensure_initialized()
        
        if self._index is None or not self._chunks:
            return []
            
        text = (query or "").strip()
        if not text:
            return []

        k = top_k or self._settings.rag_top_k
        k = max(1, min(k, len(self._chunks)))

        try:
            q_emb = self._model.encode(
                [text],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            ).astype(np.float32)
            
            scores, indices = self._index.search(q_emb, k)

            results: List[RetrievedChunk] = []
            for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
                if 0 <= idx < len(self._chunks):
                    base = self._chunks[idx]
                    results.append(
                        RetrievedChunk(
                            topic=base.topic,
                            content=base.content,
                            score=float(score)
                        )
                    )
                    
            return results
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return []

    def build_context(self, query: str, top_k: int | None = None) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            query: User query
            top_k: Number of chunks to retrieve
            
        Returns:
            Concatenated context string
        """
        chunks = self.retrieve(query, top_k=top_k)
        
        if not chunks:
            return ""

        parts: List[str] = []
        total = 0
        limit = self._settings.max_context_chars

        for c in chunks:
            snippet = f"[{c.topic}] {c.content}".strip()
            if total + len(snippet) + 2 > limit:
                break
            parts.append(snippet)
            total += len(snippet) + 2
            
        return "\n\n".join(parts)