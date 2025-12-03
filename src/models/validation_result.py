from pydantic import BaseModel, Field
from typing import List, Dict
from .invoice import InvoiceData
 
class ValidationRule(BaseModel):
    """
    Not a Pydantic model, but describes one check in the validation process.
    """
    rule_name: str = Field(..., description="Name of the rule that was checked")
    status: str = Field(..., description="Result of the check (PASSED or FAILED)")
    message: str = Field(..., description="Details about the check result")
 
class ValidationResult(BaseModel):
    """
    This model represents the final audit report for a single invoice.
    It combines the original data with the results of all validation checks.
    """
    invoice_data: InvoiceData = Field(..., description="The full, extracted invoice data")
    overall_status: str = Field("FAILED", description="Overall result of the audit (PASSED or FAILED)")
    total_checks: int = Field(..., description="Total number of rules applied")
    failed_checks: int = Field(..., description="Number of rules that failed")
    rules_results: List[ValidationRule] = Field(..., description="A list of results for each individual rule")
    
    recommendation: str = Field(..., description="The final recommendation (e.g., 'Approve for Payment', 'Route to human for review')")
 
    class Config:
        """Pydantic model configuration."""
        from_attributes= True
        json_schema_extra = {
            "example": {
                "invoice_data": {
                    "invoice_id": "INV-2025-001",
                    "vendor_name": "Fake Vendor Inc.", # This name is not in the ERP
                    "total_amount": 2100.00,
                    # ... other invoice fields ...
                    "original_filename": "invoice_456.png",
                    "processing_status": "Validated"
                },
                "overall_status": "FAILED",
                "total_checks": 3,
                "failed_checks": 1,
                "rules_results": [
                    {"rule_name": "Check for mandatory fields", "status": "PASSED", "message": "All mandatory fields are present."},
                    {"rule_name": "Check line item totals", "status": "PASSED", "message": "Line items sum (2000.00) + Tax (100.00) matches total (2100.00)."},
                    {"rule_name": "ERP Vendor Check", "status": "FAILED", "message": "Vendor 'Fake Vendor Inc.' is not an approved vendor in the ERP."}
                ],
                "recommendation": "Route to human for review. Reason: Unapproved vendor."
            }
        }
 