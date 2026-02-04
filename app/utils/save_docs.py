import os
import shutil

import streamlit as st
from langchain.docstore.document import Document

from .db_orm import Incident
from .prepare_vectordb import (
    ensure_user_dirs, get_user_dirs,
    get_vectorstore_user,
)


def save_docs_to_vectordb_user(username: str, uploaded_docs, existing_docs):
    """
    Save newly uploaded documents to user-specific docs folder

    Parameters:
    - username (str): Current logged-in user
    - uploaded_docs (list): Files uploaded through Streamlit uploader
    - existing_docs (list): Filenames already in user's docs folder

    Returns:
    - List of newly saved filenames
    """

    # Get user-specific directories
    dirs = ensure_user_dirs(username)
    docs_dir = dirs['docs']

    # Filter out already existing files by name
    new_files = [doc for doc in uploaded_docs if doc.name not in existing_docs]
    new_file_names = [doc.name for doc in new_files]

    if new_files and st.button("Process"):
        for doc in new_files:
            file_path = os.path.join(docs_dir, doc.name)
            try:
                with open(file_path, "wb") as f:
                    f.write(doc.getvalue())
                st.success(f"✅ Saved for {username}: {doc.name}")
            except Exception as e:
                st.error(f"❌ Failed to save {doc.name}: {e}")
                continue

        return new_file_names

    return []


def get_user_documents(username: str):
    """Get list of documents for specific user"""
    dirs = get_user_dirs(username)
    docs_dir = dirs['docs']

    if os.path.exists(docs_dir):
        filenames = os.listdir(docs_dir)
        if "images" in filenames:
            filenames.remove("images")  # Exclude images directory
        return filenames
    return []


def delete_user_document(username: str, filename: str):
    """Delete specific document for user and update cache"""
    from .prepare_vectordb import get_user_dirs, get_vectorstore_user

    dirs = get_user_dirs(username)
    file_path = os.path.join(dirs['docs'], filename)
    cache_path = os.path.join(dirs['vectordb'], "files.txt")

    if not os.path.exists(file_path):
        return False

    # 1) Delete physical file
    os.remove(file_path)

    # 2) Delete image folder
    img_dir = os.path.join(dirs['docs'], "images", filename)
    if os.path.exists(img_dir):
        shutil.rmtree(img_dir)

    # 3) Remove vectors tied to this file using stored IDs
    vectordb = get_vectorstore_user(username)
    ids_to_delete = []
    remaining_lines = []

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                if "\\" in raw:
                    fname, ids_part = raw.split("\\", 1)
                    ids = [i for i in ids_part.split("/") if i]
                else:
                    fname, ids = raw, []

                if fname == filename:
                    ids_to_delete = ids
                    continue  # skip writing this entry back
                remaining_lines.append(raw)

        with open(cache_path, "w", encoding="utf-8") as f:
            for line in remaining_lines:
                f.write(line + "\n")

    if ids_to_delete:
        vectordb.delete(ids=ids_to_delete)
        vectordb.persist()

    st.success(f"🗑️ Deleted {filename} for user {username}")
    return True


def add_resolved_incident_to_vectordb(
    username: str,
    incident: Incident,
) -> str:
    """Add resolved incident details to user's vectorstore"""
    _ = ensure_user_dirs(username)

    content = "\n\n".join([
        f"Incident Name: {incident.name}",
        f"Description: {incident.description}",
        f"Solution: {incident.solution}",
    ])
    incident_id = f"incident_{incident.id}"
    doc = Document(
        page_content=content,
        metadata={
            "source": incident_id,
            "filename": incident_id
        }
    )

    vectordb = get_vectorstore_user(username)
    vectordb.add_documents([doc], ids=[incident_id])
    vectordb.persist()

    st.success(f"✅ Added resolved incident '{incident.name}' to vectorstore for user: {username}")
    return incident_id


def delete_incident_from_vectordb(
    username: str,
    incident_id: str,
) -> None:
    """Delete incident document from user's vectorstore"""
    vectordb = get_vectorstore_user(username)

    if not incident_id.startswith("incident_"):
        incident_id = f"incident_{incident_id}"

    vectordb.delete(ids=[incident_id])
    vectordb.persist()
