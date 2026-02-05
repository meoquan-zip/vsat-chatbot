import os

import streamlit as st
from dotenv import load_dotenv

from .db_orm import create_all_tables
from .template import load_templates_as_env_vars


def init_app():
    load_dotenv()
    data_dir = "./data/"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    create_all_tables()
    load_templates_as_env_vars()
    st.session_state["authentication_status"] = True
    st.session_state["username"] = "admin"
