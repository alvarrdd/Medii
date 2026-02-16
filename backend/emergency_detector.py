"""Emergency symptom detection module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EmergencyDetector:
    """
    Keyword-based emergency symptom detector.
    
    Uses curated phrases to identify potentially life-threatening symptoms.
    """

    keywords: List[str]

    @classmethod
    def default(cls) -> EmergencyDetector:
        """Create detector with default emergency keywords (EN + HY)."""
        phrases = [
            # English
            "chest pain",
            "pressure in chest",
            "tightness in chest",
            "shortness of breath",
            "difficulty breathing",
            "trouble breathing",
            "cannot breathe",
            "stopped breathing",
            "loss of consciousness",
            "lost consciousness",
            "passed out",
            "fainted",
            "severe bleeding",
            "heavy bleeding",
            "uncontrolled bleeding",
            "bleeding that will not stop",
            "one side of the body is weak",
            "one-sided weakness",
            "face drooping",
            "face droop",
            "slurred speech",
            "sudden confusion",
            "seizure",
            "overdose",
            "took too many pills",
            "severe allergic reaction",
            "anaphylaxis",
            "swelling of the face",
            "swelling of the lips",
            "swelling of the tongue",
            "suicidal",
            "want to harm myself",
            "want to kill myself",
            # Armenian (HY)
            "կրծքավանդակի ցավ",
            "շնչահեղձություն",
            "շնչառության դժվարություն",
            "չեմ կարող շնչել",
            "շունչս կտրվում է",
            "գիտակցության կորուստ",
            "կորցրեցի գիտակցություն",
            "գլխապտույտ և ուշագնացություն",
            "ուժեղ արյունահոսություն",
            "արյունահոսություն չի դադարում",
            "դեմքի թուլություն",
            "դեմքի կախում",
            "խոսքի խանգարում",
            "հանկարծակի շփոթություն",
            "ցնցում",
            "անաֆիլաքսիա",
            "դեմքի այտուց",
            "շրթունքների այտուց",
            "լեզվի այտուց",
            "ինքնասպանության մտքեր",
            "ուզում եմ վնասել ինձ",
            "ուզում եմ սպանել ինձ",
        ]
        return cls(keywords=[p.lower() for p in phrases])

    def is_emergency(self, message: str) -> bool:
        """
        Check if message contains emergency keywords.
        
        Args:
            message: User message to check
            
        Returns:
            True if emergency detected, False otherwise
        """
        if not message:
            return False
            
        text = message.strip().lower()
        return any(phrase in text for phrase in self.keywords)
