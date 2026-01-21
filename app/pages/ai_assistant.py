import streamlit as st

from utils.chat_app import ChatApp

chat_app = ChatApp()
st.set_page_config(
    page_title="AI Assistant - VSAT App",
    page_icon="🤖",
)
chat_app.run()
