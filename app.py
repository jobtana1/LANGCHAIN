import streamlit as st
from anthropic import Anthropic
import json
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Claude 3.7 Chat", layout="wide")

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = "You are Claude, a helpful AI assistant created by Anthropic."
    
if "saved_conversations" not in st.session_state:
    st.session_state.saved_conversations = []

# Ajout du contrôle de temps pour les sauvegardes
if "last_save_time" not in st.session_state:
    st.session_state.last_save_time = datetime.now()

# Token management functions
def count_tokens(messages, system_prompt):
    """Simple token counter (approximation)"""
    # Approximation: 1 token ≈ 4 characters
    total_chars = len(system_prompt)
    for msg in messages:
        total_chars += len(str(msg.get("content", "")))
    return total_chars // 4

def trim_conversation(messages, max_tokens=150000):
    """Trim conversation if it gets too long"""
    # Calculate approximate tokens
    while count_tokens(messages, st.session_state.system_prompt) > max_tokens and len(messages) > 1:
        # Remove oldest message
        messages.pop(0)
    return messages

# Conversation management functions
def save_conversation(title=None):
    """Save current conversation to session state"""
    if not st.session_state.messages:
        return None  # Don't save empty conversations
        
    # Generate title from first user message if not provided
    if not title:
        first_user_msg = next((msg["content"] for msg in st.session_state.messages 
                             if msg["role"] == "user"), "")
        
        # Create a short title from the first user message
        if first_user_msg:
            short_title = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
            title = f"{short_title} - {datetime.now().strftime('%m/%d %H:%M')}"
        else:
            title = f"Chat {datetime.now().strftime('%m/%d %H:%M')}"
        
    conv_id = len(st.session_state.saved_conversations)
    
    # Create better summary
    first_msg = next((msg["content"][:50] for msg in st.session_state.messages 
                     if msg["role"] == "user"), "")
    last_msg = next((msg["content"][:50] for msg in reversed(st.session_state.messages) 
                    if msg["role"] == "assistant"), "")
    
    if first_msg and last_msg:
        summary = f"{first_msg}... → {last_msg}..."
    else:
        summary = f"{first_msg or last_msg}..."
    
    # Save conversation data
    conversation = {
        "id": conv_id,
        "title": title,
        "messages": st.session_state.messages.copy(),
        "system_prompt": st.session_state.system_prompt,
        "timestamp": datetime.now().isoformat(),
        "summary": summary
    }
    
    st.session_state.saved_conversations.append(conversation)
    return conv_id

def load_conversation(conv_id):
    """Load a saved conversation"""
    for conv in st.session_state.saved_conversations:
        if conv["id"] == conv_id:
            st.session_state.messages = conv["messages"].copy()
            st.session_state.system_prompt = conv["system_prompt"]
            return True
    return False

# UI components
def sidebar_ui():
    """Render the sidebar UI"""
    with st.sidebar:
        st.title("Chat Settings")
        
        # System prompt editor
        st.subheader("System Prompt")
        new_prompt = st.text_area("Edit", st.session_state.system_prompt, height=100)
        if new_prompt != st.session_state.system_prompt:
            st.session_state.system_prompt = new_prompt
            
        # Conversation management
        st.subheader("Conversation")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("New Chat"):
                st.session_state.messages = []
                st.rerun()
                
        with col2:
            if st.button("Save Chat"):
                title = st.text_input("Title:", f"Chat {datetime.now().strftime('%H:%M')}")
                save_id = save_conversation(title)
                st.success(f"Saved #{save_id}")
                
        # Saved conversations
        st.subheader("Saved Chats")
        if not st.session_state.saved_conversations:
            st.write("No saved conversations")
        else:
            for conv in st.session_state.saved_conversations:
                with st.expander(f"{conv['title']}"):
                    st.write(f"Created: {conv['timestamp'][:10]}")
                    st.write(f"Summary: {conv.get('summary', '')}")
                    if st.button(f"Load", key=f"load_{conv['id']}"):
                        load_conversation(conv["id"])
                        st.rerun()
        
        # Export functionality            
        if st.button("Export All Chats"):
            if st.session_state.saved_conversations:
                export_data = json.dumps(st.session_state.saved_conversations)
                st.download_button(
                    "Download JSON",
                    export_data,
                    file_name=f"claude_chats_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )

def main():
    # Main title
    st.title("Claude 3.7 Sonnet Chat")
    
    # Initialize Anthropic client
    try:
        client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception as e:
        st.error(f"API Key Error: {str(e)}")
        st.info("Please add your Anthropic API key to Streamlit secrets.")
        return
        
    # Render sidebar
    sidebar_ui()
    
    # Trim conversation if needed
    st.session_state.messages = trim_conversation(st.session_state.messages)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get Claude's response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=4000,
                        system=st.session_state.system_prompt,
                        messages=st.session_state.messages
                    )
                    
                    assistant_response = response.content[0].text
                    
                    # Display the response
                    st.write(assistant_response)
                    
                    # Add response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                    # Version corrigée de la logique d'auto-sauvegarde avec contrôle de temps
                    # Calculez le temps écoulé depuis la dernière sauvegarde
                    time_since_last_save = (datetime.now() - st.session_state.last_save_time).total_seconds()
                    
                    should_save = (
                        # Sauvegarde basée sur le nombre de messages
                        (len(st.session_state.messages) % 5 == 0 and 
                         len(st.session_state.messages) > 0) or 
                        # Sauvegarde basée sur la taille de la réponse
                        len(assistant_response) > 1000
                    ) and (
                        # Assurez-vous qu'au moins 2 minutes se sont écoulées depuis la dernière sauvegarde
                        time_since_last_save > 120  # 120 secondes = 2 minutes
                    )
                    
                    if should_save:
                        save_id = save_conversation()
                        if save_id is not None:
                            st.toast(f"Conversation auto-saved", icon="💾")
                            # Mettez à jour le timestamp de la dernière sauvegarde
                            st.session_state.last_save_time = datetime.now()
                    
                except Exception as e:
                    st.error(f"API Error: {str(e)}")

if __name__ == "__main__":
    main()
