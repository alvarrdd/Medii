"""Armenian-first symptom preprocessor."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

ARMENIAN_RANGE = r"\u0531-\u0587\u0589-\u058A"
ENGLISH_RANGE = r"a-zA-Z"
ALLOWED = rf"[{ARMENIAN_RANGE}{ENGLISH_RANGE}0-9 ,;՝՛։\s-]"


class SymptomPreprocessor:
    """
    Normalize and lightly canonicalize symptom text.

    Design choice:
    - Keep Armenian text in Armenian (dataset is Armenian-heavy).
    - Map common English symptom phrases to Armenian equivalents.
    """

    def __init__(self):
        self._clean_pattern = re.compile(rf"[^{ALLOWED}]", flags=re.UNICODE | re.IGNORECASE)
        self._arm_char_re = re.compile(rf"[{ARMENIAN_RANGE}]")

        # Phrase-level replacements (longest first when applied).
        self._phrase_map: Dict[str, str] = {
            # English -> Armenian
            "shortness of breath": "շնչահեղձություն",
            "difficulty breathing": "շնչառության դժվարություն",
            "chest pain": "կրծքավանդակի ցավ",
            "abdominal pain": "որովայնի ցավ",
            "stomach pain": "որովայնի ցավ",
            "sore throat": "կոկորդի ցավ",
            "throat pain": "կոկորդի ցավ",
            "head ache": "գլխացավ",
            "head pain": "գլխացավ",
            "headache": "գլխացավ",
            "high fever": "բարձր ջերմություն",
            "fever": "ջերմություն",
            "temperature": "ջերմություն",
            "coughing": "հազ",
            "cough": "հազ",
            "nausea": "սրտխառնոց",
            "vomiting": "փսխում",
            "throwing up": "փսխում",
            "diarrhea": "լուծ",
            "loose stool": "լուծ",
            "dizziness": "գլխապտույտ",
            "fatigue": "հոգնածություն",
            "weakness": "թուլություն",
            # Armenian normalization
            "եւ": "և",
            "գլխի ցավ": "գլխացավ",
            "փորլուծ": "լուծ",
            "կրծքավանդակային ցավ": "կրծքավանդակի ցավ",
        }
        # Spoken Armenian body-part variants -> canonical medical form.
        self._bodypart_map: Dict[str, str] = {
            "ատամ": "ատամի",
            "ծունկ": "ծնկի",
            "ծնկ": "ծնկի",
            "գլուխ": "գլխի",
            "փոր": "որովայնի",
            "որովայն": "որովայնի",
            "մեջք": "մեջքի",
            "կոկորդ": "կոկորդի",
            "ականջ": "ականջի",
            "աչք": "աչքի",
            "սիրտ": "կրծքավանդակի",
        }

    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        value = text.strip().lower()
        value = self._clean_pattern.sub(" ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _apply_phrases(self, text: str) -> str:
        if not text:
            return text
        out = text
        for src in sorted(self._phrase_map.keys(), key=len, reverse=True):
            dst = self._phrase_map[src]
            out = re.sub(rf"\b{re.escape(src)}\b", dst, out)
        return re.sub(r"\s+", " ", out).strip()

    def _split_symptoms(self, text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[;,]|\s+(և|ու|նաև|and|with)\s+", text)
        out: List[str] = []
        for p in parts:
            if not isinstance(p, str):
                continue
            chunk = p.strip()
            if not chunk or chunk in {"և", "ու", "նաև", "and", "with"}:
                continue
            if len(chunk) >= 2:
                out.append(chunk)
        seen = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def _normalize_spoken_pain(self, text: str) -> str:
        if not text:
            return text
        out = text
        # e.g. "ատամս ցավում է", "ծունկը ցավումա", "գլուխս ցավում է"
        for src, dst in self._bodypart_map.items():
            out = re.sub(
                rf"\b{re.escape(src)}(?:ը|ս|ն)?\s+ցավում\s*(?:է|ա)?\b",
                f"{dst} ցավ",
                out,
            )
            out = re.sub(
                rf"\b{re.escape(src)}(?:ը|ս|ն)?\s*ցավ\b",
                f"{dst} ցավ",
                out,
            )
        out = re.sub(r"\bցավը\b", "ցավ", out)
        return re.sub(r"\s+", " ", out).strip()

    def preprocess(self, text: str) -> Tuple[str, List[str]]:
        normalized = self._normalize(text)
        normalized = self._normalize_spoken_pain(normalized)
        canonical = self._apply_phrases(normalized)
        symptom_list = self._split_symptoms(canonical)
        joined = " և ".join(symptom_list) if symptom_list else canonical

        # Keep output Armenian when possible for Armenian dataset match.
        if not self._arm_char_re.search(joined):
            joined = self._apply_phrases(joined)

        logger.debug("Preprocess -> joined: %s | list: %s", joined, symptom_list)
        return joined, symptom_list
