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
    if not title:
        title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
    conv_id = len(st.session_state.saved_conversations)
    
    # Create summary
    first_msg = st.session_state.messages[0]["content"][:100] if st.session_state.messages else ""
    summary = f"{first_msg}..."
    
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
                st.experimental_rerun()
                
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
                if st.button(f"{conv['title']} ({conv['timestamp'][:10]})", key=f"load_{conv['id']}"):
                    load_conversation(conv["id"])
                    st.experimental_rerun()
        
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
                    
                    # Auto-save every 10 messages
                    if len(st.session_state.messages) % 10 == 0:
                        save_conversation(f"Auto-saved {datetime.now().strftime('%H:%M')}")
                    
                except Exception as e:
                    st.error(f"API Error: {str(e)}")

if __name__ == "__main__":
    main()
