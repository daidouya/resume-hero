import streamlit as st

st.title("Resume Hero")

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Upload PDFs"):
        st.switch_page("pages/upload.py")  # Navigate to Upload Page

with col2:
    if st.button("📥 Retrieve Results"):
        st.switch_page("pages/retrieve.py")  # Navigate to Results Page