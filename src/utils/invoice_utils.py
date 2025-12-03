import json
import os
import sys
from pathlib import Path
import streamlit as st

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from config import settings

def get_directory_structure():
    return {
        "auto_processed": settings.PROCESSED_DIR,
        "pending_review": settings.REVIEW_DIR,
        "approved": settings.APPROVED_DIR,
        "rejected": settings.REJECTED_DIR
    }

def get_invoice_count_in_subdirs(directory: Path):
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return 0
    return len([d for d in directory.iterdir() if d.is_dir()])

def get_pending_invoices():
    dirs = get_directory_structure()
    pending_dir = dirs["pending_review"]

    if not pending_dir.exists():
        return []

    pending_invoices = []
    
    for invoice_dir in pending_dir.iterdir():
        if not invoice_dir.is_dir():
            continue

        invoice_id = invoice_dir.name

        pdf_file = None
        meta_file = invoice_dir / f"{invoice_id}.meta.json"
        report_file = invoice_dir / f"{invoice_id}_report.json"
        report_html_file = invoice_dir / f"{invoice_id}_report.html"

        for ext in ['.pdf', '.png', '.jpg', '.jpeg']:
            candidate = invoice_dir / f"{invoice_id}{ext}"
            if candidate.exists():
                pdf_file = candidate
                break

        invoice_data = {
            "invoice_id": invoice_id,
            "invoice_dir": invoice_dir,
            "pdf_file": pdf_file,
            "meta_file": meta_file if meta_file.exists() else None,
            "report_file": report_file if report_file.exists() else None,
            "report_html_file": report_html_file if report_html_file.exists() else None,
            "vendor": "Unknown",
            "amount": "N/A",
            "date": "Unknown",
            "status": "Pending Review",
            "issues": []
        }

        if meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    invoice_data["metadata"] = json.load(f)
            except:
                pass

        if report_file.exists():
            try:
                with open(report_file, "r") as f:
                    report = json.load(f)
                    invoice_data["report"] = report

                    inv_data = report.get("invoice_data", {})
                    invoice_data["vendor"] = inv_data.get("vendor_name", "Unknown")
                    invoice_data["amount"] = inv_data.get("total_amount", "N/A")
                    invoice_data["date"] = inv_data.get("invoice_date", "Unknown")
                    invoice_data["status"] = report.get("validation_status", "Pending Review")

                    rules = report.get("validation_rules", [])
                    failed = [r.get("message") for r in rules if r.get("status") == "FAILED"]
                    invoice_data["issues"] = failed
            except:
                pass

        pending_invoices.append(invoice_data)

    return pending_invoices
