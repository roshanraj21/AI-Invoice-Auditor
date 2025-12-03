import os
import sys
from typing import Dict, Any, Optional

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

try:
    from config.settings import LLM_TRANSLATION_MODEL, TRANSLATION_FIELDS
    from src.llm.litellm_gateway import LLMGateway
except ImportError as e:
    print(f"Error importing modules in translation.py: {e}")
    print("Please ensure all dependencies are installed and paths are correct.")
    sys.exit(1)

# Initialize our LLM Gateway
llm_gateway = LLMGateway(model=LLM_TRANSLATION_MODEL)


def translate_invoice_data(data: Dict[str, Any], language_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Orchestrates the translation of key fields in the extracted data.
    Skip translation if the invoice language is already English.
    """
    if not data or "error" in data:
        return data
        
    if language_code and language_code.lower() == 'en':
        print(f"\n[TranslationAgent] Skipping translation: Language is already EN.")
        data["translation_confidence"] = 1.0
        return data
        
    print(f"\n[TranslationAgent] Starting translation (Language: {language_code or 'unknown'})...")
    confidences = []

    try:
        # ✅ 1. Translate header fields
        for field in TRANSLATION_FIELDS.get("header", []):
            if field in data and data[field]:
                original = data[field]
                result = llm_gateway.call_for_translation(original)
                data[field] = result["text"]
                confidences.append(result["confidence"])

        # ✅ 2. Translate line item fields
        if "line_items" in data and isinstance(data["line_items"], list):
            for item in data["line_items"]:
                for field in TRANSLATION_FIELDS.get("line_item", []):
                    if field in item and item[field]:
                        original = item[field]
                        result = llm_gateway.call_for_translation(original)
                        item[field] = result["text"]    
                        confidences.append(result["confidence"])

        # ✅ Compute mean confidence
        data["translation_confidence"] = sum(confidences) / len(confidences) if confidences else None
        print("[TranslationAgent] Translation complete.")
        return data

    except Exception as e:
        print(f"[TranslationAgent] Unexpected error: {e}")
        return {"error": f"Unexpected error in translation: {e}"}
