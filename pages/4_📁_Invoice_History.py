import streamlit as st
import json
import os
import sys
from pathlib import Path
import streamlit.components.v1 as components

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import settings
from src.utils.pdf_utils import display_pdf

st.set_page_config(page_title="Invoice History", page_icon="📁", layout="wide")

def get_invoices_from_folder(folder_path, status_name):
    """Get all invoices from a specific folder"""
    invoices = []
    
    if not folder_path.exists():
        return invoices
    
    for invoice_dir in folder_path.iterdir():
        if not invoice_dir.is_dir():
            continue
        
        invoice_id = invoice_dir.name
        
        # Find invoice file
        invoice_file = None
        for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.docx']:
            candidate = invoice_dir / f"{invoice_id}{ext}"
            if candidate.exists():
                invoice_file = candidate
                break
        
        meta_file = invoice_dir / f"{invoice_id}.meta.json"
        report_file = invoice_dir / f"{invoice_id}_report.json"
        report_html_file = invoice_dir / f"{invoice_id}_report.html"
        
        invoice_data = {
            "invoice_id": invoice_id,
            "invoice_dir": invoice_dir,
            "invoice_file": invoice_file,
            "meta_file": meta_file if meta_file.exists() else None,
            "report_file": report_file if report_file.exists() else None,
            "report_html_file": report_html_file if report_html_file.exists() else None,
            "status": status_name,
            "vendor": "Unknown",
            "amount": "N/A",
            "date": "Unknown"
        }
        
        # Load report data
        if report_file.exists():
            try:
                with open(report_file, "r") as f:
                    report = json.load(f)
                    invoice_data["report"] = report
                    
                    inv_data = report.get("invoice_data", {})
                    invoice_data["vendor"] = inv_data.get("vendor_name", "Unknown")
                    invoice_data["amount"] = inv_data.get("total_amount", "N/A")
                    invoice_data["date"] = inv_data.get("invoice_date", "Unknown")
            except:
                pass
        
        # Load metadata
        if meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    invoice_data["metadata"] = json.load(f)
            except:
                pass
        
        invoices.append(invoice_data)
    
    return invoices

def get_all_processed_invoices(status_filter=None, search_term=None):
    """Get invoices from all folders except pending_review"""
    all_invoices = []
    
    folders = {
        "Auto-Processed": settings.PROCESSED_DIR,
        "Approved": settings.APPROVED_DIR,
        "Rejected": settings.REJECTED_DIR
    }
    
    for status_name, folder_path in folders.items():
        if status_filter and status_filter != status_name:
            continue
        all_invoices.extend(get_invoices_from_folder(folder_path, status_name))
    
    # Search filter
    if search_term:
        search_term = search_term.lower().strip()
        all_invoices = [
            inv for inv in all_invoices 
            if search_term in inv["invoice_id"].lower()
        ]
    
    # Sort by invoice_id
    all_invoices.sort(key=lambda x: x["invoice_id"], reverse=True)
    
    return all_invoices

# Page header
st.title("📁 Invoice History")
st.markdown("View all processed invoices and their reports")

st.divider()

# Filters
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    status_filter = st.selectbox(
        "📊 Filter by Status",
        ["All", "Auto-Processed", "Approved", "Rejected"],
        help="Filter invoices by their processing status"
    )

with col2:
    search_term = st.text_input(
        "🔍 Search by Invoice ID",
        placeholder="Enter invoice ID...",
        help="Search for a specific invoice"
    )

with col3:
    st.write("")  # Spacing
    st.write("")  # Spacing
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# Get invoices
filter_value = None if status_filter == "All" else status_filter
invoices = get_all_processed_invoices(filter_value, search_term)

# Display count
st.caption(f"Found **{len(invoices)}** invoice(s)")

st.divider()

# Main layout
if not invoices:
    st.info("📭 No invoices found matching your criteria")
else:
    col_list, col_detail = st.columns([1, 2])
    
    with col_list:
        st.markdown("### 📋 Invoice List")
        
        for idx, invoice in enumerate(invoices, 1):
            # Status emoji
            if invoice["status"] == "Auto-Processed":
                status_icon = "✅"
            elif invoice["status"] == "Approved":
                status_icon = "👍"
            else:
                status_icon = "❌"
            
            button_label = f"{status_icon} **{invoice['invoice_id']}**"
            
            # Highlight selected
            is_selected = (
                "selected_history_invoice" in st.session_state 
                and st.session_state.selected_history_invoice == invoice["invoice_id"]
            )
            
            button_type = "primary" if is_selected else "secondary"
            
            if st.button(
                button_label,
                use_container_width=True,
                type=button_type,
                key=f"hist_btn_{invoice['invoice_id']}"
            ):
                st.session_state.selected_history_invoice = invoice["invoice_id"]
                st.rerun()
            
            # Quick info
            st.caption(f"💰 {invoice['amount']} • 🏢 {invoice['vendor'][:20]}...")
    
    with col_detail:
        if "selected_history_invoice" not in st.session_state or not st.session_state.selected_history_invoice:
            st.info("👈 Select an invoice from the list to view details")
        else:
            # Find selected invoice
            inv = next(
                (i for i in invoices if i["invoice_id"] == st.session_state.selected_history_invoice),
                None
            )
            
            if not inv:
                st.warning("⚠️ Invoice not found")
                st.session_state.selected_history_invoice = None
            else:
                # Invoice header
                st.markdown(f"### 📄 {inv['invoice_id']}")
                
                # Status badge
                if inv["status"] == "Auto-Processed":
                    st.success(f"✅ Status: {inv['status']}")
                elif inv["status"] == "Approved":
                    st.success(f"👍 Status: {inv['status']}")
                else:
                    st.error(f"❌ Status: {inv['status']}")
                
                # Tabs
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📊 Summary",
                    "📄 Document",
                    "📋 HTML Report",
                    "📝 JSON Data",
                    "✉️ Metadata"
                ])
                
                with tab1:
                    st.markdown("#### 📊 Quick Summary")
                    
                    if inv.get("report"):
                        report = inv["report"]
                        invoice_data = report.get("invoice_data", {})
                        
                        # Basic info only
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("🏢 Vendor", invoice_data.get("vendor_name", inv["vendor"]))
                        with col2:
                            st.metric("💰 Total", f"{invoice_data.get('currency', '')} {invoice_data.get('total_amount', inv['amount'])}")
                        with col3:
                            st.metric("📅 Invoice Date", invoice_data.get("invoice_date", inv["date"]))
                        with col4:
                            st.metric("📌 Status", inv["status"])
                        
                        st.divider()
                        
                        # Validation summary
                        rules = report.get("validation_rules", [])
                        if rules:
                            passed = sum(1 for r in rules if r.get("status") == "PASSED")
                            failed = sum(1 for r in rules if r.get("status") == "FAILED")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("✅ Passed Rules", passed)
                            with col2:
                                st.metric("❌ Failed Rules", failed)
                        
                        # Human review if exists
                        human_review = report.get("human_review")
                        if human_review:
                            st.divider()
                            st.markdown("#### 👤 Human Review")
                            
                            decision = human_review.get("decision", "")
                            if decision == "APPROVE":
                                st.success(f"**Decision:** ✅ {decision}")
                            else:
                                st.error(f"**Decision:** ❌ {decision}")
                            
                            st.info(f"**Feedback:** {human_review.get('feedback', 'No feedback provided')}")
                    
                    else:
                        # Fallback if no report
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🏢 Vendor", inv["vendor"])
                        with col2:
                            st.metric("💰 Amount", inv["amount"])
                        with col3:
                            st.metric("📅 Date", inv["date"])
                    
                    st.divider()
                    st.info("💡 View other tabs for detailed reports and documents")
                
                with tab2:
                    st.markdown("#### 📄 Document Preview")
                    if inv.get("invoice_file"):
                        if inv["invoice_file"].suffix.lower() == '.pdf':
                            display_pdf(inv["invoice_file"])
                        else:
                            st.image(str(inv["invoice_file"]))
                    else:
                        st.warning("📄 Document file not available")
                
                with tab3:
                    st.markdown("#### 📋 HTML Validation Report")
                    if inv.get("report_html_file"):
                        try:
                            html_content = open(inv["report_html_file"]).read()
                            components.html(html_content, height=800, scrolling=True)
                        except Exception as e:
                            st.error(f"❌ Error loading HTML report: {str(e)}")
                    else:
                        st.warning("📋 HTML report not available")
                
                with tab4:
                    st.markdown("#### 📝 JSON Report Data")
                    if inv.get("report"):
                        st.json(inv["report"], expanded=True)
                    else:
                        st.warning("📝 JSON report not available")
                
                with tab5:
                    st.markdown("#### ✉️ Invoice Metadata")
                    if inv.get("metadata"):
                        st.json(inv["metadata"], expanded=True)
                    else:
                        st.warning("✉️ Metadata not available")

# Footer
st.divider()
st.caption("💡 Tip: Use filters to narrow down your search. This page shows only processed invoices (not pending review).")