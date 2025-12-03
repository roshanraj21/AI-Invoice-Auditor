from pydantic import BaseModel, Field
from typing import List, Optional

class Vendor(BaseModel):
    """pydantic model for vendors.json"""
    vendor_id: str
    vendor_name: str
    country: str
    currency: str

class PurchaseOrderLineItem(BaseModel):
    """Pydantic model for a line item within a PO"""
    item_code: str
    description: str
    qty: int
    unit_price: float
    currency: str

class PurchaseOrder(BaseModel):
    """Pydantic model for PO_records.json"""
    po_number: str
    vendor_id: str
    line_items: List[PurchaseOrderLineItem]

class Sku(BaseModel):
    """Pydantic model for sku_master.json"""
    item_code: str
    category: str
    uom: str
    gst_rate: int