import uvicorn
import sys
import os
 
# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------
 
try:
    from config.settings import ERP_HOST, ERP_PORT
except ImportError:
    print("Error: Could not import settings from config.settings")
    print(f"Current sys.path: {sys.path}")
    print(f"Project root (added): {project_root}")
    sys.exit(1)
 
 
if __name__ == "__main__":
    print(f"Starting Mock ERP Server at http://{ERP_HOST}:{ERP_PORT}")
    print("See API docs at http://{ERP_HOST}:{ERP_PORT}/docs")
 
    # We point uvicorn to the 'app' instance inside the 'src.erp.app' module
    uvicorn.run(
        "src.erp.app:app",
        host=ERP_HOST,
        port=ERP_PORT,
        reload=True,  # reload=True is great for development
        log_level="info"
    )