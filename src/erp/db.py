import json
from pydantic import ValidationError, BaseModel
from typing import List, Dict, Optional
import sys
import os
 
# --- Add project root to path ---
# the absolute path of the 'ai-invoice-auditor' directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------
 
try:
    from config.settings import VENDORS_FILE, PO_RECORDS_FILE, SKU_MASTER_FILE
    from src.erp.models import Vendor, PurchaseOrder, Sku
except ImportError:
    print("Error: Could not import from config or src.erp.models.")
    print(f"Current sys.path: {sys.path}")
    print(f"Project root (added): {project_root}")
    sys.exit(1)
 
class MockERPDatabase:
    """
    Handles loading and querying the mock ERP data from JSON files.
    This class is instantiated once by the FastAPI app on startup.
    """
    def __init__(self):
        print("Initializing Mock ERP Database...")
        self.vendors: Dict[str, Vendor] = self._load_data(VENDORS_FILE, Vendor, "vendor_id")
        self.purchase_orders: Dict[str, PurchaseOrder] = self._load_data(PO_RECORDS_FILE, PurchaseOrder, "po_number")
        self.skus: Dict[str, Sku] = self._load_data(SKU_MASTER_FILE, Sku, "item_code")
        print("Mock ERP Database loaded successfully.")
        print(f"Loaded {len(self.vendors)} vendors.")
        print(f"Loaded {len(self.purchase_orders)} purchase orders.")
        print(f"Loaded {len(self.skus)} SKUs.")
 
    def _load_data(self, file_path: str, model: type, key_field: str) -> Dict[str, BaseModel]:
        """
        Generic function to load a JSON file into a dict of Pydantic models.
        """
        data_dict = {}
        try:
            with open(file_path, 'r') as f:
                data_list = json.load(f)
 
                if not isinstance(data_list, list):
                    print(f"Error: {file_path} does not contain a JSON list.")
                    return {}
 
                for index, item in enumerate(data_list):
                    try:
                        # Use the Pydantic model to parse and validate the item
                        model_instance = model(**item)
                        key = getattr(model_instance, key_field)
                        data_dict[key] = model_instance
                    except ValidationError as e:
                        print(f"Warning: Skipping item {index} in {file_path} due to validation error: {e}")
        except FileNotFoundError:
            print(f"Error: {file_path} not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: {file_path} contains invalid JSON.")
            sys.exit(1)
        return data_dict
 
    # --- Public API for querying data ---
 
    def get_vendor_by_id(self, vendor_id: str) -> Optional[Vendor]:
        return self.vendors.get(vendor_id)
 
    def get_vendor_by_name(self, name: str) -> Optional[Vendor]:
        """
        Search for a vendor by name (case-insensitive).
        """
        search_name = name.strip().lower()
        
        # Iterate over the VALUES (vendor objects), not keys
        for vendor in self.vendors.values():
            if vendor.vendor_name.strip().lower() == search_name:
                return vendor
        return None
 
    def get_po_by_number(self, po_number: str) -> Optional[PurchaseOrder]:
        return self.purchase_orders.get(po_number)
 
    def get_sku_by_code(self, item_code: str) -> Optional[Sku]:
        return self.skus.get(item_code)
 
# Single instance to be shared by the FastAPI app
try:
    db = MockERPDatabase()
except Exception as e:
    print(f"Failed to initialize database: {e}")
    db = None