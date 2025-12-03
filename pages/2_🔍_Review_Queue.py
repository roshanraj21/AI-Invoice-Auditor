import streamlit as st
import time
import streamlit.components.v1 as components
from src.utils.invoice_utils import get_pending_invoices
from src.utils.review_utils import process_human_decision
from src.utils.pdf_utils import display_pdf
from src.utils.stats_utils import refresh_invoice_counts

st.set_page_config(page_title="Review Queue", page_icon="🔍", layout="wide")

st.title("🔍 Invoice Review Queue")
st.markdown("Review and approve/reject invoices that require human attention")

# Get pending invoices
pending_invoices = get_pending_invoices()

# Display status
if not pending_invoices:
    st.success("🎉 Great job! No invoices pending review at the moment.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh List", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("📊 Back to Dashboard", use_container_width=True):
            st.switch_page("app.py")
else:
    # Show count with visual indicator
    if len(pending_invoices) > 10:
        st.error(f"⚠️ **{len(pending_invoices)} invoices** require review")
    elif len(pending_invoices) > 5:
        st.warning(f"⚠️ **{len(pending_invoices)} invoices** require review")
    else:
        st.info(f"📋 **{len(pending_invoices)} invoices** require review")

    st.divider()

    # Two-column layout
    col_list, col_detail = st.columns([1, 2])

    with col_list:
        st.markdown("### 📋 Pending List")
        st.caption("Click on an invoice to review")
        
        # Display invoice buttons
        for idx, invoice in enumerate(pending_invoices, 1):
            button_label = f"**{idx}.** {invoice['invoice_id']}"
            
            # Highlight selected invoice
            is_selected = (
                "selected_invoice" in st.session_state 
                and st.session_state.selected_invoice == invoice["invoice_id"]
            )
            
            button_type = "primary" if is_selected else "secondary"
            
            if st.button(
                button_label, 
                use_container_width=True, 
                type=button_type,
                key=f"inv_btn_{invoice['invoice_id']}"
            ):
                st.session_state.selected_invoice = invoice["invoice_id"]
                st.rerun()
            
            # Show quick info below button
            st.caption(f"💰 {invoice['amount']} • 🏢 {invoice['vendor'][:20]}...")

    with col_detail:
        if "selected_invoice" not in st.session_state or not st.session_state.selected_invoice:
            st.info("👈 Select an invoice from the list to begin review")
        else:
            # Find selected invoice
            inv = next(
                (i for i in pending_invoices if i["invoice_id"] == st.session_state.selected_invoice), 
                None
            )

            if not inv:
                st.warning("⚠️ Invoice not available. Refreshing...")
                st.session_state.selected_invoice = None
                time.sleep(1)
                st.rerun()

            # Invoice header
            st.markdown(f"### 📄 {inv['invoice_id']}")
            
            # Create tabs for different views
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📋 Review & Decision",
                "📄 Document Preview",
                "📊 HTML Report",
                "📝 JSON Data",
                "✉️ Metadata"
            ])

            with tab1:
                # Key information
                st.markdown("#### 📊 Invoice Details")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🏢 Vendor", inv["vendor"])
                with col2:
                    st.metric("💰 Amount", inv["amount"])
                with col3:
                    st.metric("📅 Date", inv["date"])
                with col4:
                    st.metric("📌 Status", inv["status"])

                st.divider()

                # Issues section
                st.markdown("#### ⚠️ Validation Issues")
                if inv["issues"]:
                    for issue in inv["issues"]:
                        st.error(f"❌ {issue}")
                else:
                    st.success("✅ No validation issues detected")

                st.divider()

                # Decision section
                st.markdown("#### ✍️ Your Decision")
                
                col1, col2 = st.columns(2)
                with col1:
                    decision = st.radio(
                        "Action",
                        ["APPROVE", "REJECT"],
                        help="Choose whether to approve or reject this invoice"
                    )
                
                with col2:
                    if decision == "APPROVE":
                        st.success("✅ You are approving this invoice")
                    else:
                        st.error("❌ You are rejecting this invoice")

                feedback = st.text_area(
                    "Feedback (required)",
                    placeholder="Explain your decision. This will be logged for audit purposes.",
                    help="Provide detailed reasoning for your decision",
                    height=100
                )

                # Submit button
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button(
                        f"{'✅ Approve' if decision == 'APPROVE' else '❌ Reject'} Invoice",
                        use_container_width=True,
                        type="primary"
                    ):
                        if not feedback or len(feedback.strip()) < 5:
                            st.error("⚠️ Please provide detailed feedback (at least 5 characters)")
                        else:
                            with st.spinner(f"Processing {decision.lower()}..."):
                                success = process_human_decision(
                                    inv["invoice_id"], 
                                    decision, 
                                    feedback
                                )
                                
                                if success:
                                    st.success(f"✅ Invoice {decision.lower()}ed successfully!")
                                    time.sleep(1.5)
                                    
                                    # Clear selection and refresh
                                    st.session_state.selected_invoice = None
                                    st.session_state.invoices_data = refresh_invoice_counts()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to process decision. Please try again.")

            with tab2:
                st.markdown("#### 📄 Document Preview")
                if inv.get("pdf_file"):
                    display_pdf(inv["pdf_file"])
                else:
                    st.warning("📄 PDF file not available")

            with tab3:
                st.markdown("#### 📊 HTML Validation Report")
                if inv.get("report_html_file"):
                    try:
                        html_content = open(inv["report_html_file"]).read()
                        components.html(html_content, height=800, scrolling=True)
                    except Exception as e:
                        st.error(f"❌ Error loading HTML report: {str(e)}")
                else:
                    st.warning("📊 HTML report not available")

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
st.caption("💡 Tip: Review all tabs before making a decision. Use the feedback field to document your reasoning.")