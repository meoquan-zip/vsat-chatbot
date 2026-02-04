import json
import os
import re
from typing import List

import streamlit as st
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .db_crud import get_user_last_n_messages, log_chat_message
from .db_orm import Incident


def load_chat_history_from_db(username: str) -> List[dict]:
    """
    Load chat history from database for UI rendering and LLM context.
    Each entry: {role: "human"|"ai", content: str, images: [{name, path, source}]}.
    """
    db_messages = get_user_last_n_messages(username)
    chat_history: List[dict] = []

    for msg in db_messages:
        images = []
        if msg.images_json:
            try:
                images = json.loads(msg.images_json)
            except Exception:
                images = []

        chat_history.append({
            "role": "human" if msg.is_human else "ai",
            "content": msg.message,
            "images": images,
        })

    return chat_history


def chat_user_prompt(chat_history: List,
                     vectordb,
                     username: str) -> List:
    """
    Display chat input box and handle user prompt for chatbot interaction.
    """
    user_prompt = st.chat_input("Ask a question:")

    return _chat_response_streaming(
        prompt=user_prompt,
        chat_history=chat_history,
        vectordb=vectordb,
        username=username
    )


def chat_incident_prompt(incident: Incident,
                         chat_history: List,
                         vectordb,
                         username: str) -> List:
    prompt = (
        f"I have an incident that needs troubleshooting help:\n\n"
        f"Name: {incident.name}\n\n"
        f"Description: {incident.description}\n\n"
        f"Logs: {incident.log or 'N/A'}\n\n"
        f"SLA time (minutes): {incident.sla_no_of_hours}"  # leave as minutes for testing purposes
    )
    return _chat_response_streaming(
        prompt=prompt,
        chat_history=chat_history,
        vectordb=vectordb,
        username=username
    )


def _chat_response_streaming(prompt: str,
                             chat_history: List,
                             vectordb,
                             username: str = None,
                             system_instruction: str = None) -> List:
    """
    Generate chatbot response with streaming.
    """
    IMAGE_WIDTH = "content"  # "content", "stretch", or int pixel value
    def _render_message(entry: dict):
        role_label = "AI" if entry.get("role") == "ai" else "Human"
        content = entry.get("content", "")
        images = entry.get("images") or []
        placeholder_names = re.findall(r"\[IMAGE:([^\]]+)\]", content)
        lookup = {img.get("name"): img for img in images if img.get("name")}

        with st.chat_message(role_label):
            st.markdown(content)
            shown = set()
            for name in placeholder_names:
                if name in shown:
                    continue
                meta = lookup.get(name)
                if not meta:
                    continue
                caption_parts = [meta.get("source"), name]
                caption = " - ".join([p for p in caption_parts if p])
                st.image(
                    image=meta.get("path"),
                    caption=caption or None,
                    width=IMAGE_WIDTH,
                )
                shown.add(name)

    # Display chat messages
    for entry in chat_history:
        _render_message(entry)

    # Convert to LangChain messages for the model
    lc_chat_history = []
    for entry in chat_history:
        if entry.get("role") == "human":
            lc_chat_history.append(HumanMessage(content=entry.get("content", "")))
        else:
            lc_chat_history.append(AIMessage(content=entry.get("content", "")))

    if not prompt:
        return chat_history
    
    # Show user's message immediately
    with st.chat_message("Human"):
        st.write(prompt)

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GENERATIVE_AI_MODEL"),
        temperature=0.1,
        streaming=True,
        google_api_key=os.getenv('GOOGLE_API_KEY')
    )

    retriever = vectordb.as_retriever()

    system_instruction = system_instruction or (
        "You are an internal RAG-based AI assistant for a technical support and incident management system. "
        "You will receive a user query together with: "
        "(1) the ongoing chat history, and "
        "(2) relevant context retrieved from the system's knowledge base (vector database). "

        "Your job is to provide accurate and helpful answers strictly based on the retrieved context. "
        "Use the chat history only to maintain continuity and better understand the user's intent. "

        "The user query may come from two sources: "
        "- a manually typed question, or "
        "- an automatically generated prompt related to an unresolved incident (status = 'open'), "
        "which may include incident name, description, logs, SLA information, or other details. "

        "When the query is incident-related, treat it as a request for troubleshooting guidance or resolution suggestions. "
        "Provide actionable steps, possible causes, and recommendations grounded in the retrieved knowledge. "

        "Images inside the retrieved context are represented by placeholders like [IMAGE:image_3.png]. "
        "If an image is part of a step or helps clarity, keep the placeholder in the answer exactly where it belongs. "
        "Do not invent new image names. Only use placeholders that already appear in the provided context. "

        "Do not invent facts or solutions that are not supported by the provided context. "
        "If the retrieved information is insufficient or unclear, ask the user for more details "
        "(for example: additional logs, environment conditions, error messages, or incident updates). "

        "Do not mention the existence of the knowledge base, embeddings, or vector search. "
        "Simply answer naturally as a technical assistant. "

        "After answering, append a short 'Sources:' section listing only the document filenames (no paths, no image paths). "
        "If no sources are available, state 'Sources: none'. "

        "Answer using only the following context:\n\n{context}"
    )
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])
    doc_prompt = PromptTemplate.from_template(
        "Source: {filename}\nImages available: {img_list}\nContent:\n{page_content}"
    )

    chain = create_stuff_documents_chain(
        llm=llm,
        prompt=rag_prompt,
        document_prompt=doc_prompt,
    )
    retrieval_chain = create_retrieval_chain(retriever, chain)

    # Pre-fetch docs to build image lookup (docx images) and surface filenames
    retrieved_docs = retriever.get_relevant_documents(prompt)
    image_lookup = {}
    for doc in retrieved_docs:
        meta = doc.metadata or {}
        filename = meta.get("filename") or os.path.basename(str(meta.get("source", "")))
        img_paths_json = meta.get("img_paths_json")
        if not img_paths_json:
            continue
        try:
            img_map = json.loads(img_paths_json)
        except Exception:
            continue
        for name, path in img_map.items():
            if name not in image_lookup:
                image_lookup[name] = {
                    "path": path,
                    "source": filename,
                }

    # Create a new AI chat bubble and stream the response
    final_response = ""
    with st.chat_message("AI"):
        def stream_response():
            nonlocal final_response
            for chunk in retrieval_chain.stream({
                "input": prompt,
                "chat_history": lc_chat_history
            }):
                content = ""
                if isinstance(chunk, dict):
                    content = chunk.get("answer") or chunk.get("result") or ""
                elif isinstance(chunk, ChatGenerationChunk):
                    content = chunk.text
                final_response += content
                yield content
        st.write_stream(stream_response)

        # Render images referenced in the final response, if available
        placeholder_names = re.findall(r"\[IMAGE:([^\]]+)\]", final_response)
        used_images = []
        shown = set()
        for name in placeholder_names:
            if name in shown:
                continue
            meta = image_lookup.get(name)
            if not meta:
                continue
            caption_parts = [meta.get("source"), name]
            caption = " — ".join([p for p in caption_parts if p])
            st.image(
                image=meta.get("path"),
                caption=caption or None,
                width=IMAGE_WIDTH,
            )
            used_images.append({"name": name, **meta})
            shown.add(name)

    if username:
        # Save user message to database
        log_chat_message(
            username=username,
            is_human=True,
            message=prompt,
        )
        # Save AI response to database with image metadata
        images_json = json.dumps(used_images) if used_images else None
        log_chat_message(
            username=username,
            is_human=False,
            message=final_response,
            images_json=images_json,
        )
    
    # Update chat_history with both user and AI messages (include images for rendering)
    chat_history = chat_history + [
        {
            "role": "human",
            "content": prompt,
            "images": [],
        },
        {
            "role": "ai",
            "content": final_response,
            "images": used_images,
        }
    ]

    return chat_history
