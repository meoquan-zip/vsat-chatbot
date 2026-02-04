import streamlit as st

from utils.chat_app import ChatApp
from utils.db_orm import init_db

st.set_page_config(
    page_title="AI Assistant - VSAT App",
    page_icon="🤖",
)

init_db()

chat_app = ChatApp()
chat_app.run()
