"""Model output safety evaluation module."""
from __future__ import annotations
import logging
from backend.config import Settings

logger = logging.getLogger(__name__)

class ModelEvaluator:
    """
    Final safety layer for LLM responses.
    Ensures medical disclaimers and softens diagnostic language.
    """

    def __init__(self, settings: Settings):
        """Initialize with settings."""
        self._settings = settings

    def _soften_diagnostic_language(self, text: str) -> str:
        """
        Replace definitive medical language with cautious phrasing.
        
        Args:
            text: Raw LLM output
            
        Returns:
            Softened text
        """
        replacements = {
            "You have ": "You may have ",
            "you have ": "you may have ",
            "This is ": "This could be ",
            "this is ": "this could be ",
            "Diagnosis: ": "Possible considerations: ",
            "diagnosis: ": "possible considerations: ",
            # Armenian equivalents
            "Դուք ունեք ": "Դուք կարող եք ունենալ ",
            "դուք ունեք ": "դուք կարող եք ունենալ ",
            "Ախտորոշում՝ ": "Հնարավոր դիտարկումներ՝ ",
            "ախտորոշում՝ ": "հնարավոր դիտարկումներ՝ ",
        }
        
        result = text
        for src, dst in replacements.items():
            result = result.replace(src, dst)
            
        return result

    def enforce(self, raw_text: str) -> str:
        """
        Apply safety transformations and add disclaimer.
        
        Args:
            raw_text: Raw LLM response
            
        Returns:
            Safe, disclaimer-included response
        """
        text = (raw_text or "").strip()
        
        if not text:
            text = (
                "Չեմ կարող մեկնաբանել դատարկ հաղորդագրությունը, բայց "
                "առողջապահական մասնագետը կարող է մանրամասն վերլուծել ձեր ախտանիշները։"
            )

        # Soften language
        text = self._soften_diagnostic_language(text)

        # Add disclaimer if not present
        disclaimer = self._settings.disclaimer
        if disclaimer not in text:
            if not text.endswith("."):
                text = text.rstrip() + "."
            text = f"{text}\n\n{disclaimer}"

        return text