import streamlit as st
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
try:
    from src.graph.review_workflow import review_app
except:
    review_app = None

def process_human_decision(invoice_id, decision, feedback):
    if review_app is None:
        st.error("Review workflow unavailable.")
        return False

    try:
        result = review_app.invoke({
            "invoice_id": invoice_id,
            "human_decision": decision,
            "human_feedback": feedback
        })

        if result.get("error"):
            st.error(result["error"])
            return False

        return True

    except Exception as e:
        st.error(f"Workflow error: {e}")
        return False
