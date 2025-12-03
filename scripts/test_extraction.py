import os
import sys
import json
from pprint import pprint

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

try:
    from logic.extraction_agent import extract_invoice_data
    from logic.translation_agent import translate_invoice_data
    from src.utils.file_utils import read_metadata_file # <-- NEW IMPORT
    from config.settings import INCOMING_DIR
except ImportError as e:
    print(f"Error: Could not import modules in test_extraction.py: {e}")
    print("Please ensure __init__.py files exist and paths are correct.")
    sys.exit(1)

def test_extraction_pipeline():
    """
    Runs a test on a single invoice file from the incoming directory.
    """
    print("--- Starting Extraction Test ---")
    
    # --- !!! ---
    # --- !!! --- EDIT THIS FILENAME to match a file in your incoming folder
    # --- !!! ---
    TEST_INVOICE_FILENAME = "INV_DE_004.pdf" 
    # --- !!! ---
    
    test_filepath = os.path.join(INCOMING_DIR, TEST_INVOICE_FILENAME)
    
    if not os.path.exists(test_filepath):
        print(f"Error: Test file not found at: {test_filepath}")
        print("Please edit 'TEST_INVOICE_FILENAME' in 'scripts/test_extraction.py'")
        return

    # 1. --- Test Extraction (US-3) ---
    extracted_data = extract_invoice_data(test_filepath)
    
    if "error" in extracted_data:
        print("\n--- EXTRACTION FAILED ---")
        pprint(extracted_data)
        return
        
    print("\n--- EXTRACTION SUCCESSFUL (US-3) ---")
    pprint(extracted_data)
    
    # --- NEW: Read Metadata ---
    metadata = read_metadata_file(test_filepath)
    language = metadata.get("language") if metadata else None
    # --------------------------

    # 2. --- Test Translation (US-4) ---
    print("\n--- Starting Translation Test (US-4) ---")
    # Pass the language code to the translation function
    translated_data = translate_invoice_data(extracted_data, language_code=language)
    
    print("\n--- TRANSLATION COMPLETE (US-4) ---")
    pprint(translated_data)
    
    # 3. --- Save output for inspection ---
    output_filename = os.path.join(project_root, "test_output.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n--- Test output saved to: {output_filename} ---")

if __name__ == "__main__":
    # Ensure your AWS credentials are set in your environment!
    # export AWS_ACCESS_KEY_ID="your_key"
    # export AWS_SECRET_ACCESS_KEY="your_secret"
    # export AWS_REGION_NAME="us-east-1"
    
    test_extraction_pipeline()