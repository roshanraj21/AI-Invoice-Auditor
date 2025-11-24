import sys
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor
from typing import Set
from pathlib import Path
import hashlib

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from config.settings import INCOMING_DIR
    from src.graph.workflow import graph_app 
    from src.utils.pipeline_logger import log_event

except ImportError as e:
    print(f"Error: Could not import settings or graph_app: {e}")
    print("Please ensure your src/workflow.py file exists and paths are correct.")
    print(f"Project root (added): {project_root}")
    sys.exit(1)

VALID_EXTENSIONS = ('.pdf', '.docx', '.png', '.jpg', '.jpeg')
HASH_FILE = Path("processed_hashes.txt")
HASH_FILE.touch(exist_ok=True)
from pathlib import Path

def _normalize_incoming_dir(p) -> Path:
    # Ensure absolute, resolved Path for watchdog + logs
    return Path(p).expanduser().resolve()

def compute_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def has_been_processed(file_hash):
    with HASH_FILE.open("r") as f:
        return file_hash in set(line.strip() for line in f)

def mark_as_processed(file_hash):
    with HASH_FILE.open("a") as f:
        f.write(file_hash + "\n")

def process_invoice_workflow(filepath: str):
    """
    This is the "worker" function that runs in a separate thread.
    It invokes the full LangGraph workflow for a single invoice.
    """
    try:
        filename = os.path.basename(filepath)
        file_hash = compute_file_hash(filepath)
        if has_been_processed(file_hash):
            print(f"[Monitor] ⏩ Duplicate invoice skipped: {filename}")
            try:
                log_event(Path(filename).stem, "duplicate_check", "skipped", f"Duplicate detected, skipping")
            except:
                pass
            return
        print(f"--- [Worker] Starting workflow for: {filename} ---")
        log_event(Path(filename).stem, "detect", "started", f"Invoice received: {filename}")
        input_data = {"filepath": filepath}
        final_state = graph_app.invoke(input_data)
        

        if final_state.get("error"):
            print(f"--- [Worker] Workflow FAILED for: {filename} ---")
            log_event(Path(filename).stem, "workflow_error", "error", str(final_state.get("error")))
            print(f"  Error: {final_state['error']}")
        else:
            print(f"--- [Worker] Workflow SUCCESS for: {filename} ---")
            log_event(Path(filename).stem, "workflow_complete", "completed", "Workflow completed successfully")
            print(f"  Final Status: {final_state.get('validation_status')}")
            print(f"  Report saved to: {final_state.get('report_paths', {}).get('json')}")
            print(f"  Indexed for RAG: {final_state.get('is_indexed')}")
            mark_as_processed(file_hash)

    except Exception as e:
        print(f"[Worker] CRITICAL Error processing {filepath}: {e}")

class InvoiceHandler(FileSystemEventHandler):
    """
    Handles file system events and dispatches work to a thread pool.
    """
    def __init__(self, executor: ThreadPoolExecutor):
        self.executor = executor
        self.processing: Set[str] = set() # Track files being processed

    def on_created(self, event):
        """
        Called when a file or directory is created.
        """
        if event.is_directory:
            return

        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        if not filename.lower().endswith(VALID_EXTENSIONS):
            return
            
        # 2. Check if we're already processing this file
        if filepath in self.processing:
            print(f"[Monitor] Ignoring duplicate event for: {filename}")
            return
       
        time.sleep(1) 
        
        print("\n" + "="*50)
        print(f"[Monitor] New invoice file detected: {filename}")
        
        # Add to processing set and submit to thread pool
        self.processing.add(filepath)
        self.executor.submit(self.process_and_cleanup, filepath)

    def process_and_cleanup(self, filepath: str):
        """
        Wrapper to run the workflow and remove the file from the processing set.
        """
        process_invoice_workflow(filepath)
        if filepath in self.processing:
            self.processing.remove(filepath)

def start_monitoring():
    """
    Starts the watchdog file monitor with a thread pool.
    """
    incoming_path = _normalize_incoming_dir(INCOMING_DIR)

    if not incoming_path.exists():
        print(f"Error: Incoming directory not found: {incoming_path}")
        # Create it to avoid silent mismatch
        incoming_path.mkdir(parents=True, exist_ok=True)
        print(f"[Monitor] Created missing incoming directory: {incoming_path}")

    # Create a thread pool that can run up to 5 invoices at the same time
    max_concurrent_invoices = 5
    with ThreadPoolExecutor(max_workers=max_concurrent_invoices) as executor:
        event_handler = InvoiceHandler(executor)
        observer = Observer()

        # IMPORTANT: pass a *string* absolute path to watchdog
        observer.schedule(event_handler, str(incoming_path), recursive=False)

        print("="*50)
        print("🚀 AI Invoice Auditor - Monitoring Agent STARTED")
        print(f"👀 Watching for new invoices in: {incoming_path}")
        print(f"⚙️  Max concurrent processing: {max_concurrent_invoices}")
        print("Press CTRL+C to stop.")
        print("="*50)

        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n[Monitor] Stopping monitor...")

        observer.join()
        print("[Monitor] Waiting for all processing to complete...")

    print("[Monitor] Monitor shut down gracefully.")


if __name__ == "__main__":
    start_monitoring()