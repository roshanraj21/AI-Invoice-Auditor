import os
import sys
import json
import re
import faiss 
import numpy as np
from typing import Any, Dict, List, Optional

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from config.settings import VECTOR_STORE_DIR, LLM_EMBEDDING_MODEL
    from src.llm.litellm_gateway import LLMGateway
    
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings

except ImportError as e:
    print(f"Error importing modules in vector_store.py: {e}")
    sys.exit(1)


EMBEDDING_GATEWAY = LLMGateway(model=LLM_EMBEDDING_MODEL)
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "invoice_faiss_db")

class LiteLLMEmbeddings(Embeddings):
    """A wrapper that makes LLMGateway compatible with LangChain Embeddings interface."""
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def embed_query(self, text: str) -> List[float]:
        try:
            return self.gateway.get_embedding(text)
        except Exception as e:
            print(f"[EmbeddingWrapper] Error embedding query: {e}")
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            return [self.gateway.get_embedding(text) for text in texts]
        except Exception as e:
            print(f"[EmbeddingWrapper] Error embedding documents: {e}")
            return []

EMBEDDINGS = LiteLLMEmbeddings(gateway=EMBEDDING_GATEWAY)

def _load_faiss_index() -> Optional[FAISS]:
    """Loads FAISS index from disk, or returns None if not exists."""
    if not os.path.exists(FAISS_INDEX_PATH):
        print("[VectorStore] No FAISS index found. Creating new vector DB.")
        return None
    try:
        db = FAISS.load_local(FAISS_INDEX_PATH, EMBEDDINGS, allow_dangerous_deserialization=True)
        print(f"[VectorStore] Loaded FAISS index from {FAISS_INDEX_PATH}")
        return db
    except Exception as e:
        print(f"[VectorStore] Could not load FAISS index: {e}.")
        return None


# Adds readable summary → helps RAG answer why/rejection queries
def _failed_rules_summary(validation_rules: List[Dict[str, Any]]) -> str:
    fails = [f"{r.get('rule_name')}: {r.get('message')}" for r in validation_rules or [] if r.get("status") == "FAILED"]
    return "; ".join(fails) if fails else "None"


def format_invoice_for_rag(report_data: Dict[str, Any], file_metadata: Dict[str, Any]) -> str:
    invoice = report_data.get("invoice_data", {})
    validation_rules_list = report_data.get("validation_rules", [])
    analysis = report_data.get("ai_analysis", {})
    overall_status = report_data.get("validation_status", "N/A")
    translation_conf = report_data.get("translation_confidence")

    lines = [
        f"Invoice ID: {invoice.get('invoice_id', 'N/A')}",
        f"Vendor: {invoice.get('vendor_name', 'N/A')}",
        f"PO Number: {invoice.get('po_number', 'N/A')}",
        f"Date: {invoice.get('invoice_date', 'N/A')}",
        f"Total Amount: {invoice.get('total_amount', 0)} {invoice.get('currency', '')}",
        f"Status: {overall_status}",
        "--- Items ---"
    ]

    for item in invoice.get('line_items', []):
        lines.append(
            f"- {item.get('description')}: {item.get('quantity')} x {item.get('unit_price')} = {item.get('line_total')}"
        )

    if translation_conf is not None:
        lines.append(f"Translation Confidence: {round(translation_conf, 3)}")

    lines.extend([
        "\n--- Email & File Information ---",
        f"Sender Email: {file_metadata.get('sender', 'N/A')}",
        f"Email Subject: {file_metadata.get('subject', 'N/A')}",
        f"Received Date: {file_metadata.get('received_timestamp', 'N/A')}",
    ])
    
    lines.extend([
        "\n--- Audit Report ---",
        f"Recommendation: {analysis.get('recommendation', 'N/A')}",
        f"Summary: {analysis.get('analysis', 'N/A')}",
    ])

    for rule in validation_rules_list:
        if rule.get('status') == "FAILED":
            lines.append(f"Validation FAILED: {rule.get('rule_name')} - {rule.get('message')}")
    
    human_review = report_data.get('human_review')
    if human_review and isinstance(human_review, dict):
        lines.extend([
            "\n--- Human Review ---",
            f"Human Decision: {human_review.get('decision', 'N/A')}",
            f"Feedback: {human_review.get('feedback', 'N/A')}"
        ])
    
    return "\n".join(lines)


def _compact_invoice_summary(report_data: Dict[str, Any]) -> str:
    """Short searchable summary for analytics queries (why rejected, list reviewed, etc.)."""
    inv = report_data.get("invoice_data", {})
    status = report_data.get("validation_status", "N/A")

    hr = report_data.get("human_review") or {}
    decision = (hr.get("decision") or "").upper() if isinstance(hr, dict) else ""

    fails = _failed_rules_summary(report_data.get("validation_rules", []))
    return (
        f"{inv.get('invoice_id','N/A')} | Vendor={inv.get('vendor_name','N/A')} | "
        f"Status={status} | HumanDecision={decision or 'N/A'} | "
        f"Total={inv.get('total_amount',0)} {inv.get('currency','')} | "
        f"FailedRules={fails}"
    )


# metadata stored (critical for analytics)
def add_invoice_to_vector_store(
    report_data: Dict[str, Any],
    file_metadata: Dict[str, Any]
):
    doc_id = None
    try:
        invoice_data = report_data.get("invoice_data", {})
        validation_status = report_data.get("validation_status", "UNKNOWN")
        human_review = report_data.get("human_review") or {}

        doc_id = invoice_data.get('invoice_id', invoice_data.get('original_filename'))
        if not doc_id:
            raise ValueError("Report must have invoice_id or original_filename inside invoice_data")

        full_text = format_invoice_for_rag(report_data, file_metadata)
        summary = _compact_invoice_summary(report_data)
        failed_rules = _failed_rules_summary(report_data.get("validation_rules", []))

        # ✅ Embedding text = summary + full report improves retrieval quality
        page_content = summary + "\n\n" + full_text

        doc = Document(
            page_content=page_content,
            metadata={
                "doc_id": doc_id,
                "source": invoice_data.get('original_filename', 'N/A'),
                "vendor": invoice_data.get('vendor_name', 'N/A'),
                "status": validation_status,
                "total_amount": invoice_data.get('total_amount', 0),
                "sender": file_metadata.get('sender', 'N/A'),
                "translation_confidence": report_data.get("translation_confidence"),
                "failed_rules_summary": failed_rules,
                "human_decision": (human_review.get("decision") or "").upper(),
                "human_feedback": human_review.get("feedback"),
                "report_json_str": json.dumps(report_data, default=str),
                "meta_json_str": json.dumps(file_metadata, default=str)
            }
        )

        db = _load_faiss_index()
        if db is None:
            print(f"[VectorStore] Creating new index with document: {doc_id}")
            db = FAISS.from_documents([doc], EMBEDDINGS)
        else:
            print(f"[VectorStore] Adding document to existing index: {doc_id}")
            db.add_documents([doc])

        db.save_local(FAISS_INDEX_PATH)
        print(f"[VectorStore] ✅ Indexed & saved: {doc_id}")

    except Exception as e:
        print(f"[VectorStore] ❌ Failed to index {doc_id}. Error: {e}")


# -------------------------
# ✅ ANALYTICS HELPERS
# -------------------------

def _all_docs() -> List[Document]:
    db = _load_faiss_index()
    if db is None:
        return []
    return list(db.docstore._dict.values())


def get_invoice_by_id(invoice_id: str) -> Optional[Document]:
    invoice_id = (invoice_id or "").strip()
    for d in _all_docs():
        if d.metadata.get("doc_id") == invoice_id:
            return d
    return None


def get_invoices_by_status(statuses: List[str]) -> List[Document]:
    statuses = [s.upper() for s in statuses]
    out = []
    for d in _all_docs():
        md = d.metadata or {}
        if md.get("status","").upper() in statuses or md.get("human_decision","").upper() in statuses:
            out.append(d)
    return out


def get_human_reviewed() -> List[Document]:
    out = []
    for d in _all_docs():
        if (d.metadata or {}).get("human_decision") in ("APPROVE", "REJECT"):
            out.append(d)
    return out


def explain_rejection(invoice_id: str) -> str:
    doc = get_invoice_by_id(invoice_id)
    if not doc:
        return f"No invoice found with ID {invoice_id}."

    md = doc.metadata or {}
    report = {}
    try:
        report = json.loads(md.get("report_json_str") or "{}")
    except:
        report = {}

    lines = [f"Invoice {invoice_id} — Rejection Explanation"]

    # Human review details
    hr = report.get("human_review")
    if hr:
        lines.append(f"- Human Decision: {hr.get('decision','N/A')}")
        if hr.get("feedback"):
            lines.append(f"- Reviewer Feedback: {hr.get('feedback')}")

    # Failed rules
    fails = [r for r in (report.get("validation_rules") or []) if r.get("status") == "FAILED"]
    if fails:
        lines.append("- Failed Rules:")
        for r in fails:
            src = r.get("source","System")
            lines.append(f"  • [{src}] {r.get('rule_name')}: {r.get('message')}")
    else:
        if md.get("failed_rules_summary"):
            lines.append(f"- Failed Rules: {md.get('failed_rules_summary')}")

    return "\n".join(lines)


def search_vector_store(question: str, top_k: int = 3) -> str:
    db = _load_faiss_index()
    if db is None:
        return "No information available."
        
    try:
        results = db.similarity_search(question, k=top_k)
        if not results:
            return "No information available."
        
        context = []
        for doc in results:
            context.append(f"--- Context (Invoice: {doc.metadata.get('doc_id','N/A')}) ---\n{doc.page_content}")

        return "\n\n".join(context)
        
    except Exception as e:
        print(f"[VectorStore] FAILED search. Error: {e}")
        return "Error during search."
