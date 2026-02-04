import streamlit as st

from utils.db_orm import init_db


st.set_page_config(
    page_title="Home - VSAT App",
    page_icon="🏠",
)

init_db()

st.title("🏠 VSAT App Homepage")
st.write("Welcome to the VSAT application.")
