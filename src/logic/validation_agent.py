import os
import sys
import yaml
import requests
import json
from typing import Dict, Any, List
from decimal import Decimal, InvalidOperation

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from config.settings import RULES_PATH, ERP_URL
    import litellm
except ImportError as e:
    print(f"Error importing modules in validation_agent.py: {e}")
    sys.exit(1)

# LOAD YAML RULES

def _load_rules() -> Dict[str, Any]:
    try:
        with open(RULES_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[ValidationAgent] CRITICAL: Could not load rules.yaml: {e}")
        return {}

RULES = _load_rules()

def _create_rule_result(rule_name: str, status: str, message: str, source="Internal") -> Dict[str, str]:
    return {"rule_name": rule_name, "status": status, "message": message, "source": source}

# INTERNAL VALIDATION (Stage 1)

def _check_internal_rules(data: Dict[str, Any]) -> List[Dict[str, str]]:
    print("[ValidationAgent] Running Stage 1: Internal Checks...")
    results = []

    # --- 1. Required Header Fields ---
    rule_name = "Required Header Fields"
    header_rules = RULES.get("required_fields", {}).get("header", [])
    missing_fields = [field for field in header_rules if not data.get(field)]
    
    if missing_fields:
        results.append(_create_rule_result(
            rule_name, "FAILED", f"Missing required header fields: {', '.join(missing_fields)}", "Internal"
        ))

    else:
        results.append(_create_rule_result(rule_name, "PASSED", "All required header fields are present.","Internal"))

    # --- 2. Required Line Item Fields ---
    rule_name = "Required Line Item Fields"
    if "line_items" not in data or not data["line_items"]:
        results.append(_create_rule_result(rule_name, "FAILED", "Invoice has no line items.","Internal"))
    else:
        missing_item_fields = False
        for item in data["line_items"]:
            for field in RULES.get("required_fields", {}).get("line_item", []):
                if not item.get(field):
                    missing_item_fields = True
                    break

        if missing_item_fields:
            results.append(_create_rule_result(
                rule_name, "FAILED",
                "One or more line items are missing required fields.",
                "Internal"
            ))
        else:
            results.append(_create_rule_result(
                rule_name, "PASSED", "All line items have required fields.","Internal"
            ))

    # --- 3. Currency Check ---
    rule_name = "Currency Check"
    currency = data.get("currency")
    accepted = RULES.get("accepted_currencies", [])
    if currency not in accepted:
        results.append(_create_rule_result(rule_name, "FAILED", f"Invalid or unaccepted currency: {currency}","Internal"))
    else:
        results.append(_create_rule_result(rule_name, "PASSED", f"Currency '{currency}' is valid.","Internal"))

    # --- 4. Financial Checks ---
    try:
        line_sum = sum(Decimal(str(item.get("line_total", 0))) for item in data.get("line_items", []))
        subtotal = Decimal(str(data.get("subtotal", 0)))
        tax = Decimal(str(data.get("tax_amount", 0)))
        total = Decimal(str(data.get("total_amount", 0)))
        delta = Decimal(str(RULES.get("tolerances", {}).get("financial_rounding_delta", 0.02)))

        # Subtotal
        if abs(line_sum - subtotal) > delta:
            results.append(_create_rule_result(
                "Subtotal Check", "FAILED",
                f"Subtotal mismatch. Line sum = {line_sum}, but subtotal = {subtotal}",
                "Internal"
            ))
        else:
            results.append(_create_rule_result("Subtotal Check", "PASSED", "Subtotal matches.","Internal"))

        # Total
        if abs((subtotal + tax) - total) > delta:
            results.append(_create_rule_result(
                "Total Check", "FAILED",
                f"Total mismatch. Subtotal+Tax = {subtotal + tax}, but total = {total}","Internal"
            ))
        else:
            results.append(_create_rule_result("Total Check", "PASSED", "Total is correct.","Internal"))

    except (InvalidOperation, TypeError):
        results.append(_create_rule_result(
            "Financial Calculation", "FAILED",
            "Non-numeric values in subtotal/tax/total.","Internal"
        ))

    return results

# ERP VALIDATION (Stage 2)
def _check_erp_rules(data: Dict[str, Any]) -> List[Dict[str, str]]:
    print("[ValidationAgent] Running Stage 2: ERP Checks...")
    results = []
    po_number = data.get("po_number")
    vendor_name = data.get("vendor_name")
    invoice_currency = data.get("currency")
    vendor_id = None
    erp_po = None

    try:
        # --- Vendor Check ---
        rule_name = "ERP Vendor Check"
        if not vendor_name:
            results.append(_create_rule_result(rule_name, "FAILED", "Vendor missing.","ERP"))
            return results
            
        response = requests.get(f"{ERP_URL}/vendor/by_name/{vendor_name}", timeout=5)
        if response.status_code == 404:
            results.append(_create_rule_result(rule_name, "FAILED", f"Vendor '{vendor_name}' not in ERP.","ERP"))
            return results
        response.raise_for_status()
        erp_vendor = response.json()
        vendor_id = erp_vendor.get("vendor_id")

        results.append(_create_rule_result(rule_name, "PASSED", f"Vendor '{vendor_name}' exists. ID={vendor_id}","ERP"))

        # --- Currency Check ---
        rule_name = "Vendor Currency Check"
        if erp_vendor.get("currency") != invoice_currency:
            results.append(_create_rule_result(
                rule_name, "FAILED",
                f"Invoice currency {invoice_currency} does not match vendor currency {erp_vendor.get('currency')}","ERP"
            ))
        else:
            results.append(_create_rule_result(rule_name, "PASSED", "Currency matches vendor.","ERP"))

        # --- PO Check ---
        rule_name = "ERP PO Check"
        if not po_number:
            results.append(_create_rule_result(rule_name, "SKIPPED", "No PO, skipping PO checks.","ERP"))
        else:
            po_resp = requests.get(f"{ERP_URL}/po/{po_number}", timeout=5)
            if po_resp.status_code == 404:
                results.append(_create_rule_result(rule_name, "FAILED", f"PO '{po_number}' not found.","ERP"))
            else:
                po_resp.raise_for_status()
                erp_po = po_resp.json()
                results.append(_create_rule_result(rule_name, "PASSED", f"PO '{po_number}' is valid.","ERP"))

                # Vendor matches PO
                rule_name = "PO-Vendor Match"
                if erp_po.get("vendor_id") != vendor_id:
                    results.append(_create_rule_result(
                        rule_name, "FAILED",
                        f"PO vendor {erp_po.get('vendor_id')} does not match invoice vendor {vendor_id}","ERP"
                    ))
                else:
                    results.append(_create_rule_result(rule_name, "PASSED", "PO vendor matches.","ERP"))

        # --- Line Item SKU Checks ---
        po_map = {item["item_code"]: item for item in erp_po.get("line_items", [])} if erp_po else {}

        for i, item in enumerate(data.get("line_items", [])):
            # Map item_id from invoice data to item_code in ERP records
            item_code = item.get("item_id")  # Invoice field
            desc = item.get("description", f"Item {i+1}")
            prefix = f"Line Item {i+1} '{desc}'"

            if not item_code:
                results.append(_create_rule_result(f"{prefix} SKU Check", "FAILED", "Missing SKU.","ERP"))
                continue

            sku_resp = requests.get(f"{ERP_URL}/sku/{item_code}", timeout=5)
            if sku_resp.status_code == 404:
                results.append(_create_rule_result(
                    f"{prefix} SKU Check", "FAILED", f"SKU '{item_code}' not found in ERP","ERP"
                ))
                continue
            sku_resp.raise_for_status()
            results.append(_create_rule_result(f"{prefix} SKU Check", "PASSED", f"SKU '{item_code}' exists.","ERP"))

            if po_number and erp_po:
                if item_code not in po_map:
                    results.append(_create_rule_result(
                        f"{prefix} PO Check", "FAILED", "Item not in PO.","ERP"
                    ))
                    continue
                results.append(_create_rule_result(f"{prefix} PO Check", "PASSED", "Item matches PO.","ERP"))

    except Exception as e:
        results.append(_create_rule_result("ERP Validation", "FAILED", f"Error during ERP validation: {e}","ERP"))

    return results

# AI VALIDATION (Stage 3)

def _check_ai_validation(data: Dict[str, Any]) -> List[Dict[str, str]]:
    print("[ValidationAgent] Running Stage 3: AI Checks...")

    prompt = f"""
    You are an invoice validation checker.
    Return ONLY a JSON list of rule results.

    Rules you must check:
    1. Vendor name looks suspicious or misspelled.
    2. Currency seems unusual for this vendor.
    3. Total amount extremely high (> 1,000,000).

    Respond ONLY with JSON:
    [
      {{"rule_name": "...", "status": "PASSED or FAILED", "message": "..."}}
    ]

    If no issues, return [].

    Invoice:
    {json.dumps(data)}
    """

    try:
        resp = litellm.completion(
            model="bedrock/amazon.nova-lite-v1:0",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No markdown."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0
        )

        content = resp.choices[0].message["content"].strip()

        # Remove fenced markdown if present
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].replace("json", "").strip()

        # Parse JSON
        try:
            parsed = json.loads(content)
        except:
            print("[AI Validation] Output not JSON, skipping AI rules.")
            return []

        # Handle single dict case
        if isinstance(parsed, dict):
            parsed = [parsed]

        cleaned = []
        for r in parsed:
            rule_name = r.get("rule_name", "AI Check")
            raw_status = str(r.get("status", "PASSED")).strip().lower()

            status = "FAILED" if raw_status in ["fail", "failed", "error"] else "PASSED"
            message = r.get("message", "")

            cleaned.append({
                "rule_name": rule_name,
                "status": status,
                "message": message,
                "source": "AI"
            })

        print("[AI Validation] Final cleaned rules:", cleaned)
        return cleaned

    except Exception as e:
        print(f"[ValidationAgent] AI validation skipped due to error: {e}")
        return []

# MAIN VALIDATION ENTRY POINT
def validate_invoice_data(invoice_data: Dict[str, Any]) -> List[Dict[str, str]]:
    print(f"\n[ValidationAgent] Starting validation for: {invoice_data.get('original_filename')}")

    internal_results = _check_internal_rules(invoice_data)
    erp_results = _check_erp_rules(invoice_data)
    ai_results = _check_ai_validation(invoice_data)

    all_results = internal_results + erp_results + ai_results

    failed = [r for r in all_results if r["status"] == "FAILED"]
    if not failed:
        print(f"[ValidationAgent] Validation PASSED.")
    else:
        print(f"[ValidationAgent] Validation FAILED with {len(failed)} errors.")

    return all_results
