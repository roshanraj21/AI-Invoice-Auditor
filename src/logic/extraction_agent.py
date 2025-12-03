import os
import sys
from typing import Dict, Any

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.llm.litellm_gateway import LLMGateway
    from src.models.invoice import InvoiceData
    from config.settings import LLM_EXTRACTION_MODEL
    from src.utils.file_utils import get_file_content

except ImportError as e:
    print(f"Error importing modules in extraction.py: {e}")
    print("Please ensure all dependencies are installed and paths are correct.")
    sys.exit(1)

# Initialize our LLM Gateway
llm_gateway = LLMGateway(model=LLM_EXTRACTION_MODEL)

def extract_invoice_data(filepath: str) -> Dict[str, Any]:
    """
    Orchestrates the extraction of structured data from an invoice file.
    This is the simplified "text-only" pipeline.
    
    Args:
        filepath: The full path to the invoice file.
        
    Returns:
        A dictionary containing the structured invoice data or an error message.
    """
    filename = os.path.basename(filepath)
    print(f"\n[ExtractionAgent] Starting extraction for: {filename}")
    
    # Extract text from file
    invoice_text = get_file_content(filepath)
    
    if not invoice_text:
        print(f"[ExtractionAgent] No text could be extracted from {filename}.")
        return {"error": f"No text content found in {filename}."}
    
    print(f"[ExtractionAgent] Extracted {len(invoice_text)} characters of text")
    
    try:
        # Call LLM with PydanticOutputParser for structured extraction
        structured_data = llm_gateway.call_for_structured_extraction(
            invoice_text=invoice_text,
            pydantic_schema=InvoiceData,
            original_filename=filename
        )
        
        if "error" in structured_data:
            print(f"[ExtractionAgent] Extraction failed: {structured_data['error']}")
            return structured_data
            
        print("[ExtractionAgent] ✓ Extraction successful.")
        return structured_data

    except Exception as e:
        print(f"[ExtractionAgent] ✗ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Unexpected error in extraction: {str(e)}"}