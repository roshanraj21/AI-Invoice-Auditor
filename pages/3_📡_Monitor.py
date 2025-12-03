import streamlit as st
import json
from pathlib import Path
import streamlit.components.v1 as components
import os
import sys
import subprocess
import time

# --- Setup and Imports ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Assuming config.settings exists and INCOMING_DIR is defined
try:
    from config.settings import INCOMING_DIR
except ImportError:
    # Fallback for demonstration if config is not available
    INCOMING_DIR = Path.home() / "temp_incoming"

# Set up the paths
LOG_FILE = Path("pipeline_history.jsonl")
RESOLVED_INCOMING = Path(INCOMING_DIR).expanduser().resolve()
st.caption(f"📂 INCOMING_DIR = `{RESOLVED_INCOMING}`")

# Streamlit page setup
st.set_page_config(page_title="Monitor & Control", page_icon="📡", layout="wide")

# Page header
st.title("📡 Processing Monitor & Control Center")
st.markdown("Monitor pipeline execution and trigger processing actions")
st.divider()

# ---------- SERVICE CONTROL (Original code retained) ----------
st.markdown("### ⚙️ Service Management")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🚀 FastAPI Server")
    if "fastapi_process" not in st.session_state:
        st.session_state.fastapi_process = None
    
    subcol1, subcol2 = st.columns(2)
    with subcol1:
        if st.button("▶️ Start", key="start_fastapi", use_container_width=True):
            if st.session_state.fastapi_process is None:
                # IMPORTANT: Ensure this script path is correct relative to execution context
                try:
                    st.session_state.fastapi_process = subprocess.Popen(["python", "scripts/start_erp.py"])
                    st.success("✅ Server started")
                except FileNotFoundError:
                    st.error("Error: scripts/start_erp.py not found.")
            else:
                st.info("Already running")
    
    with subcol2:
        if st.button("⛔ Stop", key="stop_fastapi", use_container_width=True):
            if st.session_state.fastapi_process is not None:
                st.session_state.fastapi_process.terminate()
                st.session_state.fastapi_process = None
                st.success("✅ Server stopped")
            else:
                st.info("Not running")
    
    # Status indicator
    if st.session_state.fastapi_process is not None:
        st.success("🟢 **Status:** Running")
    else:
        st.error("🔴 **Status:** Stopped")

with col2:
    st.markdown("#### 👁️ Monitor Agent")
    if "monitor_process" not in st.session_state:
        st.session_state.monitor_process = None
    
    subcol1, subcol2 = st.columns(2)
    with subcol1:
        if st.button("▶️ Start", key="start_monitor", use_container_width=True):
            if st.session_state.monitor_process is None:
                # IMPORTANT: Ensure this script path is correct relative to execution context
                try:
                    st.session_state.monitor_process = subprocess.Popen(["python", "scripts/monitor_agent.py"])
                    st.success("✅ Agent started")
                except FileNotFoundError:
                    st.error("Error: scripts/monitor_agent.py not found.")
            else:
                st.info("Already running")
    
    with subcol2:
        if st.button("⛔ Stop", key="stop_monitor", use_container_width=True):
            if st.session_state.monitor_process is not None:
                st.session_state.monitor_process.terminate()
                st.session_state.monitor_process = None
                st.success("✅ Agent stopped")
            else:
                st.info("Not running")
    
    # Status indicator
    if st.session_state.monitor_process is not None:
        st.success("🟢 **Status:** Running")
    else:
        st.error("🔴 **Status:** Stopped")

st.divider()

# ---------- FILE UPLOAD (Original code retained) ----------
st.markdown("### 📤 Upload Documents to Pipeline")

col1, col2 = st.columns(2)

with col1:
    invoice_files = st.file_uploader(
        "📄 Invoice Files",
        type=["pdf", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="Upload invoice documents to process"
    )
    if invoice_files:
        st.success(f"✅ {len(invoice_files)} invoice(s) selected")

with col2:
    meta_files = st.file_uploader(
        "📋 Metadata Files (.meta.json)",
        type=["json"],
        accept_multiple_files=True,
        help="Upload matching metadata files"
    )
    if meta_files:
        st.success(f"✅ {len(meta_files)} metadata file(s) selected")

if st.button("🚀 Send All to Pipeline", type="primary", use_container_width=True):
    if not invoice_files or not meta_files:
        st.error("⚠️ Please upload both invoices AND metadata files")
        st.stop()

    invoice_names = [f.name for f in invoice_files]
    meta_names = [f.name for f in meta_files]

    # Validation
    missing_meta = []
    for inv_name in invoice_names:
        inv_base = inv_name.rsplit('.', 1)[0]
        matching_meta = f"{inv_base}.meta.json"
        if matching_meta not in meta_names:
            missing_meta.append((inv_name, matching_meta))

    if missing_meta:
        st.error("❌ Missing metadata files:")
        for inv, meta in missing_meta:
            st.markdown(f"  • `{inv}` → expected `{meta}`")
        st.stop()

    # Save files
    RESOLVED_INCOMING.mkdir(parents=True, exist_ok=True)

    with st.spinner("📤 Uploading files..."):
        for f in invoice_files:
            with open(RESOLVED_INCOMING / f.name, "wb") as out:
                out.write(f.read())

        for f in meta_files:
            with open(RESOLVED_INCOMING / f.name, "wb") as out:
                out.write(f.read())


    st.success(f"✅ Uploaded {len(invoice_files)} invoice(s) and {len(meta_files)} metadata file(s)")
    st.info("🤖 Monitor agent will process them automatically")

st.divider()

# ---------- LOG VIEWER (FIXED SECTION) ----------
st.markdown("### 🔍 Live Processing Logs")

# Function to read logs and return the latest entries (slightly improved for safety)
def read_logs():
    if not LOG_FILE.exists():
        return []

    try:
        # Read the last 200 lines for performance
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()[-200:]
        # Filter out empty lines before parsing JSON
        events = [json.loads(l) for l in lines if l.strip()]
        return events
    except Exception as e:
        # Handle cases where the log file might be partially written or corrupted
        st.warning(f"Error reading log file: {e}")
        return []

if LOG_FILE.exists():
    # Read the log snapshot for the current rerun of the script
    all_events = read_logs()

    # Filters and refresh/auto-control (Expanded columns for new control)
    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
    with col1:
        only_errors = st.checkbox("🔴 Errors only", key="filter_errors")
    with col2:
        only_review = st.checkbox("⚠️ Review-routed only", key="filter_review")
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col4:
        # This controls the actual Javascript scrolling action
        auto_scroll = st.checkbox("↓ Scroll Down", value=True)
    with col5:
        # This controls the script's self-rerun for live updates
        auto_refresh = st.checkbox("✨ Auto-Refresh (1s)", value=False)


    # Filter logs
    filtered = all_events
    if only_errors:
        filtered = [e for e in filtered if e.get("status") == "error"]
    if only_review:
        filtered = [e for e in filtered if "review" in e.get("message", "").lower()]

    # Display count
    st.caption(f"Showing **{len(filtered)}** of **{len(all_events)}** recent events")

    # Display logs using HTML component
    scroll_html = """
    <div id="logbox" style="
        height:400px;
        width:100%;
        overflow-y: auto;
        border:1px solid #e0e0e0;
        border-radius:8px;
        padding:14px;
        font-size:14px;
        background:#ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
    """

    if filtered:
        for e in filtered:
            # Determine icon and color (using .get() for safety)
            status = e.get("status", "unknown")
            message = e.get("message", "No message")

            if status == "completed":
                icon = "✅"
                color = "#10b981"
            elif status == "error":
                icon = "🔴"
                color = "#ef4444"
            elif "review" in message.lower():
                icon = "⚠️"
                color = "#f59e0b"
            else: # Catch for 'started', 'processing', etc.
                icon = "➡️"
                color = "#3b82f6"
            
            # Format stage name
            stage_name = e.get('stage', 'N/A').replace('_', ' ')

            scroll_html += f"""
            <div style="
                margin-bottom:12px;
                padding:12px;
                background:#f9fafb;
                border-left:4px solid {color};
                border-radius:6px;
            ">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                    <span style="font-size:18px;">{icon}</span>
                    <strong style="color:#111827; font-size:15px;">{e.get('invoice_id', 'N/A')}</strong>
                    <span style="color:#6b7280; font-size:12px;">•</span>
                    <span style="color:#374151; font-size:13px; text-transform:capitalize;">{stage_name}</span>
                </div>
                <div style="font-size:12px; color:#9ca3af; margin-bottom:6px;">
                    🕒 {e.get('timestamp', 'N/A')}
                </div>
                <div style="font-size:13px; color:#4b5563; line-height:1.5;">
                    {message}
                </div>
            </div>
            """
    else:
        scroll_html += """
        <div style="text-align:center; padding:60px 20px; color:#9ca3af;">
            <div style="font-size:48px; margin-bottom:12px;">📭</div>
            <div style="font-size:16px; font-weight:500;">No logs match your filters</div>
            <div style="font-size:14px; margin-top:8px;">Try adjusting the filters above</div>
        </div>
        """

    # Auto-scroll script (triggered only if checked)
    if auto_scroll:
        scroll_html += """
        <script>
        var box = document.getElementById('logbox');
        box.scrollTop = box.scrollHeight;
        </script>
        """

    scroll_html += "</div>"

    components.html(scroll_html, height=450, scrolling=False)

    # Auto-Refresh Logic: Rerun the script after 1 second to update logs
    if auto_refresh:
        time.sleep(1)
        st.rerun()

else:
    st.info("📭 No logs recorded yet. Upload some documents to get started!")

# Footer
st.divider()
st.caption("💡 Tip: Keep both services running for automatic processing. Logs update in real-time.")