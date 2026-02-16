"""Specialist recommendation module."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    _HAS_FUZZ = True
except Exception:
    _HAS_FUZZ = False

@dataclass(frozen=True)
class SpecialistMapper:
    """
    Maps diseases to medical specialists using a CSV of disease→specialist.
    Provides fallbacks and simple fuzzy matching.
    """
    # List of (disease_lower, specialist)
    _rules: List[Tuple[str, str]]
    _fallback: str = "Թերապևտ / Ընտանեկան բժիշկ"

    def _norm(self, s: str) -> str:
        s = (s or "").lower().strip()
        s = re.sub(r"[\s,;:՝՛։\.\-_/]+", " ", s)
        return s

    @classmethod
    def from_csv(cls, csv_path: Path) -> "SpecialistMapper":  # ✅ Fixed forward reference
        """
        Load disease→specialist mapping from CSV.
        Accepts CSVs with two columns: disease, specialist (any header names).
        """
        if not csv_path.exists():
            logger.warning(f"CSV not found at {csv_path}, using fallback only")
            return cls(_rules=[])

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
                # Force headerless read for Armenian CSVs
                try:
                    df = pd.read_csv(csv_path, header=None, encoding='utf-8-sig')
                    read_ok = True
                except Exception:
                    pass
            
            if not read_ok:
                logger.error(f"Failed to read CSV: {csv_path}")
                return cls(_rules=[])

            if df.shape[1] < 2:
                logger.error("Specialist CSV must have at least two columns (disease,specialist)")
                return cls(_rules=[])

            # Determine columns (handle both headered and headerless)
            if df.shape[1] >= 2 and not str(df.columns[0]).isdigit():
                # Has headers
                col0 = df.columns[0]
                col1 = df.columns[1]
            else:
                # Headerless - use indices
                col0 = 0
                col1 = 1

            rules: List[Tuple[str, str]] = []
            for _, row in df.iterrows():
                disease = str(row[col0]).strip()
                specialist = str(row[col1]).strip() or cls._fallback
                if disease and specialist:
                    rules.append((disease.lower(), specialist))

            # De-duplicate
            seen: Dict[str, str] = {}
            for d, sp in rules:
                if d not in seen:
                    seen[d] = sp
            rules = list(seen.items())

            logger.info(f"Loaded {len(rules)} disease→specialist rules")
            return cls(_rules=rules)
            
        except Exception as e:
            logger.error(f"Error loading specialist CSV: {e}")
            return cls(_rules=[])

    def recommend_all(self, diseases: List[str]) -> Dict[str, str]:
        """Map every predicted disease to its best-matching specialist.
        Returns a dict {disease_name: specialist_name}. Unmatched diseases map to fallback.
        """
        mapping: Dict[str, str] = {d: s for d, s in self._rules}
        keys = list(mapping.keys())
        result: Dict[str, str] = {}
        for cand in diseases or []:
            q = self._norm(cand)
            # Exact
            if q in mapping:
                result[cand] = mapping[q]
                continue
            # Substring
            matched = False
            for k in keys:
                if q in k or k in q:
                    result[cand] = mapping[k]
                    matched = True
                    break
            if matched:
                continue
            # Fuzzy
            if _HAS_FUZZ:
                best_k: Optional[str] = None
                best_sc = 0.0
                for k in keys:
                    sc = fuzz.token_set_ratio(q, k)
                    if sc > best_sc:
                        best_sc = sc
                        best_k = k
                if best_k is not None and best_sc >= 80.0:
                    result[cand] = mapping[best_k]
                    continue
            # Fallback if still not matched
            result[cand] = self._fallback
        return result

    def recommend(self, diseases: List[str]) -> str:
        """Backwards-compatible single specialist recommendation.
        Aggregates across diseases and returns the most likely specialist.
        """
        if not diseases:
            return self._fallback

        per_disease = self.recommend_all(diseases)
        # Aggregate scores: count frequency per specialist
        scores_by_specialist: Dict[str, float] = {}
        for sp in per_disease.values():
            scores_by_specialist[sp] = scores_by_specialist.get(sp, 0.0) + 1.0
        return max(scores_by_specialist.items(), key=lambda x: x[1])[0]