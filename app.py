import streamlit as st
import os
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Set page config
st.set_page_config(page_title="LangChain + Claude Assistant", layout="wide")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(return_messages=True)

if "chain" not in st.session_state:
    # Get API key from secrets
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    
    # Initialize Claude
    llm = ChatAnthropic(
        model="claude-3-7-sonnet-20250219",
        anthropic_api_key=api_key,
        temperature=0.7
    )
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant helping with a crucial project. Be concise and focused on the task."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    
    # Create conversation chain
    st.session_state.chain = ConversationChain(
        llm=llm,
        prompt=prompt,
        memory=st.session_state.memory,
        verbose=True
    )

# App interface
st.title("LangChain + Claude Assistant")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
prompt = st.chat_input("Type your message here...")
if prompt:
    # Add user message
    st.session_state.messages.append({"role": "human", "content": prompt})
    
    # Display user message
    with st.chat_message("human"):
        st.write(prompt)
    
    # Get response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.chain.invoke({"input": prompt})
            st.write(response["response"])
    
    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response["response"]})
