import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("pipeline_history.jsonl")

def log_event(invoice_id: str, stage: str, status: str = "completed", message: str = ""):
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "invoice_id": invoice_id,
        "stage": stage,
        "status": status,
        "message": message
    }

    # Append as JSONL line
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
