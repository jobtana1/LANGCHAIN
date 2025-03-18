# Add these to your app.py imports
import streamlit as st
from datetime import datetime
import os

# Add this in your sidebar
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

# Add this to your main function before the chat loop
def main():
    # Existing setup code...
    
    # Add conversation management
    render_conversation_sidebar()
    
    # Auto-save every N messages
    if "messages" in st.session_state and len(st.session_state.messages) % 10 == 0:
        save_conversation(st.session_state.messages, 
                         title=f"Auto-saved {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Apply token window management before sending to API
    if "messages" in st.session_state:
        st.session_state.messages = manage_context_window(st.session_state.messages)
    
    # Existing chat loop...
