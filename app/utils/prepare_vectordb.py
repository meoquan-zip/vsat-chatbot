# utils/prepare_vectordb.py

import nest_asyncio
nest_asyncio.apply()

import os
import shutil
from typing import List
import streamlit as st
import hashlib
import pandas as pd
import re
import fitz  # PyMuPDF for PDF image extraction
from paddleocr import PaddleOCR

from dotenv import load_dotenv
import chromadb
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredWordDocumentLoader
)
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.embeddings import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document

from utils.db_orm import Incident

# --- Constants ---
DEFAULT_DOCS_DIR    = "docs"
DEFAULT_PERSIST_DIR = "Vector_DB - Documents"
DEFAULT_CHUNKS_DIR  = "chunks"
CHUNK_SIZE          = 8000
CHUNK_OVERLAP       = 800

# Load your .env (must contain OPENAI_API_KEY)
load_dotenv()

def has_new_files(persist_dir: str, current_files: List[str]) -> bool:
    cache_path = os.path.join(persist_dir, "files.txt")
    if not os.path.exists(cache_path):
        return True
    with open(cache_path, "r", encoding="utf-8") as f:
        cached_files = set(line.strip() for line in f.readlines())
    return set(current_files) != cached_files

def is_gibberish(text, threshold=0.3):
    if not text:
        return True
    alnum = sum(c.isalnum() for c in text)
    ratio = alnum / max(len(text), 1)
    return ratio < threshold

def ocr_pdf_with_paddleocr(pdf_path, lang='vi'):  # Vietnamese support
    ocr = PaddleOCR(lang=lang, use_angle_cls=True, show_log=False)
    doc = fitz.open(pdf_path)
    all_text = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        images = page.get_images(full=True)
        page_text = []
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            import numpy as np
            import cv2
            img_array = np.frombuffer(image_bytes, np.uint8)
            img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_cv is not None:
                result = ocr.ocr(img_cv, cls=True)
                for line in result:
                    for box in line:
                        text = box[1][0]
                        page_text.append(text)
        # If no images, try to render the page as an image and OCR it
        if not images:
            pix = page.get_pixmap()
            img_cv = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            result = ocr.ocr(img_cv, cls=True)
            for line in result:
                for box in line:
                    text = box[1][0]
                    page_text.append(text)
        if page_text:
            all_text.append(f"Page {page_num+1}:\n" + "\n".join(page_text))
    doc.close()
    if all_text:
        return [Document(page_content="\n\n".join(all_text), metadata={"source": pdf_path})]
    return []


def load_text_from_txt_file(filepath):
    encodings = ['utf-8', 'utf-16', 'cp1252', 'iso-8859-1', 'gbk']
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            return [Document(page_content=content, metadata={"source": filepath})]
        except (UnicodeDecodeError, LookupError):
            continue

    st.error(f"Cannot decode text file: {filepath}")
    return []


def extract_text(file_list: List[str], docs_dir: str = DEFAULT_DOCS_DIR):
    docs = []
    for fn in file_list:
        path = os.path.join(docs_dir, fn)
        try:
            if fn.lower().endswith(".pdf"):
                loaded = PyPDFLoader(path).load()
                all_text = " ".join(doc.page_content for doc in loaded)
                if not loaded or is_gibberish(all_text):
                    st.warning(f"⚠️ Falling back to PaddleOCR for: {fn}")
                    try:
                        ocr_loaded = ocr_pdf_with_paddleocr(path, lang='vi')
                        docs.extend(ocr_loaded)
                    except Exception as ocr_e:
                        continue
                else:
                    docs.extend(loaded)
            elif fn.lower().endswith(".txt"):
                docs.extend(load_text_from_txt_file(path))
            elif fn.lower().endswith(".docx"):
                docs.extend(Docx2txtLoader(path).load())
            elif fn.lower().endswith(".doc"):
                docs.extend(UnstructuredWordDocumentLoader(path).load())
            elif fn.lower().endswith(".xls") or fn.lower().endswith(".xlsx"):
                # Excel support for both .xls and .xlsx, with engine selection
                try:
                    if fn.lower().endswith(".xls"):
                        df = pd.read_excel(path, sheet_name=None, engine="xlrd")
                    else:
                        df = pd.read_excel(path, sheet_name=None, engine="openpyxl")
                except Exception as e:
                    # Fallback to default engine if specified engine fails
                    try:
                        df = pd.read_excel(path, sheet_name=None)
                    except Exception as e2:
                        st.error(f"❌ Failed to read Excel file {fn}: {e2}")
                        continue
                text = ""
                for sheet, data in df.items():
                    text += f"Sheet: {sheet}\n"
                    text += data.to_string(index=False)
                    text += "\n\n"
                if text.strip():
                    docs.append(Document(page_content=text, metadata={"source": path}))
            else:
                st.warning(f"⚠️ Unsupported file type: {fn}")
        except Exception as e:
            st.error(f"❌ Failed to process {fn}: {e}")
    return docs

def get_text_chunks(
    docs,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP
):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_documents(docs)

def save_text_chunks(
    chunks,
    chunks_dir: str = DEFAULT_CHUNKS_DIR,
    overwrite: bool = True
) -> None:
    if overwrite and os.path.isdir(chunks_dir):
        shutil.rmtree(chunks_dir)
    os.makedirs(chunks_dir, exist_ok=True)

    for i, chunk in enumerate(chunks):
        src = chunk.metadata.get("source", "")
        base = os.path.splitext(os.path.basename(src))[0] if src else "doc"
        fname = f"{base}_chunk_{i:04d}.txt"
        path = os.path.join(chunks_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(chunk.page_content)

    print(f"✅ Exported {len(chunks)} chunks to '{chunks_dir}/'")
    
def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_vectorstore(
    file_list: List[str],
    docs_dir: str = DEFAULT_DOCS_DIR,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    chunks_dir: str = DEFAULT_CHUNKS_DIR
) -> Chroma:
    """
    Incrementally update a Chroma vectorstore by embedding only new files.
    """
    # embedding = OpenAIEmbeddings(
    #     model="text-embedding-3-large",
    #     openai_api_key=st.secrets["OPENAI_API_KEY"]
    # )
    embedding = GoogleGenerativeAIEmbeddings(
        model="text-embedding-004",
        google_api_key=os.getenv('GOOGLE_API_KEY')
    )

    # Load or create vectorstore
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embedding
    )

    # Load previously embedded file list
    cache_path = os.path.join(persist_dir, "files.txt")
    prev_files = set()
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            prev_files = set(line.strip() for line in f)

    # Filter new files
    new_files = [f for f in file_list if f not in prev_files]
    if not new_files:
        print("✅ No new files to add.")
        return vectordb

    print(f"🆕 New files to process: {new_files}")
    docs = extract_text(new_files, docs_dir)
    chunks = get_text_chunks(docs)

    # Deduplicate by chunk content hash
    seen_hashes = set()
    unique_chunks: List[Document] = []
    for chunk in chunks:
        content_hash = hash_text(chunk.page_content)
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_chunks.append(chunk)

    # Add only unique chunks
    if unique_chunks:
        vectordb.add_documents(unique_chunks)
        vectordb.persist()
        print(f"✅ Added {len(unique_chunks)} unique chunks.")
    else:
        print("⚠️ No unique chunks to embed — skipping update.")

    # Append new files to file cache
    with open(cache_path, "a", encoding="utf-8") as f:
        for fname in new_files:
            f.write(fname + "\n")

    # Save new chunks for inspection
    save_text_chunks(unique_chunks, chunks_dir=chunks_dir, overwrite=False)

    return vectordb


# --- User-specific Constants ---
def get_user_dirs(username: str):
    """Get user-specific directory paths"""
    user_base = f"data/kb/{username}"
    return {
        'docs': f"{user_base}/docs",
        'chunks': f"{user_base}/chunks",
        'vectordb': f"{user_base}/vector_db"
    }

def ensure_user_dirs(username: str):
    """Create user-specific directories"""
    dirs = get_user_dirs(username)
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def has_new_files_user(username: str, current_files: List[str]) -> bool:
    """Check for new files in user's directory"""
    dirs = get_user_dirs(username)
    cache_path = os.path.join(dirs['vectordb'], "files.txt")

    if not os.path.exists(cache_path):
        return True

    with open(cache_path, "r", encoding="utf-8") as f:
        cached_files = set(line.strip() for line in f.readlines())
    return set(current_files) != cached_files

def get_vectorstore_user(
        username: str,
        file_list: List[str] = []
) -> 'Chroma':
    """
    Get user-specific vectorstore
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_community.vectorstores import Chroma

    # Ensure user directories exist
    dirs = ensure_user_dirs(username)

    embedding = GoogleGenerativeAIEmbeddings(
        model=os.getenv('TEXT_EMBEDDING_MODEL'),
        google_api_key=os.getenv('GOOGLE_API_KEY')
    )

    # Load or create user-specific vectorstore
    vectordb = Chroma(
        persist_directory=dirs['vectordb'],
        embedding_function=embedding
    )

    # Load previously embedded file list
    cache_path = os.path.join(dirs['vectordb'], "files.txt")
    prev_files = set()
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            prev_files = set(line.strip() for line in f)

    # Filter new files
    new_files = [f for f in file_list if f not in prev_files]
    if not new_files:
        return vectordb

    st.info(f"🆕 Processing {len(new_files)} new files for user: {username}")

    # Extract text from new files
    docs = extract_text(new_files, dirs['docs'])
    chunks = get_text_chunks(docs)

    # Deduplicate by chunk content hash
    seen_hashes = set()
    unique_chunks = []
    for chunk in chunks:
        content_hash = hash_text(chunk.page_content)
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_chunks.append(chunk)

    # Add only unique chunks
    if unique_chunks:
        # this returns a list of IDs of added documents
        # todo: retrieve and store these IDs so when user deletes a document file,
        #       we can also delete corresponding vectors from the vectordb
        vectordb.add_documents(unique_chunks)
        vectordb.persist()

        # st.success(f"✅ Added {len(unique_chunks)} unique chunks for {username}")

        # Lưu thông báo vào session state thay vì st.success
        st.session_state[f'vectorstore_success_{username}'] = f"✅ Added {len(unique_chunks)} unique chunks for {username}"

    # Update file cache
    with open(cache_path, "a", encoding="utf-8") as f:
        for fname in new_files:
            f.write(fname + "\n")

    # Save chunks for inspection
    save_text_chunks(unique_chunks, chunks_dir=dirs['chunks'], overwrite=False)

    return vectordb

def cleanup_user_data(username: str):
    """Clean up all user data"""
    user_base = f"data/kb/{username}"
    if os.path.exists(user_base):
        shutil.rmtree(user_base)
        st.success(f"🗑️ Cleaned up all data for user: {username}")

# def rebuild_user_vectorstore(username: str):
#     """Rebuild vectorstore from scratch for user"""
#     dirs = get_user_dirs(username)
#
#     # Xóa toàn bộ vectorstore cũ
#     if os.path.exists(dirs['vectordb']):
#         shutil.rmtree(dirs['vectordb'])
#
#     # Tạo lại thư mục
#     os.makedirs(dirs['vectordb'], exist_ok=True)
#
#     # Lấy danh sách file hiện tại và rebuild
#     current_files = get_user_documents(username)
#     if current_files:
#         return get_vectorstore_user(username, current_files)
#
#     return None

def add_resolved_incident_to_vectordb(
    username: str,
    incident: Incident,
) -> str:
    """Add resolved incident details to user's vectorstore"""
    _ = ensure_user_dirs(username)

    # Tạo document từ thông tin incident
    # content = f"""
    #     Incident Name: {incident.name}\n\nDescription: {incident.description}\n\nSolution: {incident.solution}"
    content = "\n\n".join([
        f"Incident Name: {incident.name}",
        f"Description: {incident.description}",
        f"Solution: {incident.solution}",
    ])
    incident_id = f"incident_{incident.id}"
    doc = Document(page_content=content, metadata={"source": incident_id})

    # Lấy vectorstore của user
    vectordb = get_vectorstore_user(username)

    # Thêm document vào vectordb
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
