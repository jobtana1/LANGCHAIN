import streamlit as st
import uuid
from langchain.llms import Anthropic
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

# Retrieve API Key from Streamlit Secrets
anthropic_api_key = st.secrets["ANTHROPIC_API_KEY"]

# Initialize Anthropic Language Model
llm = Anthropic(
    anthropic_api_key=anthropic_api_key,
    model="claude-v1",
    temperature=0.7
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

# Chat Interface
st.title("LangChain + Claude Assistant")

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
    st.session_state.messages.append({"role": "assistant", "content": response["response"]}) Update app with new Anthropic integration
