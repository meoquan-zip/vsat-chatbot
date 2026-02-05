import streamlit as st

from utils.chat_app import ChatApp
from utils.config import init_app

st.set_page_config(
    page_title="AI Assistant - VSAT App",
    page_icon="🤖",
)

init_app()

chat_app = ChatApp()
chat_app.run()
