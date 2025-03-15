import streamlit as st
import os
import uuid
from datetime import datetime
import sqlite3
import json
import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

# Database functions
def get_db_connection():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect('data/conversations.db')
    conn.row_factory = sqlite3.Row
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        model TEXT
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
    )
    ''')
    
    conn.commit()
    return conn

def save_conversation(conversation_id, messages, title=None):
    conn = get_db_connection()
    now = datetime.now().isoformat()
    
    existing = conn.execute(
        "SELECT * FROM conversations WHERE conversation_id = ?", 
        (conversation_id,)
    ).fetchone()
    
    if not existing:
        if not title:
            first_message = messages[0]["content"] if messages else "New Conversation"
            title = first_message[:50] + "..." if len(first_message) > 50 else first_message
            
        conn.execute(
            "INSERT INTO conversations (conversation_id, title, created_at, updated_at, model) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, title, now, now, "Claude 3.7 Sonnet")
        )
    else:
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            (now, conversation_id)
        )
    
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    
    for msg in messages:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, msg["role"], msg["content"], now)
        )
    
    conn.commit()
    conn.close()

def get_conversations():
    conn = get_db_connection()
    conversations = conn.execute(
        "SELECT * FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(c) for c in conversations]

def get_messages(conversation_id):
    conn = get_db_connection()
    messages = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY message_id",
        (conversation_id,)
    ).fetchall()
    conn.close()
    return [dict(m) for m in messages]

def search_conversations(query):
    conn = get_db_connection()
    
    results = conn.execute(
        """
        SELECT c.conversation_id, c.title, c.updated_at, m.content
        FROM conversations c
        JOIN messages m ON c.conversation_id = m.conversation_id
        WHERE m.content LIKE ?
        GROUP BY c.conversation_id
        ORDER BY c.updated_at DESC
        """,
        (f"%{query}%",)
    ).fetchall()
    
    conn.close()
    return [dict(r) for r in results]

# Main app
st.set_page_config(page_title="Claude 3.7 Chat", layout="wide")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Chat", "History", "Search"])

# Get API Key
api_key = st.secrets["ANTHROPIC_API_KEY"]

# Initialize chat model
if "llm" not in st.session_state:
    st.session_state.llm = ChatAnthropic(
        anthropic_api_key=api_key,
        model="claude-3-7-sonnet-20250219",
        temperature=0.7,
        max_tokens=100000  # Using a much higher token limit for context windows
    )

# Set up conversation
if "conversation" not in st.session_state:
    try:
        memory = ConversationBufferMemory()
        st.session_state.conversation = ConversationChain(
            llm=st.session_state.llm, 
            memory=memory,
            verbose=True  # Add this for debugging
        )
    except Exception as e:
        st.error(f"Error initializing conversation: {str(e)}")
# Initialize state
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
    
if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat page
if page == "Chat":
    st.title("Claude 3.7 Chat")
    
    # New chat button
    if st.button("New Chat"):
        if st.session_state.messages:
            save_conversation(st.session_state.conversation_id, st.session_state.messages)
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.conversation = ConversationChain(
            llm=st.session_state.llm, 
            memory=ConversationBufferMemory()
        )
        st.rerun()
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
# Chat input
prompt = st.chat_input("Ask something...")
if prompt:
    # Display user message
    st.session_state.messages.append({"role": "human", "content": prompt})
    with st.chat_message("human"):
        st.write(prompt)
    
    # Get and display AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.conversation.predict(input=prompt)
                st.write(response)
                # Save AI message
                st.session_state.messages.append({"role": "assistant", "content": response})
                # Auto-save
                save_conversation(st.session_state.conversation_id, st.session_state.messages)
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)

# History page
elif page == "History":
    st.title("Conversation History")
    
    conversations = get_conversations()
    
    if not conversations:
        st.info("No saved conversations yet.")
    else:
        # Display conversations
        for conv in conversations:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{conv['title']}**")
                st.write(f"Last updated: {conv['updated_at']}")
            with col2:
                if st.button("Load", key=f"load_{conv['conversation_id']}"):
                    # Load conversation
                    loaded_messages = get_messages(conv['conversation_id'])
                    formatted_messages = [
                        {"role": msg["role"], "content": msg["content"]} 
                        for msg in loaded_messages
                    ]
                    
                    # Update state
                    st.session_state.conversation_id = conv['conversation_id']
                    st.session_state.messages = formatted_messages
                    st.session_state.conversation = ConversationChain(
                        llm=st.session_state.llm, 
                        memory=ConversationBufferMemory()
                    )
                    
                    # Go to chat page
                    st.session_state.page = "Chat"
                    st.rerun()
            st.divider()

# Search page
elif page == "Search":
    st.title("Search Conversations")
    
    query = st.text_input("Search for keywords:")
    
    if query:
        results = search_conversations(query)
        
        if not results:
            st.info(f"No results found for '{query}'")
        else:
            st.success(f"Found {len(results)} results")
            
            for result in results:
                with st.expander(f"{result['title']} - {result['updated_at']}"):
                    st.write(f"**Content:** {result['content']}")
                    if st.button("Load", key=f"load_search_{result['conversation_id']}"):
                        # Load conversation
                        loaded_messages = get_messages(result['conversation_id'])
                        formatted_messages = [
                            {"role": msg["role"], "content": msg["content"]} 
                            for msg in loaded_messages
                        ]
                        
                        # Update state
                        st.session_state.conversation_id = result['conversation_id']
                        st.session_state.messages = formatted_messages
                        st.session_state.conversation = ConversationChain(
                            llm=st.session_state.llm, 
                            memory=ConversationBufferMemory()
                        )
                        
                        # Go to chat page
                        st.session_state.page = "Chat"
                        st.rerun()

# Auto-save info
st.sidebar.markdown("---")
st.sidebar.info("💾 Your conversations are automatically saved.")
