import os
import sys
import json
from typing import TypedDict, List, Dict, Any, Optional
from pathlib import Path
import shutil
from langgraph.graph import StateGraph, END

# --- Add project root to path ----
# (This assumes workflow.py is in src/graph/workflow.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.utils.file_utils import read_metadata_file
    from src.utils.pipeline_logger import log_event
    
    from src.logic.extraction_agent import extract_invoice_data
    from src.logic.translation_agent import translate_invoice_data
    from src.logic.validation_agent import validate_invoice_data
    from src.logic.reporting_agent import generate_report
    from src.rag.vector_store import add_invoice_to_vector_store
    from config.settings import PROCESSED_DIR, REVIEW_DIR
    from src.utils.report_utils import generate_html_report
except ImportError as e:
    print(f"ERROR: Failed to import modules in workflow.py: {e}")
    sys.exit(1)

# 1. DEFINE THE STATE
class InvoiceState(TypedDict):
    """State that flows through the graph"""
    filepath: str
    extracted_data: Optional[Dict[str, Any]]
    language: Optional[str]
    invoice_data: Optional[Dict[str, Any]]
    translation_confidence: Optional[float]

    rules_results: Optional[List[Dict[str, Any]]] 
    validation_status: Optional[str]  # "PASSED" or "FAILED"
    
    report_data: Optional[Dict[str, Any]] # The final JSON report object
    report_paths: Optional[Dict[str, str]] # {"json": "...", "html": "..."}
    is_indexed: bool
    error: Optional[str]

def _move_invoice_files(source_filepath_str: str, target_base_dir: Path) -> Path:
    """Moves invoice file and metadata to target directory"""
    try:
        source_filepath = Path(source_filepath_str)
        invoice_id = source_filepath.stem
        
        target_invoice_dir = target_base_dir / invoice_id
        target_invoice_dir.mkdir(parents=True, exist_ok=True)
        
        # Move main file
        target_invoice_path = target_invoice_dir / source_filepath.name
        shutil.move(str(source_filepath), str(target_invoice_path))
        print(f"[Graph] Moved invoice to: {target_invoice_path}")
        
        # Move metadata
        source_meta_path = source_filepath.with_suffix('.meta.json')
        if source_meta_path.exists():
            target_meta_path = target_invoice_dir / f"{invoice_id}.meta.json"
            shutil.move(str(source_meta_path), str(target_meta_path))
            print(f"[Graph] Moved metadata to: {target_meta_path}")
            
        return target_invoice_dir
        
    except Exception as e:
        print(f"[Graph] ERROR moving files: {e}")
        raise

# --- WORKFLOW NODES ---
def extraction_node(state: InvoiceState) -> Dict[str, Any]:
    """Extract data from invoice"""
    print("--- [Graph] Node: Extract ---")
    filepath = state.get('filepath')
    invoice_id = Path(filepath).stem
    log_event(invoice_id, "detected", "completed", f"Started processing {invoice_id}")
    try:
        filepath = state['filepath']
        print(f"[Graph] Processing: {os.path.basename(filepath)}")
        extracted_data = extract_invoice_data(filepath)
        
        if not extracted_data or "error" in extracted_data:
            error_msg = extracted_data.get("error", "Unknown extraction error")
            log_event(invoice_id, "extraction", "error", error_msg)
            raise Exception(f"Extraction failed: {error_msg}")
        
        log_event(invoice_id, "extraction", "completed", "Extraction successful")
        # print(f"[Graph] Extraction successful")
        return {"extracted_data": extracted_data, "error": None}
        
    except Exception as e:
        # print(f"[Graph] Extraction FAILED: {e}")
        log_event(invoice_id, "extraction", "error", str(e))
        return {"error": str(e), "extracted_data": None}

def translation_node(state: InvoiceState) -> Dict[str, Any]:
    """Translate invoice data to English"""
    print("--- [Graph] Node: Translate ---")
    filepath = state['filepath']
    invoice_id = Path(filepath).stem
    try:
        if state.get('error') or not state.get('extracted_data'):
            raise Exception("Cannot translate - extraction failed")
        
        filepath = state['filepath']
        extracted_data = state['extracted_data']
        
        metadata = read_metadata_file(filepath)
        language = metadata.get("language", "en") if metadata else "en"
        translated_data = translate_invoice_data(extracted_data, language_code=language)
        
        if not translated_data or "error" in translated_data:
            error_msg = translated_data.get("error", "Unknown translation error")
            log_event(invoice_id, "translation", "error", str(translated_data.get("error")))
            raise Exception(f"Translation failed: {error_msg}")
        
        print("[Graph] Translation successful")
        log_event(invoice_id, "translation", "completed", "Translation successful")
        return {
                "invoice_data": translated_data, 
                "language": language, 
                "translation_confidence": translated_data.get("translation_confidence"),
                "error": None
            }
    except Exception as e:
        print(f"[Graph] Translation FAILED: {e}")
        log_event(invoice_id, "translation", "error", str(e))
        return {"error": str(e), "invoice_data": None}

def validation_node(state: InvoiceState) -> Dict[str, Any]:
    """Validate invoice data using manual rules only"""
    print("--- [Graph] Node: Validate ---")
    filepath = state['filepath']
    invoice_id = Path(filepath).stem
    try:
        if state.get('error') or not state.get('invoice_data'):
            msg = "Cannot validate - prior step failed"
            log_event(invoice_id, "validation", "error", msg)
            raise Exception("Cannot validate - prior step failed")
        
        invoice_data = state['invoice_data']
        
        # This function returns the list of rule findings
        rules_results = validate_invoice_data(invoice_data)
        
        failed_checks = len([r for r in rules_results if r['status'] == 'FAILED'])
        status = "FAILED" if failed_checks > 0 else "PASSED"
        
        # print(f"[Graph] Validation {status} ({failed_checks} failures)")
        log_event(invoice_id, "validation", "completed", f"{status} ({failed_checks} issues)")
        return {
            "rules_results": rules_results,
            "validation_status": status,
            "error": None
        }
        
    except Exception as e:
        log_event(invoice_id, "validation", "error", str(e))
        return {
            "rules_results": [{
                "rule_name": "Validation Error",
                "status": "FAILED",
                "message": str(e)
            }],
            "validation_status": "FAILED",
            "error": str(e)
        }

def generate_report_node(state: InvoiceState) -> Dict[str, Any]:
    """Generate final JSON report"""
    print("--- [Graph] Node: Generate Report ---")
    filepath = state['filepath']
    invoice_id = Path(filepath).stem
    try:
        invoice_data = state.get('invoice_data')
        rules_results = state.get('rules_results')
        
        if not invoice_data:
            invoice_data = {"invoice_id": Path(state['filepath']).stem, "error": state.get('error', 'Data extraction failed')}
        if not rules_results:
            rules_results = [{"rule_name": "Pipeline Error", "status": "FAILED", "message": state.get('error', 'Unknown error')}]
        
        # Call the reporting agent
        report_data = generate_report(
            invoice_data=invoice_data,
            validation_rules=rules_results
        )
        
        log_event(invoice_id, "report_generation", "completed", "Report generated")
        return {"report_data": report_data, "error": None}
        
    except Exception as e:
        log_event(invoice_id, "report_generation", "error", str(e))
        return {
            "report_data": {"error": str(e)},
            "error": str(e)
        }

def save_and_index_node(state: InvoiceState) -> Dict[str, Any]:
    """Success path: Save JSON, HTML, and index for RAG"""
    print("--- [Graph] Node: Save & Index (Success) ---")
    filepath = state['filepath']
    invoice_id = Path(filepath).stem
    try:
        filepath = state['filepath']
        invoice_id = Path(filepath).stem
        report_data = state['report_data']
        
        target_dir = _move_invoice_files(filepath, PROCESSED_DIR)
        
        # --- Save JSON Report ---
        report_path_json = target_dir / f"{invoice_id}_report.json"
        with open(report_path_json, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"[Graph] JSON Report saved: {report_path_json}")

        # --- Save HTML Report ---
        report_path_html = target_dir / f"{invoice_id}_report.html"
        html_content = generate_html_report(report_data)
        with open(report_path_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[Graph] HTML Report saved: {report_path_html}")
        
        # Load metadata for indexing
        meta_path = target_dir / f"{invoice_id}.meta.json"
        file_metadata = {}
        if meta_path.exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                file_metadata = json.load(f)
        
        # Index for RAG
        print(f"[Graph] Indexing invoice: {invoice_id}")
        add_invoice_to_vector_store(
            report_data=report_data,
            file_metadata=file_metadata
        )
        
        log_event(invoice_id, "routing", "completed", "Auto-processed (PASSED)")
        log_event(invoice_id, "indexing", "completed", "Indexed into vector store")
        return {
            "report_paths": {"json": str(report_path_json), "html": str(report_path_html)},
            "is_indexed": True,
            "error": None
        }
        
    except Exception as e:
        log_event(invoice_id, "save_and_index", "error", str(e))
        return {"error": str(e)}

def save_and_fail_node(state: InvoiceState) -> Dict[str, Any]:
    """Failure path: Save JSON and HTML to review directory"""
    print("--- [Graph] Node: Save & Fail (Review) ---")
    filepath = state['filepath']
    invoice_id = Path(filepath).stem
    try:
        filepath = state['filepath']
        invoice_id = Path(filepath).stem
        report_data = state['report_data']
        
        target_dir = _move_invoice_files(filepath, REVIEW_DIR)
        
        report_path_json = target_dir / f"{invoice_id}_report.json"
        with open(report_path_json, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"[Graph] JSON Report saved: {report_path_json}")

        report_path_html = target_dir / f"{invoice_id}_report.html"
        html_content = generate_html_report(report_data)
        with open(report_path_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[Graph] HTML Report saved: {report_path_html}")
        
        log_event(invoice_id, "routing", "completed", "Sent to human review")
        return {
            "report_paths": {"json": str(report_path_json), "html": str(report_path_html)},
            "is_indexed": False,
            "error": None
        }
        
    except Exception as e:
        log_event(invoice_id, "save_and_fail", "error", str(e))
        return {"error": str(e)}

# DEFINE THE ROUTER
def router_check_validation(state: InvoiceState) -> str:
    """Route based on validation status"""
    print("--- [Graph] Router: Checking status ---")
    
    if state.get("error"):
        print(f"[Graph] Error detected: {state['error'][:50]}... → routing to review")
        return "fail_path"
    
    status = state.get("validation_status", "FAILED")
    if status == "PASSED":
        print("[Graph] Status: PASSED → routing to success")
        return "success_path"
    else:
        print(f"[Graph] Status: {status} → routing to review")
        return "fail_path"

# 4. BUILD THE GRAPH

def build_workflow():
    """Builds and compiles the LangGraph workflow"""
    print("[WorkflowBuilder] Building graph...")
    
    workflow = StateGraph(InvoiceState)
    
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("translation", translation_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("generate_report", generate_report_node)
    workflow.add_node("save_and_index", save_and_index_node)
    workflow.add_node("save_and_fail", save_and_fail_node)
    
    workflow.set_entry_point("extraction")
    workflow.add_edge("extraction", "translation")
    workflow.add_edge("translation", "validate")
    workflow.add_edge("validate", "generate_report")
    
    workflow.add_conditional_edges(
        "generate_report",
        router_check_validation,
        {
            "success_path": "save_and_index",
            "fail_path": "save_and_fail"
        }
    )
    
    workflow.add_edge("save_and_index", END)
    workflow.add_edge("save_and_fail", END)
    
    app = workflow.compile()
    print("[WorkflowBuilder] ✅ Graph compiled successfully")
    return app

try:
    graph_app = build_workflow()
    
    try:
        diagram_path = os.path.join(project_root, "workflow_diagram.png")
        graph_app.get_graph().draw_mermaid_png(output_file_path=diagram_path)
        print(f"[WorkflowBuilder] Diagram saved: {diagram_path}")
    except Exception as e:
        print(f"[WorkflowBuilder] Could not generate diagram: {e}")

except Exception as e:
    print(f"FATAL: Could not build workflow: {e}")
    graph_app = None

if __name__ == "__main__":
    if graph_app:
        print("\n✅ Workflow ready. Import 'graph_app' from this module to run.")
    else:
        print("\n❌ Workflow build FAILED.")