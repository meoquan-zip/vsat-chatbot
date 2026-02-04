import os

import streamlit as st

from utils.db_orm import create_all_tables

if not os.path.exists("./data/"):
    os.makedirs("./data/")

create_all_tables()

st.set_page_config(
    page_title="Home - VSAT App",
    page_icon="🏠",
)

st.title("🏠 VSAT App Homepage")
st.write("Welcome to the VSAT application.")
