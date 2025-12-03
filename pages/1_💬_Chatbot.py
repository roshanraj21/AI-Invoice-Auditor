import streamlit as st
import time
from langchain_core.messages import HumanMessage, AIMessage
from src.rag.rag_agent import get_compiled_app

st.set_page_config(page_title="Chatbot", page_icon="💬", layout="wide")

st.title("💬 RAG Chatbot")
st.markdown("Ask questions about invoices, vendors, and processing history")

# Initialize chatbot
if "rag_app" not in st.session_state:
    with st.spinner("Loading chatbot..."):
        st.session_state.rag_app = get_compiled_app()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit_thread_{int(time.time())}"

# Sidebar with chat info
with st.sidebar:
    st.markdown("### 💡 Chat Information")
    st.info(f"**Thread ID:** `{st.session_state.thread_id}`")
    st.metric("Messages", len(st.session_state.messages))
    
    st.divider()
    
    st.markdown("### 🎯 Example Questions")
    st.markdown("""
    - "Show me all pending invoices"
    - "What's the total amount from Vendor X?"
    - "List rejected invoices this month"
    - "Show invoices over $10,000"
    - "Which vendor has the most invoices?"
    """)
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = f"streamlit_thread_{int(time.time())}"
        st.rerun()

# Main chat interface
if not st.session_state.messages:
    st.info("👋 Welcome! Ask me anything about your invoices. I can search, analyze, and provide insights from your invoice database.")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask me about invoices, vendors, amounts..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # Check if chatbot is available
    if st.session_state.rag_app is None:
        with st.chat_message("assistant"):
            error_msg = "❌ Chatbot backend is currently unavailable. Please try again later."
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
    else:
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                # Build chat history
                history = []
                for msg in st.session_state.messages[:-1]:  # Exclude current message
                    if msg["role"] == "user":
                        history.append(HumanMessage(content=msg["content"]))
                    else:
                        history.append(AIMessage(content=msg["content"]))

                # Prepare inputs
                inputs = {
                    "user_question": prompt,
                    "chat_history": history
                }
                config = {"configurable": {"thread_id": st.session_state.thread_id}}

                try:
                    # Get response from RAG agent
                    result = st.session_state.rag_app.invoke(inputs, config=config)
                    answer = result.get("answer", "I couldn't find an answer to that question.")
                    
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    error_msg = f"⚠️ An error occurred: {str(e)}"
                    st.error(error_msg)
                    # Remove the user message that caused the error
                    st.session_state.messages.pop()

# Footer
st.divider()
st.caption("💡 Tip: You can ask about specific invoices, vendors, amounts, dates, or request summaries and analytics")