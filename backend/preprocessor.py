"""Armenian-aware symptom preprocessor"""

import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

ARMENIAN_RANGE = r"\u0531-\u0587\u0589-\u058A"
ENGLISH_RANGE = r"a-zA-Z"
ALLOWED = rf"[{ARMENIAN_RANGE}{ENGLISH_RANGE}0-9 ,;՝՛։\s-]"

class SymptomPreprocessor:
    def __init__(self):
        self._clean_pattern = re.compile(rf"[^{ALLOWED}]", flags=re.UNICODE | re.IGNORECASE)

        self.synonyms: Dict[str, str] = {
            "headache": "headache", "head ache": "headache", "head pain": "headache",
            "fever": "fever", "temperature": "fever", "high temp": "fever",
            "cough": "cough", "coughing": "cough",
            "sore throat": "sore throat", "throat pain": "sore throat",
            "nausea": "nausea", "vomiting": "vomiting", "throwing up": "vomiting",
            "diarrhea": "diarrhea", "loose stool": "diarrhea",
            "chest pain": "chest pain", "shortness of breath": "shortness of breath",
            "dizziness": "dizziness", "fatigue": "fatigue", "weakness": "weakness",

            "գլխացավ": "headache", "գլխի ցավ": "headache", "գլուխս ցավում է": "headache",
            "տենդ": "fever", "ջերմություն": "fever", "բարձր ջերմություն": "fever",
            "հազ": "cough", "հազում եմ": "cough",
            "կոկորդի ցավ": "sore throat", "կոկորդս ցավում է": "sore throat",
            "սրտխառնոց": "nausea", "փսխում": "vomiting", "փսխում եմ": "vomiting",
            "փորլուծ": "diarrhea", "փորհատ": "diarrhea", "որովայնի ցավ": "abdominal pain",
            "կրծքավանդակի ցավ": "chest pain", "շնչառության դժվարություն": "shortness of breath",
            "գլխապտույտ": "dizziness", "թուլություն": "weakness", "հոգնածություն": "fatigue",
        }

    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        text = text.strip().lower()
        text = re.sub(r"\s+եւ\s+", " և ", text)
        text = re.sub(r"եւ\s+", "և ", text)
        text = re.sub(r"\s+եւ", " և", text)
        text = self._clean_pattern.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _apply_synonyms(self, text: str) -> str:
        words = text.split()
        result = []
        for w in words:
            result.append(self.synonyms.get(w, w))
        return " ".join(result)

    def _split_symptoms(self, text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[;,]|\s+(և|ու|և էլ|նաև)\s+", text)
        out: List[str] = []
        for p in parts:
            p = p.strip()
            if p and p not in ("և", "ու", "և էլ", "նաև"):
                if len(p) >= 3:
                    out.append(p)
        seen = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def preprocess(self, text: str) -> Tuple[str, List[str]]:
        normalized = self._normalize(text)
        with_synonyms = self._apply_synonyms(normalized)
        symptom_list = self._split_symptoms(with_synonyms)
        joined = " և ".join(symptom_list) if symptom_list else with_synonyms

        logger.debug(f"Preprocess → joined: {joined} | list: {symptom_list}")
        return joined, symptom_list