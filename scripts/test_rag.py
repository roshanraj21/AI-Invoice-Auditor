import os
import sys
from pprint import pprint

# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --------------------------------

try:
    # We must setup credentials *before* importing the gateway
    from src.llm.litellm_gateway import setup_aws_credentials
    setup_aws_credentials()

    from src.rag.vector_store import search_vector_store
    from src.llm.litellm_gateway import LLMGateway
    from config.settings import LLM_RAG_MODEL
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def run_rag_query(question: str):
    """
    Runs an end-to-end RAG query.
    1. Searches the vector store for context.
    2. Calls the LLM to generate an answer based on that context.
    """
    # 1. Search Vector Store
    print("Searching vector store for relevant context...")
    context = search_vector_store(question, top_k=3)
    
    if not context or context == "No relevant context found.":
        print("--- [RAG Answer] ---")
        print("Sorry, I could not find any relevant documents in the vector store to answer that question.")
        return

    print("[RAG] context retrieved")
    # pprint(context)

    # 2. Call LLM for Generation
    print("Sending context to LLM to generate an answer...")
    try:
        rag_gateway = LLMGateway(model=LLM_RAG_MODEL)
        answer = rag_gateway.call_for_rag_generation(question, context)
        print("\n--- [RAG Answer] ---")
        print(answer)
        print("--------------------")
        return answer
        
    except Exception as e:
        print(f"\n--- [RAG Error] ---")
        print(f"Failed to generate RAG answer: {e}")
        return "Failed to generate RAG answer"
if __name__ == "__main__":
    # Get question from command line arguments
    if len(sys.argv) > 1:
        user_question = " ".join(sys.argv[1:])
        run_rag_query(user_question)
    else:
        print("--- [RAG Query] ---")
        print("Error: Please provide a question as an argument.")
        print("Example:")
        print("python scripts/query_rag.py \"What was the total for invoice INV-1002?\"")