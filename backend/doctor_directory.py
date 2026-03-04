"""Doctor directory loader and matcher."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoctorRecord:
    name: str
    clinic: str
    phone: str
    specialty: str


class DoctorDirectory:
    """Stores doctors and returns best matches for a specialist name."""

    def __init__(self, records: List[DoctorRecord]):
        self._records = records

    @staticmethod
    def _norm(text: str) -> str:
        value = (text or "").lower().strip()
        value = re.sub(r"[^\w\s\u0531-\u0587/+()-]", " ", value, flags=re.UNICODE)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    @classmethod
    def from_csv(cls, csv_path: Path) -> "DoctorDirectory":
        if not csv_path.exists():
            logger.warning("Doctor CSV not found at %s", csv_path)
            return cls([])

        df = None
        for enc in ("utf-8-sig", "utf-8"):
            try:
                # CSV is often headerless for this file.
                df = pd.read_csv(csv_path, header=None, encoding=enc)
                break
            except Exception:
                continue

        if df is None or df.shape[1] < 4:
            logger.error("Doctor CSV must have 4 columns: name, clinic, phone, specialty")
            return cls([])

        records: List[DoctorRecord] = []
        for _, row in df.iterrows():
            name = str(row[0]).strip()
            clinic = str(row[1]).strip()
            phone = str(row[2]).strip()
            specialty = str(row[3]).strip()
            if not name or not specialty:
                continue
            records.append(
                DoctorRecord(
                    name=name,
                    clinic=clinic,
                    phone=phone,
                    specialty=specialty,
                )
            )

        logger.info("Loaded %s doctor records", len(records))
        return cls(records)

    def find_by_specialist(self, specialist_name: str, limit: int = 4) -> List[DoctorRecord]:
        if not specialist_name or not self._records:
            return []

        query = self._norm(specialist_name)
        query_parts = [p.strip() for p in re.split(r"/|,| և | and ", query) if p.strip()]
        query_tokens = set(query.split()) | set(" ".join(query_parts).split())

        scored = []
        for rec in self._records:
            spec = self._norm(rec.specialty)
            spec_tokens = set(spec.split())

            inter = len(query_tokens & spec_tokens)
            overlap = inter / max(1, len(query_tokens))
            phrase = 1.0 if any(part and part in spec for part in query_parts) else 0.0
            contains = 1.0 if query in spec or spec in query else 0.0
            score = 0.55 * overlap + 0.30 * phrase + 0.15 * contains

            if score > 0:
                scored.append((score, rec, spec))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate by doctor name+phone and preserve order helper.
        def _add_unique(target: List[DoctorRecord], seen: Dict[str, bool], rec: DoctorRecord) -> bool:
            key = f"{rec.name}|{rec.phone}"
            if key in seen:
                return False
            seen[key] = True
            target.append(rec)
            return True

        # For combined specialists (e.g., "Ալերգոլոգ / Ակնաբույժ"), enforce diversity:
        # take top matches per part first, then fill remaining slots globally.
        part_buckets: Dict[str, List[DoctorRecord]] = {}
        if len(query_parts) >= 2:
            for part in query_parts:
                part_buckets[part] = [rec for _, rec, spec in scored if part in spec]

        out: List[DoctorRecord] = []
        seen: Dict[str, bool] = {}
        if part_buckets:
            progressed = True
            while progressed and len(out) < max(1, limit):
                progressed = False
                for part in query_parts:
                    bucket = part_buckets.get(part, [])
                    if not bucket:
                        continue
                    rec = bucket.pop(0)
                    if _add_unique(out, seen, rec):
                        progressed = True
                    if len(out) >= max(1, limit):
                        break

        for _, rec, _ in scored:
            if len(out) >= max(1, limit):
                break
            _add_unique(out, seen, rec)
        return out
