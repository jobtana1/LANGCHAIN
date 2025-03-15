import streamlit as st
import uuid
from langchain_anthropic import ChatAnthropic
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
import json
import datetime
import os

# Retrieve API Key
anthropic_api_key = st.secrets["ANTHROPIC_API_KEY"]

# Initialize Chat Model
llm = ChatAnthropic(
    api_key=anthropic_api_key,
    model="claude-3-7-sonnet-20240229",  # Correct model name
    temperature=0.7,
    max_tokens=4000
)

# Set up Memory
conversation_memory = ConversationBufferMemory()
conversation_chain = ConversationChain(
    llm=llm,
    memory=conversation_memory
)
# Page Config
st.set_page_config(page_title="Claude Assistant", layout="wide")

# Initialize state
def initialize_conversation_state():
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chain" not in st.session_state:
        st.session_state.chain = conversation_chain

# Init state
initialize_conversation_state()

# Export function
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
