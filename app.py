import streamlit as st
import sqlite3
import json
from datetime import datetime
from anthropic import Anthropic
import pandas as pd

st.set_page_config(page_title="Claude 3.7 Sonnet Chat", layout="wide")

# Simple token counting function
def num_tokens_from_messages(messages):
    """Return an approximate number of tokens used by a list of messages."""
    # Simple approximation: 1 token ≈ 4 characters for English text
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # message overhead
        for key, value in message.items():
            # Approximate token count by character count
            num_tokens += len(str(value)) // 4
    return num_tokens

def manage_context_window(messages, max_input_tokens=150000):
    """Ensure messages don't exceed token limit, trimming oldest if needed."""
    current_tokens = num_tokens_from_messages(messages)
    
    while current_tokens > max_input_tokens and len(messages) > 1:
        # Remove the oldest message (but keep system prompt if it's first)
        if messages[0].get("role") == "system" and len(messages) > 2:
            removed = messages.pop(1)  # Remove second message (first non-system)
        else:
            removed = messages.pop(0)  # Remove oldest message
            
        # Recalculate token count
        current_tokens = num_tokens_from_messages(messages)
    
    return messages

def save_conversation(messages, db_path="conversations.db", title=None):
    """Save the current conversation to SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY,
        title TEXT,
        summary TEXT,
        messages TEXT,
        timestamp TEXT,
        token_count INTEGER
    )''')
    
    # Generate title if not provided
    if not title:
        # Use first few words of first non-system message
        for msg in messages:
            if msg.get("role") != "system":
                content = msg.get("content", "")
                title = content[:50] + "..." if len(content) > 50 else content
                break
    
    # Calculate summary (first user message + last assistant message)
    summary = ""
    first_user_msg = next((msg.get("content", "") for msg in messages if msg.get("role") == "user"), "")
    last_assistant_msg = next((msg.get("content", "") for msg in reversed(messages) if msg.get("role") == "assistant"), "")
    summary = f"{first_user_msg[:100]}... → {last_assistant_msg[:100]}..."
    
    # Save conversation
    cursor.execute(
        "INSERT INTO conversations (title, summary, messages, timestamp, token_count) VALUES (?, ?, ?, ?, ?)",
        (title, summary, json.dumps(messages), datetime.now().isoformat(), num_tokens_from_messages(messages))
    )
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def get_conversation_list(db_path="conversations.db"):
    """Get list of all saved conversations."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, summary, timestamp, token_count FROM conversations ORDER BY timestamp DESC")
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def load_conversation(conversation_id, db_path="conversations.db"):
    """Load a specific conversation by ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT messages FROM conversations WHERE id = ?", (conversation_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return json.loads(result[0])
    return []

def render_conversation_sidebar():
    with st.sidebar:
        st.header("Conversation Management")
        
        # Save current conversation button
        if st.button("Save Current Conversation"):
            if "messages" in st.session_state and len(st.session_state.messages) > 1:
                title = st.text_input("Conversation title:", 
                                     value=f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                conversation_id = save_conversation(st.session_state.messages, title=title)
                st.success(f"Conversation saved with ID: {conversation_id}")
        
        # Start new conversation button
        if st.button("Start New Conversation"):
            # Save current conversation first
            if "messages" in st.session_state and len(st.session_state.messages) > 1:
                save_conversation(st.session_state.messages)
            
            # Clear session state except for system messages
            if "messages" in st.session_state:
                system_messages = [msg for msg in st.session_state.messages if msg["role"] == "system"]
                st.session_state.messages = system_messages
                st.experimental_rerun()
        
        # Show saved conversations
        st.subheader("Saved Conversations")
        conversations = get_conversation_list()
        for conv_id, title, summary, timestamp, token_count in conversations:
            with st.expander(f"{title} ({timestamp[:10]})"):
                st.write(f"Summary: {summary}")
                st.write(f"Tokens: {token_count}")
                if st.button(f"Load conversation #{conv_id}", key=f"load_{conv_id}"):
                    st.session_state.messages = load_conversation(conv_id)
                    st.experimental_rerun()

def main():
    st.title("Claude 3.7 Sonnet Chat")
    
    # Initialize the Anthropic client with API key from Streamlit secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    
    # Initialize messages in session state if not already present
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "You are Claude, a helpful AI assistant created by Anthropic. You are friendly, respectful, and you want to be as useful as possible."}
        ]
    
    # Add conversation management
    render_conversation_sidebar()
    
    # Auto-save every 10 messages
    if "messages" in st.session_state and len(st.session_state.messages) % 10 == 0 and len(st.session_state.messages) > 1:
        save_conversation(st.session_state.messages, 
                        title=f"Auto-saved {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Apply token window management before sending to API
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        st.session_state.messages = manage_context_window(st.session_state.messages)
    
    # Display chat messages
    for message in st.session_state.messages:
        if message["role"] != "system":  # Don't display system messages
            with st.chat_message(message["role"]):
                st.write(message["content"])
    
    # Chat input for user
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get Claude's response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = client.messages.create(
                    model="claude-3-7-sonnet-20240320",
                    max_tokens=4000,
                    messages=st.session_state.messages
                )
                assistant_response = response.content[0].text
                
                # Display the response
                st.write(assistant_response)
        
        # Add Claude's response to chat history
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

if __name__ == "__main__":
    main()
