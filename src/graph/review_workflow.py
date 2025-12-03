import os
import sys
import json
import shutil
from pathlib import Path
from typing import TypedDict, Dict, Any, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

try:
    from config import settings
    from src.rag.vector_store import add_invoice_to_vector_store
except ImportError as e:
    print(f"ERROR: Failed to import modules in review_workflow.py: {e}")
    sys.exit(1)
    
class ReviewState(TypedDict):
    """State for the human review workflow"""
    # Inputs
    invoice_id: str
    human_decision: Literal["APPROVE", "REJECT"] # Changed from Approved/Rejected
    human_feedback: str

    invoice_dir_path: Path
    report_file_path: Path
    meta_file_path: Path
    report_data: Dict[str, Any]
    metadata: Dict[str, Any]
    target_dir: Path
    error: str | None

def load_invoice_files(state: ReviewState) -> Dict[str, Any]:
    """
    Load the report.json and meta.json files from the REVIEW_DIR
    based on the invoice_id.
    """
    print(f"--- [ReviewGraph] Node: Load Files ({state['invoice_id']}) ---")
    try:
        invoice_id = state['invoice_id']
        invoice_dir = settings.REVIEW_DIR / invoice_id
        
        if not invoice_dir.exists():
            raise FileNotFoundError(f"Invoice directory not found in REVIEW_DIR: {invoice_dir}")
            
        report_file = invoice_dir / f"{invoice_id}_report.json"
        meta_file = invoice_dir / f"{invoice_id}.meta.json"
        
        if not report_file.exists():
            raise FileNotFoundError(f"Report file not found: {report_file}")
            
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        metadata = {}
        if meta_file.exists():
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        return {
            "invoice_dir_path": invoice_dir,
            "report_file_path": report_file,
            "meta_file_path": meta_file,
            "report_data": report_data,
            "metadata": metadata,
            "error": None
        }
    except Exception as e:
        print(f"[ReviewGraph] ERROR loading files: {e}")
        return {"error": str(e)}

def update_report_with_review(state: ReviewState) -> Dict[str, Any]:
    """
    Update the loaded report_data with the human's decision and feedback.
    """
    print(f"--- [ReviewGraph] Node: Update Report ({state['invoice_id']}) ---")
    if state.get("error"):
        return {}

    try:
        report_data = state['report_data']
        decision = state['human_decision']
        feedback = state['human_feedback']
        
        decision = decision.upper()
        report_data["validation_status"] = decision # e.g., "APPROVE" or "REJECT"
        report_data["human_review"] = {
            "decision": decision,
            "feedback": feedback,
            "reviewed_at": datetime.now().isoformat(),
            "reviewed_by": "human_reviewer"
        }
        
        if decision == "APPROVE":
            target_dir = settings.APPROVED_DIR
        else:
            target_dir = settings.REJECTED_DIR
            
        target_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "report_data": report_data,
            "target_dir": target_dir,
            "error": None
        }
    except Exception as e:
        print(f"[ReviewGraph] ERROR updating report: {e}")
        return {"error": str(e)}

def index_reviewed_invoice(state: ReviewState) -> Dict[str, Any]:
    """
    Calls the vector store to index the human-reviewed invoice
    (both Approved and Rejected).
    """
    print(f"--- [ReviewGraph] Node: Index Reviewed Invoice ({state['invoice_id']}) ---")
    if state.get("error"):
        return {}

    try:
        # The report_data is already updated with human feedback
        report_data = state['report_data']
        metadata = state['metadata']
        
        print(f"[ReviewGraph] Indexing invoice (Decision: {report_data['human_review']['decision']})...")
        add_invoice_to_vector_store(
            report_data=report_data,
            file_metadata=metadata
        )
        print(f"[ReviewGraph] Indexing complete.")
        return {"error": None}
        
    except Exception as e:
        print(f"[ReviewGraph] ERROR indexing invoice: {e}")
        return {"error": f"Failed to index invoice: {e}"}

def move_files_to_final_dir(state: ReviewState) -> Dict[str, Any]:
    """
    Moves the entire invoice directory (with updated report)
    from REVIEW_DIR to the target_dir (APPROVED_DIR or REJECTED_DIR).
    """
    print(f"--- [ReviewGraph] Node: Move Files ({state['invoice_id']}) ---")
    if state.get("error") and "Failed to index" not in state.get("error", ""):
         return {} 

    try:
        invoice_id = state['invoice_id']
        source_dir = state['invoice_dir_path']
        target_dir = state['target_dir']
        report_data = state['report_data']
        
        target_invoice_dir = target_dir / invoice_id

        if target_invoice_dir.exists():
            shutil.rmtree(target_invoice_dir)
        shutil.move(str(source_dir), str(target_invoice_dir))
        
        # Re-save the report.json *in the new location* with human feedback
        updated_report_path = target_invoice_dir / f"{invoice_id}_report.json"
        with open(updated_report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
        print(f"[ReviewGraph] ✅ Review complete. Files moved to: {target_invoice_dir}")
        return {"error": None}
        
    except Exception as e:
        print(f"[ReviewGraph] ERROR moving files: {e}")
        return {"error": str(e)}

def build_review_workflow():
    """Builds and compiles the review workflow"""
    print("[ReviewWorkflowBuilder] Building human review graph...")
    
    workflow = StateGraph(ReviewState)
    
    workflow.add_node("load_invoice_files", load_invoice_files)
    workflow.add_node("update_report", update_report_with_review)
    workflow.add_node("index_invoice", index_reviewed_invoice)
    workflow.add_node("move_files_to_final_dir", move_files_to_final_dir)
    
    workflow.set_entry_point("load_invoice_files")
    workflow.add_edge("load_invoice_files", "update_report")
    workflow.add_edge("update_report", "index_invoice")
    workflow.add_edge("index_invoice", "move_files_to_final_dir")

    workflow.add_edge("move_files_to_final_dir", END)
    
    app = workflow.compile()
    print("[ReviewWorkflowBuilder] ✅ Human review graph compiled.")
    return app

try:
    review_app = build_review_workflow()
except Exception as e:
    print(f"FATAL: Could not build review workflow: {e}")
    review_app = None

if __name__ == "__main__":
    if review_app:
        print("\n✅ Review workflow ready. Import 'review_app' from this module to run.")
    else:
        print("\n❌ Review workflow build FAILED.")