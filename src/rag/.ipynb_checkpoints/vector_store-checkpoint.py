import os
import sys
import json
import faiss 
import numpy as np
from typing import Any, Dict, List

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
    print("Please ensure 'langchain-community', 'langchain-core', and 'faiss-cpu' are installed.")
    sys.exit(1)

# --- Initialize ---
# A LLMGateway instance to get embeddings
EMBEDDING_GATEWAY = LLMGateway(model=LLM_EMBEDDING_MODEL)
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "invoice_faiss_db")
# ------------------

# --- LangChain Embedding Wrapper ---
class LiteLLMEmbeddings(Embeddings):
    """
    A wrapper class to make our LLMGateway compatible 
    with the LangChain Embeddings interface.
    """
    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        try:
            return self.gateway.get_embedding(text)
        except Exception as e:
            print(f"[EmbeddingWrapper] Error embedding query: {e}")
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        try:
            return [self.gateway.get_embedding(text) for text in texts]
        except Exception as e:
            print(f"[EmbeddingWrapper] Error embedding documents: {e}")
            return []

EMBEDDINGS = LiteLLMEmbeddings(gateway=EMBEDDING_GATEWAY)

def _load_faiss_index() -> FAISS | None:
    """Loads a FAISS index from the local path."""
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

def format_invoice_for_rag(invoice_data: dict[str, Any], report_data: dict[str, Any]) -> str:
    """
    Converts the structured invoice and report data into a single text string
    for embedding and retrieval.
    """
    # --- Invoice Data ---
    lines = [
        f"Invoice ID: {invoice_data.get('invoice_id') or invoice_data.get('original_filename', 'N/A')}",
        f"Vendor: {invoice_data.get('vendor_name', 'N/A')}",
        f"PO Number: {invoice_data.get('po_number', 'N/A')}",
        f"Date: {invoice_data.get('invoice_date', 'N/A')}",
        f"Total Amount: {invoice_data.get('total_amount', 0)} {invoice_data.get('currency', '')}",
        "--- Items ---"
    ]
    for item in invoice_data.get('line_items', []):
        lines.append(f"- {item.get('description')}: {item.get('quantity')} x {item.get('unit_price')} = {item.get('line_total')}")
    
    # --- Report Data ---
    lines.extend([
        "\n--- Audit Report ---",
        f"Status: {report_data.get('overall_status', 'N/A')}",
        f"Recommendation: {report_data.get('recommendation', 'N/A')}",
        f"Summary: {report_data.get('executive_summary', 'N/A')}",
        f"Findings: {report_data.get('detailed_findings', 'N/A')}"
    ])
    
    return "\n".join(lines)

def add_invoice_to_vector_store(
    invoice_data: Dict[str, Any], 
    report_data: Dict[str, Any],
    file_metadata: Dict[str, Any]
):
    """
    Main function to index a new invoice using LangChain.
    It creates an embedding and adds it to the FAISS index.
    """
    try:
        # Get unique ID
        doc_id = invoice_data.get('invoice_id') or invoice_data.get('original_filename')
        if not doc_id:
            raise ValueError("Invoice data must have 'invoice_id' or 'original_filename'")
        # Format a single text blob for embedding
        text_to_embed = format_invoice_for_rag(invoice_data, report_data)
        
        # Create a LangChain Document with rich metadata
        doc = Document(
            page_content=text_to_embed,
            metadata={
                # Key fields for filtering
                "doc_id": doc_id,
                "source": invoice_data.get('original_filename', 'N/A'),
                "vendor": invoice_data.get('vendor_name', 'N/A'),
                "status": report_data.get('overall_status', 'N/A'),
                "language": file_metadata.get('language', 'unknown'),
                
                # Full data as JSON strings for retrieval
                "invoice_json_str": json.dumps(invoice_data),
                "report_json_str": json.dumps(report_data),
                "meta_json_str": json.dumps(file_metadata)
            }
        )

        # Load the existing index
        db = _load_faiss_index()
        # Add to index
        if db is None:
            # Index doesn't exist, create a new one
            print(f"[VectorStore] Creating new index with document: {doc_id}")
            db = FAISS.from_documents([doc], EMBEDDINGS)
        else:
            # Index exists, add the new document
            print(f"[VectorStore] Adding document to existing index: {doc_id}")
            db.add_documents([doc])
        
        # Save the updated index back to disk
        db.save_local(FAISS_INDEX_PATH)
        print(f"[VectorStore] Successfully indexed and saved document: {doc_id}")

    except Exception as e:
        print(f"[VectorStore] FAILED to index document: {doc_id}. Error: {e}")

def search_vector_store(question: str, top_k: int = 3) -> str:
    """
    Searches the vector store for a questions
    Returns:
        A string of the most relevant context.
    """
    db = _load_faiss_index()
    
    if db is None:
        print("[VectorStore] Cannot search: Index is not initialized.")
        return "No information available."
        
    try:
        results = db.similarity_search(question, k=top_k)
        context = []
        if not results:
            print("[VectorStore] No relevant documents found.")
            return "No information available."
            
        for doc in results:
            # The 'source' metadata is the original filename
            context.append(f"--- Context (Doc: {doc.metadata.get('source', 'N/A')}) ---\n{doc.page_content}")
                
        print(f"[VectorStore] Found {len(context)} relevant documents for question.")
        return "\n\n".join(context)
        
    except Exception as e:
        print(f"[VectorStore] FAILED to search index. Error: {e}")
        return "Error during search."

