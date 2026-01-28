# utils/chatbot.py

import os
import streamlit as st
from dotenv import load_dotenv
from typing import List

# from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from utils.db_crud import log_chat_message, get_user_last_n_messages


def get_context_retriever_chain(vectordb, callbacks=None):
    """
    Create a context retriever chain for generating responses using ChatGPT-4o-mini.
    """
    load_dotenv()

    # Use OpenAI's GPT-4o-mini via LangChain wrapper
    # llm = ChatOpenAI(
    #     model="gpt-4o-mini",
    #     temperature=0.1,
    #     streaming=callbacks is not None,
    #     callbacks=callbacks,
    #     openai_api_key=st.secrets["OPENAI_API_KEY"]
    # )

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GENERATIVE_AI_MODEL"),
        temperature=0.1,
        streaming=True,
        google_api_key=os.getenv('GOOGLE_API_KEY')
    )

    retriever = vectordb.as_retriever()

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a chatbot. You'll receive a prompt that includes a chat history and retrieved content from the vectorDB based on the user's question. Your task is to respond to the user's question using the information from the vectordb, relying as little as possible on your own knowledge. If for some reason you don't know the answer for the question, or the question cannot be answered because there's no context, ask the user for more details. Do not invent an answer, or mention about the knowledge base. Answer the questions from this context: {context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    chain = create_stuff_documents_chain(llm=llm, prompt=prompt)
    retrieval_chain = create_retrieval_chain(retriever, chain)
    return retrieval_chain

def get_response(question, chat_history, vectordb):
    """
    Generate a response using GPT-4o-mini based on the user question and retrieved context.
    """
    chain = get_context_retriever_chain(vectordb)
    response = chain.invoke({"input": question, "chat_history": chat_history})
    
    # Fix key access for documents
    return response.get("answer") or response.get("result"), response.get("context") or response.get("source_documents")

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

def chat(chat_history, vectordb, username: str = None):
    """
    Main Streamlit chat interface using GPT-4o-mini and vector context.
    """
    user_query = st.chat_input("Ask a question:")

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

    # Display chat messages
    for message in chat_history:
        role = "AI" if isinstance(message, AIMessage) else "Human"
        with st.chat_message(role):
            st.write(message.content)

    if user_query:
        # Show user's message immediately
        with st.chat_message("Human"):
            st.write(user_query)

        # Setup LLM
        # llm = ChatOpenAI(
        #     model="gpt-4o-mini",
        #     temperature=0.1,
        #     streaming=True
        #     # openai_api_key=st.secrets["OPENAI_API_KEY"]  # Remove for now, fix separately
        # )
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GENERATIVE_AI_MODEL"),
            temperature=0.1,
            streaming=True,
            google_api_key=os.getenv('GOOGLE_API_KEY')
        )

        retriever = vectordb.as_retriever()

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a chatbot. You'll receive a prompt that includes a chat history and retrieved content from the vectorDB based on the user's question. Your task is to respond to the user's question using the information from the vectordb, relying as little as possible on your own knowledge. If for some reason you don't know the answer for the question, or the question cannot be answered because there's no context, ask the user for more details. Do not invent an answer, or mention about the knowledge base. Answer the questions from this context: {context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        chain = create_stuff_documents_chain(llm=llm, prompt=prompt)
        retrieval_chain = create_retrieval_chain(retriever, chain)

        # Create a new AI chat bubble and stream the response
        final_response = ""
        with st.chat_message("AI"):
            def stream_response():
                nonlocal final_response
                for chunk in retrieval_chain.stream({
                    "input": user_query,
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
                message=user_query
            )
            # Save AI response to database
            log_chat_message(
                username=username,
                is_human=False,
                message=final_response
            )
        
        # Update chat_history with both user and AI messages
        chat_history = chat_history + [
            HumanMessage(content=user_query),
            AIMessage(content=final_response)
        ]

    return chat_history