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
