import streamlit as st
import os
from langchain_anthropic import ChatAnthropic
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

# Page config
st.set_page_config(page_title="Claude Chat", layout="wide")

# Get API Key
api_key = st.secrets["ANTHROPIC_API_KEY"]

# Try a simpler model initialization
try:
    llm = ChatAnthropic(
        anthropic_api_key=api_key,  # Changed parameter name
        model="claude-3-opus-20240229",  # Using a well-established model
        temperature=0.7,
        max_tokens=1000
    )
    st.success("Model initialized successfully")
except Exception as e:
    st.error(f"Error initializing model: {type(e).__name__}")
    st.stop()

# Set up simple memory and conversation
memory = ConversationBufferMemory()
conversation = ConversationChain(llm=llm, memory=memory)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing messages
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
            response = conversation.predict(input=prompt)
            st.write(response)
    
    # Save AI message
    st.session_state.messages.append({"role": "assistant", "content": response})
