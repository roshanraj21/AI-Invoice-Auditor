import os
import sys
import pytesseract
from PIL import Image
import pypdf
import docx
import json
from typing import Dict, Any, Optional

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

def _extract_text_from_pdf(filepath: str) -> str:
    """Extracts text from a PDF file."""
    try:
        reader = pypdf.PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"[FileUtils] Error reading PDF {filepath}: {e}")
        return ""

def _extract_text_from_image(filepath: str) -> str:
    """Extracts text from an image file using Tesseract OCR."""
    try:
        image = Image.open(filepath)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"[FileUtils] Error reading image {filepath} with Tesseract: {e}")
        print("           (Is Tesseract installed? `sudo apt-get install tesseract-ocr`)")
        return ""

def _extract_text_from_docx(filepath: str) -> str:
    """Extracts text from a DOCX file."""
    try:
        doc = docx.Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        print(f"[FileUtils] Error reading DOCX {filepath}: {e}")
        return ""

def get_file_content(filepath: str) -> str:
    """
    Reads a file (PDF, PNG, DOCX) and returns its text content as a string.
    
    This is our unified text extraction function.
    """
    filename = os.path.basename(filepath)
    file_ext = os.path.splitext(filename)[1].lower()
    
    print(f"[FileUtils] Reading file: {filename}")
    
    if file_ext == ".pdf":
        text = _extract_text_from_pdf(filepath)
    elif file_ext in [".png", ".jpg", ".jpeg", ".tiff"]:
        text = _extract_text_from_image(filepath)
    elif file_ext == ".docx":
        text = _extract_text_from_docx(filepath)
    else:
        print(f"[FileUtils] Unsupported file type: {file_ext}")
        return ""
        
    print(f"[FileUtils] Extracted {len(text)} chars from {filename}")
    return text

def read_metadata_file(invoice_filepath: str) -> Optional[Dict[str, Any]]:
    """
    Finds and reads the corresponding .meta.json file for an invoice.
    
    Example: For 'INV_EN_001.pdf', it looks for 'INV_EN_001.meta.json'
    """
    base_name = os.path.splitext(invoice_filepath)[0]
    meta_filepath = f"{base_name}.meta.json"
    
    if not os.path.exists(meta_filepath):
        print(f"[FileUtils] Warning: No metadata file found at: {meta_filepath}")
        return None
        
    try:
        with open(meta_filepath, 'r') as f:
            metadata = json.load(f)
        print(f"[FileUtils] Successfully read metadata from: {os.path.basename(meta_filepath)}")
        return metadata
    except Exception as e:
        print(f"[FileUtils] Error reading metadata file {meta_filepath}: {e}")
        return None