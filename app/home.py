import streamlit as st

from utils.config import init_app


st.set_page_config(
    page_title="Home - VSAT App",
    page_icon="🏠",
)

init_app()

st.title("🏠 VSAT App Homepage")
st.write("Welcome to the VSAT application.")
