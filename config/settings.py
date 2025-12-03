from pathlib import Path
import os

# --- Project Root ---
# This finds the 'ai-invoice-auditor' directory
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Config Paths ---
CONFIG_DIR = BASE_DIR / "config"
RULES_PATH = CONFIG_DIR / "rules.yaml"

# --- Data Paths (US-1) ---
DATA_DIR = BASE_DIR / "data"

# Input data folders
INCOMING_DIR = DATA_DIR / "incoming"

# Mock ERP data
MOCK_ERP_DIR = DATA_DIR / "mock_erp"
VENDORS_FILE = MOCK_ERP_DIR / "vendors.json"
PO_RECORDS_FILE = MOCK_ERP_DIR / "PO_records.json"
SKU_MASTER_FILE = MOCK_ERP_DIR / "sku_master.json"

# RAG data
VECTOR_STORE_DIR = DATA_DIR / "vector_store"

# Report Paths
REPORTS_DIR = BASE_DIR / "reports"
PROCESSED_DIR = REPORTS_DIR / "auto-processed"
REVIEW_DIR = REPORTS_DIR / "pending_review"
APPROVED_DIR = REPORTS_DIR / "approved"
REJECTED_DIR = REPORTS_DIR / "rejected"

# --- Log Path ---
LOGS_DIR = BASE_DIR / "logs"
APP_LOG_FILE = LOGS_DIR / "app.log"

# --- LLM Settings ---
# Since you have Bedrock access, LiteLLM will use these.
LLM_EXTRACTION_MODEL = "bedrock/cohere.command-r-plus-v1:0"
LLM_TRANSLATION_MODEL = "bedrock/cohere.command-r-plus-v1:0"
LLM_RAG_MODEL = "bedrock/cohere.command-r-plus-v1:0"
LLM_EMBEDDING_MODEL = "bedrock/amazon.titan-embed-text-v1" 

# --- FastAPI ERP Server (US-6) ---
ERP_HOST = "127.0.0.1"
ERP_PORT = 8000
ERP_URL = f"http://{ERP_HOST}:{ERP_PORT}"


# --- !! NEW SECTION: Fields for Translation (US-4) !! ---
# This tells the translation agent which fields to translate
TRANSLATION_FIELDS = {
    "header": [
        "vendor_name",
        "customer_name"
    ],
    "line_item": [
        "description"
    ]
}
# ---------------------------------------------------------


def setup_directories():
    """
    Creates all necessary directories for the project if they don't exist.
    """
    dirs = [
        INCOMING_DIR, PROCESSED_DIR, REVIEW_DIR, MOCK_ERP_DIR,
        VECTOR_STORE_DIR, REPORTS_DIR, APPROVED_DIR, REJECTED_DIR
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create a .gitignore in vector_store to ignore DB files
    gitignore_path = VECTOR_STORE_DIR / ".gitignore"
    if not gitignore_path.exists():
        with open(gitignore_path, "w") as f:
            f.write("*\n!.gitignore\n")
            
    print("All project directories created successfully.")

if __name__ == "__main__":
    # This allows you to run `python config/settings.py` to create folders
    setup_directories()
    print(f"Project base directory: {BASE_DIR}")
    print(f"Rules file path: {RULES_PATH}")
    print(f"Incoming invoices will be read from: {INCOMING_DIR}")

