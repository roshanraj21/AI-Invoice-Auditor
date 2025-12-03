from fastapi import FastAPI, HTTPException
from typing import Optional
import sys
import os
 
# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------
 
try:
    from src.erp.models import Vendor, PurchaseOrder, Sku
    from src.erp.db import db # Import the pre-initialized db instance
except ImportError:
    print("Error: Could not import from src.erp.models or src.erp.db.")
    print(f"Current sys.path: {sys.path}")
    print(f"Project root (added): {project_root}")
    sys.exit(1)
 
 
app = FastAPI(
    title="AI Invoice Auditor - Mock ERP API",
    description="Simulates a real ERP system by providing data from JSON files."
)
 
if db is None:
    print("FATAL: Database could not be loaded. Exiting.")
    sys.exit(1)
 
# --- API Endpoints ---
 
@app.get("/", summary="API Root")
async def read_root():
    """Welcome endpoint."""
    return {"message": "Mock ERP API is running. See /docs for endpoints."}
 
@app.get("/vendor/by_name/{vendor_name}", response_model=Vendor, summary="Get Vendor by Name")
async def get_vendor_by_name(vendor_name: str):
    """
    Searches for a vendor by their name (case-insensitive).
    This is what our agent will call to validate a vendor.
    """
    vendor = db.get_vendor_by_name(vendor_name)
    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_name}' not found.")
    return vendor
 
@app.get("/vendor/by_id/{vendor_id}", response_model=Vendor, summary="Get Vendor by ID")
async def get_vendor_by_id(vendor_id: str):
    """Searches for a vendor by their unique ID."""
    vendor = db.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor ID '{vendor_id}' not found.")
    return vendor
 
@app.get("/po/{po_number}", response_model=PurchaseOrder, summary="Get Purchase Order by Number")
async def get_po_by_number(po_number: str):
    """Retrieves a single Purchase Order by its PO number."""
    po = db.get_po_by_number(po_number)
    if not po:
        raise HTTPException(status_code=404, detail=f"PO Number '{po_number}' not found.")
    return po
 
@app.get("/sku/{item_code}", response_model=Sku, summary="Get SKU by Item Code")
async def get_sku_by_code(item_code: str):
    """Retrieves a single SKU (item) by its item code."""
    sku = db.get_sku_by_code(item_code)
    if not sku:
        raise HTTPException(status_code=404, detail=f"Item Code '{item_code}' not found.")
    return sku
 