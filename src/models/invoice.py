from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import date
 
class LineItem(BaseModel):
    """
    Defines the data structure for a single line item in an invoice.
    """
    item_id: Optional[str] = Field(..., description="Stock Keeping Unit (SKU) or item code")
    description: Optional[str] = Field(None, description="Description of the item or service")
    quantity: float = Field(..., description="Quantity of the item")
    unit_price: float = Field(..., description="Price per unit of the item")
    line_total: float = Field(..., description="Total price for this line (quantity * unit_price)")
 
class InvoiceData(BaseModel):
    """
    This is the main Pydantic model (data contract) for a fully extracted and
    translated invoice. This is the central data structure for the entire workflow.
    """
    # --- Header Fields ---
    invoice_id: Optional[str] = Field(None, description="The unique invoice number")
    vendor_name: str = Field(..., description="Name of the company sending the invoice")
    customer_name: Optional[str] = Field(None, description="Name of the company receiving the invoice")
    invoice_date: Optional[date] = Field(None, description="Date the invoice was issued")
    due_date: Optional[date] = Field(None, description="Date the payment is due")
 
    # --- Financials ---
    subtotal: Optional[float] = Field(None, description="The total amount before taxes and discounts")
    tax_amount: Optional[float] = Field(None, description="Total amount of tax (e.g., VAT, GST)")
    discount_amount: Optional[float] = Field(None, description="Any discounts applied")
    total_amount: float = Field(..., description="The final amount due")
    currency: Optional[str] = Field("USD", description="Currency code (e.g., USD, EUR)")
 
    # --- References ---
    po_number: Optional[str] = Field(None, description="Purchase Order number associated with the invoice")
 
    # --- Line Items ---
    line_items: List[LineItem] = Field(..., description="List of all items or services being billed")
 
    # --- Metadata (Added by our process) ---
    original_filename: str = Field(..., description="The name of the source file (e.g., 'invoice_123.pdf')")
    processing_status: str = Field("Pending", description="Current status (e.g., Pending, Extracted, Validated, Failed)")
 
    class Config:
        """Pydantic model configuration."""
        # This allows the model to be created from non-dict objects
        # and provides an example for LLMs and documentation.
        from_attributes = True
        json_schema_extra = {
            "example": {
                "invoice_id": "INV-2025-001",
                "vendor_name": "Tech Solutions Ltd.",
                "customer_name": "Global Corp Inc.",
                "invoice_date": "2025-11-01",
                "due_date": "2025-12-01",
                "subtotal": 2000.00,
                "tax_amount": 100.00,
                "discount_amount": 0.00,
                "total_amount": 2100.00,
                "currency": "USD",
                "po_number": "PO-98765",
                "line_items": [
                    {
                        "item_id": "SKU-A123",
                        "description": "Enterprise Software License - 1 Year",
                        "quantity": 1,
                        "unit_price": 2000.00,
                        "line_total": 2000.00
                    }
                ],
                "original_filename": "invoice_123.pdf",
                "processing_status": "Extracted"
            }
        }