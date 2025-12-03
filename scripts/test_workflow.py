import os
import sys
import shutil # This module is no longer needed, but we'll leave it for now
from pprint import pprint

# --- Add project root to path ---
# (This assumes the test script is in 'project_root/tests/')
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

try:
    from src.graph.workflow import graph_app
    from config.settings import INCOMING_DIR, PROCESSED_DIR, REVIEW_DIR
except ImportError as e:
    print(f"Error: Could not import modules in test_workflow.py: {e}")
    sys.exit(1)

# Use an invoice to test the full pipeline!
# e.g., "INV_ES_001.pdf"
# This file must exist in your 'data/incoming/' folder.
TEST_INVOICE_FILENAME = "INV_ES_003.pdf" 
# --- !!! ---
def run_workflow_test():
    """
    Runs a full, end-to-end test of the compiled LangGraph workflow.
    This test assumes the invoice file is ALREADY in the INCOMING_DIR.
    """
    print("--- [Test Workflow] Starting Full Workflow Test ---")
    
    # 1. Define the test file path
    # The file MUST ALREADY be in the INCOMING_DIR for this test.
    file_to_test_path = os.path.join(INCOMING_DIR, TEST_INVOICE_FILENAME)
    
    print(f"[Test Workflow] Looking for test file at: {file_to_test_path}")
    
    # Check if the file and its metadata file exist before running
    if not os.path.exists(file_to_test_path):
         print(f"FATAL: Test file not found at {file_to_test_path}")
         print(f"Please make sure '{TEST_INVOICE_FILENAME}' is in your 'data/incoming/' folder.")
         return

    # Check for the .meta.json file
    meta_path = os.path.splitext(file_to_test_path)[0] + ".meta.json"
    if not os.path.exists(meta_path):
        print(f"[Test Workflow] Warning: Metadata file not found at {meta_path}")
        print("Continuing, but translation node might not find a language hint.")
    else:
        print(f"[Test Workflow] Found test file and its .meta.json file.")

    # 2. Run the graph
    print("[Test Workflow] Invoking graph_app...")
    
    # This is the input state for the graph
    inputs = {"filepath": file_to_test_path}
 
    try:
        # Run the graph and get the final state
        # We use .invoke() which runs the full graph from start to finish
        final_state = graph_app.invoke(inputs)
        
        print("\n--- [Test Workflow] GRAPH EXECUTION COMPLETE ---")
        
        # 3. Print the results
        print("\n--- FINAL STATE ---")
        # Use pprint for a clean print of the dictionary
        pprint(final_state)
        
        # 4. Check results
        print("\n--- TEST SUMMARY ---")
        if final_state.get("error"):
            print(f"RESULT: FAILED (Graph Error)")
            print(f"Error: {final_state['error']}")
            
        elif final_state.get("validation_status") == "PASSED":
            print(f"RESULT: SUCCESS (Validation Passed)")
            # The file should no longer be in INCOMING_DIR
            print(f"File processed and moved from INCOMING_DIR.")
            print(f"Destination: {PROCESSED_DIR}")
            print(f"Report JSON: {final_state.get('report_paths', {}).get('json')}")
            print(f"Indexed for RAG: {final_state.get('is_indexed')}")
            
        elif final_state.get("validation_status") == "FAILED":
            print(f"RESULT: SUCCESS (Validation Failed)")
            # The file should no longer be in INCOMING_DIR
            print(f"File correctly failed validation and moved from INCOMING_DIR.")
            print(f"Destination: {REVIEW_DIR}")
            print("Errors found:")
            pprint([r for r in final_state.get('rules_results', []) if r['status'] == 'FAILED'])
            
        else:
            print("RESULT: UNKNOWN")
            print("Graph finished but state is inconclusive.")
            
    except Exception as e:
        print(f"\n--- [Test Workflow] CRITICAL ERROR during graph.invoke(): {e} ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # --- IMPORTANT ---
    # Make sure your Mock ERP is running in another terminal!
    # $ python scripts/start_erp.py
    #
    # Make sure your credentials (AWS, etc.) are set in this terminal!
    #
    run_workflow_test()

