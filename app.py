import streamlit as st
import uuid
from langchain_anthropic import ChatAnthropic
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
import json
import datetime
import os

# Retrieve API Key from Streamlit Secrets
anthropic_api_key = st.secrets["ANTHROPIC_API_KEY"]

# Initialize Anthropic Chat Model
llm = ChatAnthropic(
    api_key=anthropic_api_key,
    model="claude-3-7-sonnet-20240229",  # Correct model name
    temperature=0.7,
    max_tokens=4000
)

# Set up Conversation Memory
conversation_memory = ConversationBufferMemory()
conversation_chain = ConversationChain(
    llm=llm,
    memory=conversation_memory
)

# Streamlit Page Configuration
st.set_page_config(page_title="Claude Assistant", layout="wide")

# Initialize conversation state
def initialize_conversation_state():
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chain" not in st.session_state:
        st.session_state.chain = conversation_chain

# Call state initialization
initialize_conversation_state()

# Feature 1: Export Conversation
def export_conversation():
    conversation_data = {
        "conversation_id": st.session_state.conversation_id,
        "messages": st.session_state.messages,
        "timestamp": datetime.datetime.now().isoformat()
    }
    os.makedirs("exports", exist_ok=True)
    filename = f"exports/conversation_{st.session_state.conversation_id}.json"
    with open(filename, "w") as f:
        json.dump(conversation_data, f, indent=2)
    return filename

# Feature 2: Search Messages
def search_messages(query):
    return [msg for msg in st.session_state.messages if query.lower() in msg["content"].lower()]

# Main Chat Interface
st.title("LangChain + Claude Assistant")

# Sidebar for Additional Features
with st.sidebar:
    st.header("Conversation Tools")
    if st.button("Export Conversation"):
        filename = export_conversation()
        st.success(f"Conversation exported to {filename}")
    
    search_query = st.text_input("Search Messages")
    if search_query:
        results = search_messages(search_query)
        st.subheader("Search Results")
        for msg in results:
            st.write(f"{msg['role'].capitalize()}: {msg['content']}")

# Display existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
prompt = st.chat_input("Type your message here...")
if prompt:
    # Add user message to session state
    st.session_state.messages.append({"role": "human", "content": prompt})
    
    # Display user message
    with st.chat_message("human"):
        st.write(prompt)
    
    # Generate AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.chain.invoke({"input": prompt})
            st.write(response["response"])
    
    # Add AI response to session state
    st.session_state.messages.append({"role": "assistant", "content": response["response"]})
