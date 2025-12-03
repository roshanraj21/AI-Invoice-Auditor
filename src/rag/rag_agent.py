import os
import sys
import operator
from typing import List, TypedDict, Annotated

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.llm.litellm_gateway import setup_aws_credentials
    setup_aws_credentials()

    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langgraph.graph import StateGraph, END, START
    from langgraph.checkpoint.memory import InMemorySaver

    from src.rag.vector_store import (
        search_vector_store,
        get_human_reviewed,
        get_invoices_by_status,
        get_invoice_by_id,
        explain_rejection,
    )
    from src.llm.litellm_gateway import LLMGateway
    from config.settings import LLM_RAG_MODEL

except ImportError as e:
    print(f"Error importing modules in rag_chatbot_langgraph.py: {e}")
    sys.exit(1)

class RAGAgentState(TypedDict):
    user_question: str
    context: str
    answer: str
    chat_history: Annotated[List[BaseMessage], operator.add]

# -------------------------
# Simple router
# -------------------------
def _route(question: str) -> str:
    q = (question or "").lower()

    # Human review
    if "human reviewed" in q or "human-review" in q or "reviewed by human" in q:
        return "HUMAN_REVIEWED"

    # Why rejected <invoice_id>?
    if ("why" in q and "reject" in q) or ("why" in q and "rejected" in q):
        return "WHY_REJECTED"

    # Status buckets
    if "rejected invoices" in q or "show rejected" in q or "list rejected" in q:
        return "LIST_REJECTED"
    if "approved invoices" in q or "show approved" in q or "list approved" in q:
        return "LIST_APPROVED"
    if "pending review" in q or "under review" in q:
        return "LIST_PENDING"

    # Rules / policy
    if "validation rules" in q or "what rules" in q or "which rules" in q:
        return "LIST_RULES"

    return "RAG_SEARCH"

def _fmt_docs_brief(docs: List) -> str:
    if not docs:
        return "No matching invoices."
    lines = ["Matched Invoices:"]
    for d in docs:
        md = d.metadata or {}
        lines.append(
            f"- {md.get('doc_id','N/A')} | Vendor={md.get('vendor','N/A')} | "
            f"Status={md.get('status','N/A')} | HumanDecision={md.get('human_decision','N/A')} | "
            f"Total={md.get('total_amount','N/A')}"
        )
    return "\n".join(lines)

def _infer_invoice_id(question: str) -> str:
    # naive extract token like INV_XXX or FAC-XXX
    import re
    m = re.search(r'([A-Za-z]+[-_]\d{2,}|\bINV[-_][A-Za-z0-9]+\b|\b[A-Z]{2,}[-_]\d{2,}\b)', question)
    return m.group(0) if m else ""

def retrieve_documents(state: RAGAgentState)-> RAGAgentState:
    print("---NODE: Retrieving documents---")
    question = state['user_question']
    route = _route(question)

    # 1) Human reviewed?
    if route == "HUMAN_REVIEWED":
        docs = get_human_reviewed()
        context = _fmt_docs_brief(docs)
        return {"context": context}

    # 2) Why rejected <invoice_id>?
    if route == "WHY_REJECTED":
        inv_id = _infer_invoice_id(question)
        if not inv_id:
            # if not found, return a short guidance
            return {"context": "Please specify an invoice id (e.g., INV_ES_003) to explain rejection."}
        explanation = explain_rejection(inv_id)
        return {"context": explanation}

    # 3) Status buckets
    if route == "LIST_REJECTED":
        docs = get_invoices_by_status(["REJECT", "FAILED"])
        return {"context": _fmt_docs_brief(docs)}

    if route == "LIST_APPROVED":
        docs = get_invoices_by_status(["APPROVE", "PASSED"])
        return {"context": _fmt_docs_brief(docs)}

    if route == "LIST_PENDING":
        # PENDING REVIEW invoices: those with status FAILED (pre-human) and no human decision yet
        # For simplicity, show those with status FAILED and human_decision empty
        docs = [d for d in get_invoices_by_status(["FAILED"]) if not (d.metadata or {}).get("human_decision")]
        return {"context": _fmt_docs_brief(docs)}

    # 4) Rules / policy
    if route == "LIST_RULES":
        policy = (
            "Validation Rules Checked:\n"
            "- Required header fields\n"
            "- Required line item fields\n"
            "- Currency check\n"
            "- Subtotal vs line-items sum\n"
            "- Total vs (subtotal + tax)\n"
            "- Vendor existence in ERP\n"
            "- PO validity + Vendor matches PO\n"
            "- SKU exists in ERP, qty/price tolerance vs PO\n"
            "- AI anomaly checks: suspicious vendor name, unusual currency, extreme total\n"
        )
        return {"context": policy}

    # 5) Fallback to standard vector search
    context = search_vector_store(question, top_k=3)
    return {"context": context}

def generate_answer(state: RAGAgentState):
    question = state['user_question']
    context = state['context']

    rag_gateway = LLMGateway(model=LLM_RAG_MODEL)

    print(f"[LLMGateway] Generating RAG answer...")        
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Q&A assistant for an invoice auditing system. "
                "Use the given context faithfully. If the context does not contain the answer, say you don't know. "
                "Be concise and list IDs in bullets when returning lists."
            ),
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
    ]        
  
    answer = rag_gateway._call_llm(messages, temperature=0.1, max_tokens=350)
    print(f"[LLMGateway] ✓ RAG generation successful")
    print("\n--- [RAG Answer] ---")
    print(answer)
    
    return {
        "answer": answer,
        # It’s fine if chat history is not used downstream; keep type safe:
        "chat_history": [AIMessage(content=answer)]
    }

def get_compiled_app():
    print("[Chatbot Backend] Building graph...")
    workflow = StateGraph(RAGAgentState)
    workflow.add_node("retrieve_documents", retrieve_documents)
    workflow.add_node("generate_answer", generate_answer)

    workflow.add_edge(START, "retrieve_documents")
    workflow.add_edge("retrieve_documents", "generate_answer")
    workflow.add_edge("generate_answer", END)

    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memory)

    print("[RAG Chatbot] Graph compiled and ready.")
    return app
