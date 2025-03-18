# Replace the existing tiktoken import and token counting functions with these:

# import tiktoken  <- REMOVE THIS LINE
import sqlite3
import json
from datetime import datetime

def num_tokens_from_messages(messages, model="claude-3-opus-20240229"):
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
    
    return messages# Add these functions at the TOP of your existing app.py

def num_tokens_from_messages(messages, model="claude-3-opus-20240229"):
    """Return the number of tokens used by a list of messages."""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # Close enough for Claude
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(str(value)))
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

# ADD THIS FUNCTION in your app.py (not in main)
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
