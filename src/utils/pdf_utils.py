import base64
import streamlit as st

def display_pdf(pdf_path):
    if not pdf_path or not pdf_path.exists():
        st.warning("Invoice file not found.")
        return

    ext = pdf_path.suffix.lower()

    if ext in ['.png', '.jpg', '.jpeg']:
        st.image(str(pdf_path), use_column_width=True)

    elif ext == '.pdf':
        with open(pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')

        pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}"
        width="100%" height="800" type="application/pdf"></iframe>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
