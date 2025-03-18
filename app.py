import streamlit as st
from datetime import datetime
from anthropic import Anthropic
import pandas as pd
import json

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

def save_conversation(messages, title=None):
    """Save the current conversation to session state."""
    # Initialize saved_conversations in session state if not present
    if "saved_conversations" not in st.session_state:
        st.session_state.saved_conversations = []
    
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
    
    # Create new conversation record
    conversation_id = len(st.session_state.saved_conversations)
    conversation = {
        "id": conversation_id,
        "title": title,
        "summary": summary,
        "messages": messages.copy(),
        "timestamp": datetime.now().isoformat(),
        "token_count": num_tokens_from_messages(messages)
    }
    
    # Add to saved conversations
    st.session_state.saved_conversations.append(conversation)
    return conversation_id

def get_conversation_list():
    """Get list of all saved conversations."""
    if "saved_conversations" not in st.session_state:
        st.session_state.saved_conversations = []
    
    return [
        (conv["id"], conv["title"], conv["summary"], conv["timestamp"], conv["token_count"])
        for conv in st.session_state.saved_conversations
    ]

def load_conversation(conversation_id):
    """Load a specific conversation by ID."""
    if "saved_conversations" not in st.session_state:
        return []
    
    for conv in st.session_state.saved_conversations:
        if conv["id"] == conversation_id:
            return conv["messages"].copy()
    
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
        
        # Display conversations or a message if none exist
        if not conversations:
            st.write("No saved conversations yet.")
        else:
            for conv_id, title, summary, timestamp, token_count in conversations:
                with st.expander(f"{title} ({timestamp[:10]})"):
                    st.write(f"Summary: {summary}")
                    st.write(f"Tokens: {token_count}")
                    if st.button(f"Load conversation #{conv_id}", key=f"load_{conv_id}"):
                        st.session_state.messages = load_conversation(conv_id)
                        st.experimental_rerun()
        
        # Export/Import section
        st.subheader("Backup and Restore")
        if st.button("Export All Conversations"):
            if "saved_conversations" in st.session_state and st.session_state.saved_conversations:
                export_data = json.dumps(st.session_state.saved_conversations)
                st.download_button(
                    label="Download JSON",
                    data=export_data,
                    file_name=f"claude_conversations_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )

def main():
    st.title("Claude 3.7 Sonnet Chat")
    
    # Check for API key in secrets
    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("Error: API key not found in secrets. Please add your Anthropic API key to the Streamlit secrets.")
        st.info("Go to your Streamlit app settings, find the 'Secrets' section, and add: ANTHROPIC_API_KEY = 'your-api-key'")
        return
    
    # Display API key status
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    if not api_key or api_key.startswith("sk-ant-"):
        st.success("API key detected")
    else:
        st.warning("Your API key doesn't look like a valid Anthropic key. It should start with 'sk-ant-'")
    
    # Initialize the Anthropic client
    try:
        client = Anthropic(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing Anthropic client: {str(e)}")
        return
    
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
                try:
                    # Try with the latest model
                    try:
                        response = client.messages.create(
                            model="claude-3-7-sonnet-20240320",
                            max_tokens=4000,
                            messages=st.session_state.messages
                        )
                        assistant_response = response.content[0].text
                    except Exception as e:
                        # If that fails, try with an alternative model name
                        st.warning("Trying alternative model name...")
                        response = client.messages.create(
                            model="claude-3-7-sonnet-20240305",
                            max_tokens=4000,
                            messages=st.session_state.messages
                        )
                        assistant_response = response.content[0].text
                    
                    # Display the response
                    st.write(assistant_response)
                    
                    # Add Claude's response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                except Exception as e:
                    error_message = str(e)
                    st.error(f"Error from Claude API: {error_message}")
                    st.info("This might be an issue with your API key or model access. Please check your Anthropic account.")
                    
                    # Add error message to chat history to keep the conversation coherent
                    error_response = "I apologize, but I encountered an error while processing your request. Please try again or check your API configuration."
                    st.session_state.messages.append({"role": "assistant", "content": error_response})

if __name__ == "__main__":
    main()
