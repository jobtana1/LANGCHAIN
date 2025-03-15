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

def backup_database():
    """Create a backup of the database file"""
    os.makedirs("backups", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"backups/conversations_backup_{timestamp}.db"
    
    # If database exists, create a backup
    if os.path.exists('data/conversations.db'):
        # Connect to database
        conn = sqlite3.connect('data/conversations.db')
        
        # Create backup
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        
        # Close connections
        backup_conn.close()
        conn.close()
        
        return backup_path
    return None

def export_conversation(conversation_id, format="json"):
    """Export a conversation to a file"""
    conn = get_db_connection()
    
    conversation = conn.execute(
        "SELECT * FROM conversations WHERE conversation_id = ?",
        (conversation_id,)
    ).fetchone()
    
    if not conversation:
        conn.close()
        return None
    
    messages = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY message_id",
        (conversation_id,)
    ).fetchall()
    
    conn.close()
    
    conversation_data = {
        "conversation_id": conversation_id,
        "title": conversation["title"],
        "created_at": conversation["created_at"],
        "updated_at": conversation["updated_at"],
        "model": conversation["model"],
        "messages": [dict(m) for m in messages]
    }
    
    # Create exports directory if it doesn't exist
    os.makedirs("exports", exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_{conversation_id}_{timestamp}"
    
    if format == "json":
        # Export as JSON
        with open(f"exports/{filename}.json", "w") as f:
            json.dump(conversation_data, f, indent=2)
        return f"exports/{filename}.json"
    elif format == "csv":
        # Export as CSV
        df = pd.DataFrame([dict(m) for m in messages])
        df.to_csv(f"exports/{filename}.csv", index=False)
        return f"exports/{filename}.csv"
    else:
        return None

# Context window management
def estimate_tokens(text):
    """Estimate the number of tokens in a text"""
    # Rough estimate: 1 token ≈ 4 characters for English text
    return len(text) // 4

def manage_context_window(messages, max_input_tokens=150000):
    """Manage the context window by trimming messages if needed"""
    # Convert messages to text to estimate tokens
    all_text = " ".join([msg.get("content", "") for msg in messages if isinstance(msg, dict)])
    current_tokens = estimate_tokens(all_text)
    
    # If approaching limit, start trimming older messages
    if current_tokens > max_input_tokens:
        # Keep removing oldest messages until under threshold
        while current_tokens > max_input_tokens and len(messages) > 3:
            # Always keep at least the most recent exchange
            if len(messages) > 3:
                removed = messages.pop(1)  # Remove oldest non-system message
                current_tokens -= estimate_tokens(removed.get("content", ""))
            else:
                break
                
        # If still over limit, add a note
        if current_tokens > max_input_tokens:
            messages.insert(1, {
                "role": "assistant", 
                "content": "[Note: Some earlier messages were removed to fit within context limits.]"
            })
    
    return messages

# Main app
st.set_page_config(page_title="Claude 3.7 Chat", layout="wide")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Chat", "History", "Search", "Backup"])

# Get API Key
api_key = st.secrets["ANTHROPIC_API_KEY"]

# Initialize chat model
if "llm" not in st.session_state:
    st.session_state.llm = ChatAnthropic(
        anthropic_api_key=api_key,
        model="claude-3-7-sonnet-20250219",
        temperature=0.7,
        max_tokens=4000  # Reduced max_tokens to avoid context length errors
    )

# Set up conversation
if "conversation" not in st.session_state:
    try:
        memory = ConversationBufferMemory()
        st.session_state.conversation = ConversationChain(
            llm=st.session_state.llm, 
            memory=memory,
            verbose=True
        )
    except Exception as e:
        st.error(f"Error initializing conversation: {str(e)}")

# Initialize state
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
    
if "messages" not in st.session_state:
    st.session_state.messages = []

# Set last save time for auto-save
if "last_save" not in st.session_state:
    st.session_state.last_save = datetime.now()

# Chat page
if page == "Chat":
    st.title("Claude 3.7 Chat")
    
    # Display conversation ID and controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.caption(f"Conversation ID: {st.session_state.conversation_id}")
    with col2:
        if st.button("New Chat"):
            if st.session_state.messages:
                save_conversation(st.session_state.conversation_id, st.session_state.messages)
            st.session_state.conversation_id = str(uuid.uuid4())
            st.session_state.messages = []
            try:
                st.session_state.conversation = ConversationChain(
                    llm=st.session_state.llm, 
                    memory=ConversationBufferMemory()
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error creating new chat: {str(e)}")
    with col3:
        export_format = st.selectbox("Export as:", ["json", "csv"], key="export_format")
        if st.button("Export"):
            if st.session_state.messages:
                try:
                    export_path = export_conversation(st.session_state.conversation_id, format=export_format)
                    if export_path:
                        st.success(f"Conversation exported to {export_path}")
                    else:
                        st.error("Export failed")
                except Exception as e:
                    st.error(f"Error exporting: {str(e)}")
    
    # Auto-save check
    current_time = datetime.now()
    if (current_time - st.session_state.last_save).total_seconds() > 300:  # 5 minutes
        if st.session_state.messages:
            save_conversation(st.session_state.conversation_id, st.session_state.messages)
        st.session_state.last_save = current_time
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    prompt = st.chat_input("Ask something...")
    if prompt:
        # Add to full message history
        st.session_state.messages.append({"role": "human", "content": prompt})
        
        # Display user message
        with st.chat_message("human"):
            st.write(prompt)
        
        # Get and display AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Create a managed copy of the messages for the API
                    api_messages = manage_context_window(st.session_state.messages.copy())
                    
                    # Reset the conversation memory with the managed messages
                    memory = ConversationBufferMemory()
                    for msg in api_messages:
                        if msg["role"] == "human":
                            memory.chat_memory.add_user_message(msg["content"])
                        elif msg["role"] == "assistant":
                            memory.chat_memory.add_ai_message(msg["content"])
                    
                    # Create a new chain with the managed memory
                    temp_chain = ConversationChain(
                        llm=st.session_state.llm,
                        memory=memory,
                        verbose=True
                    )
                    
                    # Get response using the managed context
                    response = temp_chain.predict(input=prompt)
                    st.write(response)
                    
                    # Save AI message to full history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # Auto-save
                    save_conversation(st.session_state.conversation_id, st.session_state.messages)
                    st.session_state.last_save = datetime.now()
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.info("The conversation may be too long. Try starting a new chat.")
                    st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Error occurred: The conversation may be too long. Try starting a new chat."})

# History page
elif page == "History":
    st.title("Conversation History")
    
    try:
        conversations = get_conversations()
        
        if not conversations:
            st.info("No saved conversations yet.")
        else:
            # Display conversations in a dataframe
            df = pd.DataFrame(conversations)
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["updated_at"] = pd.to_datetime(df["updated_at"])
            df["created"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
            df["updated"] = df["updated_at"].dt.strftime("%Y-%m-%d %H:%M")
            
            st.dataframe(df[["conversation_id", "title", "created", "updated"]], use_container_width=True)
            
            # Select conversation
            selected_id = st.selectbox(
                "Select conversation:",
                options=df["conversation_id"].tolist(),
                format_func=lambda x: df[df["conversation_id"] == x]["title"].iloc[0]
            )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Load Conversation"):
                    try:
                        loaded_messages = get_messages(selected_id)
                        formatted_messages = [
                            {"role": msg["role"], "content": msg["content"]} 
                            for msg in loaded_messages
                        ]
                        
                        # Update state
                        st.session_state.conversation_id = selected_id
                        st.session_state.messages = formatted_messages
                        
                        # Go to chat page
                        st.session_state["page"] = "Chat"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading conversation: {str(e)}")
            
            with col2:
                export_format = st.selectbox("Export format:", ["json", "csv"])
                if st.button("Export Selected"):
                    try:
                        export_path = export_conversation(selected_id, format=export_format)
                        if export_path:
                            st.success(f"Conversation exported to {export_path}")
                        else:
                            st.error("Export failed")
                    except Exception as e:
                        st.error(f"Error exporting: {str(e)}")
            
            with col3:
                if st.button("Delete", type="primary", help="Permanently delete this conversation"):
                    # Confirm deletion
                    if st.checkbox("Confirm deletion"):
                        try:
                            conn = get_db_connection()
                            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (selected_id,))
                            conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (selected_id,))
                            conn.commit()
                            conn.close()
                            st.success("Conversation deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting conversation: {str(e)}")
    except Exception as e:
        st.error(f"Error loading conversation history: {str(e)}")

# Search page
elif page == "Search":
    st.title("Search Conversations")
    
    query = st.text_input("Search for keywords:")
    
    if query:
        try:
            results = search_conversations(query)
            
            if not results:
                st.info(f"No results found for '{query}'")
            else:
                st.success(f"Found {len(results)} results")
                
                for result in results:
                    with st.expander(f"{result['title']} - {result['updated_at']}"):
                        st.write(f"**Matching content:** {result['content']}")
                        if st.button("Load", key=f"load_search_{result['conversation_id']}"):
                            try:
                                loaded_messages = get_messages(result['conversation_id'])
                                formatted_messages = [
                                    {"role": msg["role"], "content": msg["content"]} 
                                    for msg in loaded_messages
                                ]
                                
                                # Update state
                                st.session_state.conversation_id = result['conversation_id']
                                st.session_state.messages = formatted_messages
                                
                                # Go to chat page
                                st.session_state["page"] = "Chat"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error loading search result: {str(e)}")
        except Exception as e:
            st.error(f"Error searching conversations: {str(e)}")

# Backup page
elif page == "Backup":
    st.title("Backup and Restore")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Create Backup")
        if st.button("Backup All Conversations"):
            try:
                backup_path = backup_database()
                if backup_path:
                    st.success(f"Backup created at {backup_path}")
                else:
                    st.info("No conversations to backup yet")
            except Exception as e:
                st.error(f"Error creating backup: {str(e)}")
    
    with col2:
        st.subheader("Restore from Backup")
        st.warning("Restoring will replace your current conversations. Make sure to backup first!")
        
        uploaded_file = st.file_uploader("Upload backup file (.db)", type=["db"])
        if uploaded_file is not None:
            if st.button("Restore"):
                try:
                    # Create restorations directory
                    os.makedirs("restorations", exist_ok=True)
                    
                    # Save uploaded file
                    restore_path = os.path.join("restorations", "uploaded_backup.db")
                    with open(restore_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Verify it's a valid database
                    verify_conn = sqlite3.connect(restore_path)
                    tables = verify_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    verify_conn.close()
                    
                    table_names = [t[0] for t in tables]
                    if "conversations" in table_names and "messages" in table_names:
                        # Backup current database first
                        backup_database()
                        
                        # Replace current database
                        os.makedirs("data", exist_ok=True)
                        if os.path.exists("data/conversations.db"):
                            os.remove("data/conversations.db")
                        os.replace(restore_path, "data/conversations.db")
                        
                        st.success("Database restored successfully!")
                        st.info("Reload the application to see the restored conversations.")
                    else:
                        st.error("The uploaded file is not a valid backup database")
                except Exception as e:
                    st.error(f"Error restoring database: {str(e)}")

# Auto-save info in sidebar
st.sidebar.markdown("---")
st.sidebar.info(
    "💾 Your conversations are automatically saved after each message. "
    "Use the Backup page to create downloadable backups of all your conversations."
)
