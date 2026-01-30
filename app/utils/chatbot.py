import os
from typing import List

import streamlit as st
from dotenv import load_dotenv
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI

from .db_crud import get_user_last_n_messages, log_chat_message

# def get_context_retriever_chain(vectordb, callbacks=None):
#     """
#     Create a context retriever chain for generating responses using ChatGPT-4o-mini.
#     """
#     load_dotenv()

#     # Use OpenAI's GPT-4o-mini via LangChain wrapper
#     # llm = ChatOpenAI(
#     #     model="gpt-4o-mini",
#     #     temperature=0.1,
#     #     streaming=callbacks is not None,
#     #     callbacks=callbacks,
#     #     openai_api_key=st.secrets["OPENAI_API_KEY"]
#     # )

#     llm = ChatGoogleGenerativeAI(
#         model=os.getenv("GENERATIVE_AI_MODEL"),
#         temperature=0.1,
#         streaming=True,
#         google_api_key=os.getenv('GOOGLE_API_KEY')
#     )

#     retriever = vectordb.as_retriever()

#     system_instruction = (
#         "You are a chatbot. You'll receive a prompt that includes a chat "
#         "history and retrieved content from the vector DB based on the "
#         "user's question. Your task is to respond to the user's question "
#         "using the information from the vector DB, relying as little as "
#         "possible on your own knowledge. If for some reason you don't "
#         "know the answer for the question, or the question cannot be "
#         "answered because there's no context, ask the user for more "
#         "details. Do not invent an answer, or mention about the knowledge "
#         "base. Answer the questions from this context: {context}"
#     )
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_instruction),
#         MessagesPlaceholder(variable_name="chat_history"),
#         ("human", "{input}")
#     ])

#     chain = create_stuff_documents_chain(llm=llm, prompt=prompt)
#     retrieval_chain = create_retrieval_chain(retriever, chain)
#     return retrieval_chain

# def get_response(question, chat_history, vectordb):
#     """
#     Generate a response using GPT-4o-mini based on the user question and retrieved context.
#     """
#     chain = get_context_retriever_chain(vectordb)
#     response = chain.invoke({"input": question, "chat_history": chat_history})
    
#     # Fix key access for documents
#     return response.get("answer") or response.get("result"), response.get("context") or response.get("source_documents")


def load_chat_history_from_db(username: str) -> List:
    """
    Load chat history from database and convert to LangChain message objects.
    """
    db_messages = get_user_last_n_messages(username)
    chat_history = []
    
    for msg in db_messages:
        if msg.is_human:
            chat_history.append(HumanMessage(content=msg.message))
        else:
            chat_history.append(AIMessage(content=msg.message))
    
    return chat_history


def chat_user_prompt(chat_history: List,
                     vectordb,
                     username: str) -> List:
    """
    Display chat input box and handle user prompt for chatbot interaction.
    """
    user_prompt = st.chat_input("Ask a question:")

        # # Show sources in sidebar, robustly handling missing 'page'
        # with st.sidebar:
        #     metadata_dict = defaultdict(list)
        #     if context:
        #         for doc in context:
        #             meta = doc.metadata
        #             src = meta.get('source', 'unknown source')
        #             pg  = meta.get('page')
        #             # only record pages if present and truthy
        #             if pg is not None:
        #                 metadata_dict[src].append(pg)
        #         if metadata_dict:
        #             for source, pages in metadata_dict.items():
        #                 st.write(f"**Source:** {source}")
        #                 st.write(f"Pages: {', '.join(map(str, pages))}")
        #         else:
        #             st.write("No page metadata available for these sources.")
        #     else:
        #         st.write("No context found for this answer.")
    return _chat_response_streaming(
        prompt=user_prompt,
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
    # Display chat messages
    for message in chat_history:
        role = "AI" if isinstance(message, AIMessage) else "Human"
        with st.chat_message(role):
            st.write(message.content)

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

        "Do not invent facts or solutions that are not supported by the provided context. "
        "If the retrieved information is insufficient or unclear, ask the user for more details "
        "(for example: additional logs, environment conditions, error messages, or incident updates). "

        "Do not mention the existence of the knowledge base, embeddings, or vector search. "
        "Simply answer naturally as a technical assistant. "

        "Answer using only the following context:\n\n{context}"
    )
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    chain = create_stuff_documents_chain(llm=llm, prompt=rag_prompt)
    retrieval_chain = create_retrieval_chain(retriever, chain)

    # Create a new AI chat bubble and stream the response
    final_response = ""
    with st.chat_message("AI"):
        def stream_response():
            nonlocal final_response
            for chunk in retrieval_chain.stream({
                "input": prompt,
                "chat_history": chat_history
            }):
                content = ""
                if isinstance(chunk, dict):
                    content = chunk.get("answer") or chunk.get("result") or ""
                elif isinstance(chunk, ChatGenerationChunk):
                    content = chunk.text
                final_response += content
                yield content
        st.write_stream(stream_response)

    if username:
        # Save user message to database
        log_chat_message(
            username=username,
            is_human=True,
            message=prompt
        )
        # Save AI response to database
        log_chat_message(
            username=username,
            is_human=False,
            message=final_response
        )
    
    # Update chat_history with both user and AI messages
    chat_history = chat_history + [
        HumanMessage(content=prompt),
        AIMessage(content=final_response)
    ]

    return chat_history
