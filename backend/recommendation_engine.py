from __future__ import annotations

"""
Recommendation engine for Armenian medical triage.

Requirements satisfied:
- Must expose generate(symptoms: str, cleaned: str, diseases_text: str, specialist: str, context: str) -> str
- __init__ accepts specialist_mapper (even if not strictly needed right now)
- Armenian-only prompt; safe fallback if Gemini not configured/available
- No definitive diagnosis; careful language with "հնարավոր է", "կարող է լինել"
"""

import logging

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    _GENAI = True
except Exception:
    genai = None
    _GENAI = False
    logger.warning("google-generativeai not available; using fallback responses")


class RecommendationEngine:
    def __init__(
        self,
        gemini_model_name: str,
        gemini_api_key: str,
        temperature: float = 0.25,
        specialist_mapper=None,
    ):
        """
        Initialize the engine.

        Args:
            gemini_model_name: Gemini model ID (e.g., gemini-1.5-flash)
            gemini_api_key: API key to configure Gemini
            temperature: decoding temperature
            specialist_mapper: kept for architectural completeness; not required by generate()
        """
        self._model_name = gemini_model_name
        self._temperature = temperature
        self._specialist_mapper = specialist_mapper

        self._configured = False
        if _GENAI and gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self._configured = True
                logger.info("Gemini API configured")
            except Exception as e:
                logger.error(f"Failed to configure Gemini: {e}")

    def _build_prompt(
        self,
        symptoms: str,
        cleaned: str,
        diseases_text: str,
        specialist: str,
        context: str,
    ) -> str:
        """Build Armenian-safe prompt injecting retrieved CSV context."""
        ctx = context if context else "Տվյալներ չեն հայտնաբերվել"
        return (
            "Դուք բժշկական օգնական եք և պատասխանում եք միայն հայերենով։\n"
            "Խնդրում ենք չանել վերջնական ախտորոշում և չնշանակել դեղորայք։\n"
            "Օգտագործեք զգուշավո�� ձևակերպումներ՝ «հնարավոր է», «կարող է լինել»։\n\n"
            f"Օգտատիրոջ նկարագրած ախտանիշները:\n{symptoms}\n\n"
            f"Մշակված (մաքրված) ախտանիշներ:\n{cleaned}\n\n"
            f"Հնարավոր հիվանդություններ (համապատասխանությամբ):\n{diseases_text}\n\n"
            f"Առաջարկվող մասնագետ:\n{specialist}\n\n"
            f"Համապատասխան տեղեկություն (գիտելիքի բազայից):\n{ctx}\n\n"
            "Պատասխանը կազմեք հակիրճ և զգուշավոր՝ նշելով հնարավոր տարբերակներ,\n"
            "ինչ նախնական քայլեր կարելի է ձեռնարկել և երբ է պետք շտապ դիմել բժշկի։"
        )

    def generate(
        self,
        symptoms: str,
        cleaned: str,
        diseases_text: str,
        specialist: str,
        context: str,
    ) -> str:
        """
        Generate Armenian recommendation.

        Strict signature per requirement:
        generate(symptoms: str, cleaned: str, diseases_text: str, specialist: str, context: str) -> str
        """
        if not self._configured or not _GENAI:
            return self._fallback(symptoms, cleaned, diseases_text, specialist, context)

        prompt = self._build_prompt(symptoms, cleaned, diseases_text, specialist, context)
        try:
            model = genai.GenerativeModel(self._model_name)
            result = model.generate_content(prompt)
            text = getattr(result, "text", "").strip()
            if not text:
                return self._fallback(symptoms, cleaned, diseases_text, specialist, context)
            return text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return self._fallback(symptoms, cleaned, diseases_text, specialist, context)

    def _fallback(
        self,
        symptoms: str,
        cleaned: str,
        diseases_text: str,
        specialist: str,
        context: str,
    ) -> str:
        """Deterministic Armenian fallback when Gemini is not configured/available."""
        ctx = context if context else "Տվյալներ չեն գտնվել"
        parts = [
            "Հնարավոր է ներկայացնել հետևյալ մոտեցումը՝",
            "- Ուշադրություն դարձրեք ախտանիշների սկսելու ժամանակին և բնույթին։",
            "- Նշեք ուղեկցող նշանները՝ ջերմություն, ��նչահեղձություն, ցավ։",
            f"- Քննարկեք խնդիրը {specialist}-ի հետ և պլանավորեք զննություն։",
        ]
        guide = "\n".join(parts)
        return (
            f"Ձեր նկարագրած ախտանիշների հիման վրա հնարավոր է դիտարկել հետևյալ տարբերակները։\n\n"
            f"Հնարավոր հիվանդություններ (համապատասխանությամբ):\n{diseases_text}\n\n"
            f"Առաջարկվող մասնագետ՝ {specialist}։\n\n"
            f"Տեղեկատու (CSV-ից վերցված համատեքստ)\n{ctx}\n\n"
            f"{guide}"
        )
