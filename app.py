import streamlit as st
from anthropic import Anthropic
import json
from datetime import datetime
import time
import random
import os

# Fichier de sauvegarde permanent
SAVE_FILE = "claude_conversations_backup.json"

# Page configuration
st.set_page_config(page_title="Claude 3.7 Chat", layout="wide")

# Charger conversations du fichier
def load_saved_conversations():
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Erreur chargement: {str(e)}")
        return []

# Sauvegarder conversations dans fichier
def save_conversations_to_file():
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.saved_conversations, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur sauvegarde: {str(e)}")
        return False

# Gestion des tokens
def count_tokens(messages, system_prompt):
    """Simple token counter (approximation)"""
    total_chars = len(system_prompt)
    for msg in messages:
        total_chars += len(str(msg.get("content", "")))
    return total_chars // 4

def trim_conversation(messages, max_tokens=150000):
    """Trim conversation if it gets too long"""
    while count_tokens(messages, st.session_state.system_prompt) > max_tokens and len(messages) > 1:
        messages.pop(0)
    return messages

# Retry mechanism pour les appels API
def get_claude_response_with_retry(client, model, max_tokens, system, messages, max_retries=5):
    retry_count = 0
    base_wait_time = 2
    
    while retry_count < max_retries:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages
            )
            return response
            
        except Exception as e:
            error_message = str(e)
            if "overloaded_error" in error_message or "529" in error_message:
                retry_count += 1
                if retry_count >= max_retries:
                    raise e
                
                wait_time = base_wait_time * (2 ** (retry_count - 1)) + random.uniform(0, 1)
                st.warning(f"API surchargée. Nouvelle tentative dans {wait_time:.1f}s... ({retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise e
    
    raise Exception("Impossible de contacter l'API après plusieurs tentatives")

# Gestion des conversations
def save_conversation(title=None, force_file_save=False):
    if not st.session_state.messages:
        return None

    if not title:
        first_user_msg = next((msg["content"] for msg in st.session_state.messages 
                             if msg["role"] == "user"), "")

        if first_user_msg:
            short_title = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
            title = f"{short_title} - {datetime.now().strftime('%m/%d %H:%M')}"
        else:
            title = f"Chat {datetime.now().strftime('%m/%d %H:%M')}"

    # Vérifier si conversation similaire existe déjà
    existing_conv_id = None
    for i, conv in enumerate(st.session_state.saved_conversations):
        if (len(conv["messages"]) == len(st.session_state.messages) and
            all(a.get("content") == b.get("content") for a, b in zip(conv["messages"], st.session_state.messages))):
            existing_conv_id = conv["id"]
            st.session_state.saved_conversations[i]["timestamp"] = datetime.now().isoformat()
            break

    if existing_conv_id is None:
        conv_id = max([conv.get("id", -1) for conv in st.session_state.saved_conversations], default=-1) + 1

        first_msg = next((msg["content"][:50] for msg in st.session_state.messages 
                         if msg["role"] == "user"), "")
        last_msg = next((msg["content"][:50] for msg in reversed(st.session_state.messages) 
                        if msg["role"] == "assistant"), "")

        if first_msg and last_msg:
            summary = f"{first_msg}... → {last_msg}..."
        else:
            summary = f"{first_msg or last_msg}..."

        conversation = {
            "id": conv_id,
            "title": title,
            "messages": st.session_state.messages.copy(),
            "system_prompt": st.session_state.system_prompt,
            "timestamp": datetime.now().isoformat(),
            "summary": summary
        }

        st.session_state.saved_conversations.append(conversation)
    else:
        conv_id = existing_conv_id

    if force_file_save:
        save_conversations_to_file()

    return conv_id

def load_conversation(conv_id):
    for conv in st.session_state.saved_conversations:
        if conv["id"] == conv_id:
            st.session_state.messages = conv["messages"].copy()
            st.session_state.system_prompt = conv["system_prompt"]
            return True
    return False

# UI sidebar
def sidebar_ui():
    with st.sidebar:
        st.title("Chat Settings")

        st.subheader("System Prompt")
        new_prompt = st.text_area("Edit", st.session_state.system_prompt, height=100)
        if new_prompt != st.session_state.system_prompt:
            st.session_state.system_prompt = new_prompt

        st.subheader("Conversation")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("New Chat"):
                if st.session_state.messages:
                    save_id = save_conversation(force_file_save=True)
                    if save_id is not None:
                        st.toast(f"Conversation sauvegardée (ID: {save_id})", icon="💾")

                st.session_state.messages = []
                st.rerun()

        with col2:
            if st.button("Save Chat"):
                title = st.text_input("Title:", f"Chat {datetime.now().strftime('%H:%M')}")
                save_id = save_conversation(title, force_file_save=True)
                if save_id is not None:
                    st.success(f"Sauvegardé #{save_id}")

        st.subheader("Saved Chats")
        if not st.session_state.saved_conversations:
            st.write("No saved conversations")
        else:
            sorted_convs = sorted(
                st.session_state.saved_conversations, 
                key=lambda x: x.get("timestamp", ""), 
                reverse=True
            )

            for conv in sorted_convs:
                with st.expander(f"{conv['title']}"):
                    st.write(f"Created: {conv['timestamp'][:16].replace('T', ' ')}")
                    st.write(f"Summary: {conv.get('summary', '')}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Load", key=f"load_{conv['id']}"):
                            if st.session_state.messages:
                                save_conversation(force_file_save=True)

                            load_conversation(conv["id"])
                            st.rerun()
                    with col2:
                        if st.button(f"Delete", key=f"del_{conv['id']}"):
                            st.session_state.saved_conversations = [
                                c for c in st.session_state.saved_conversations if c["id"] != conv["id"]
                            ]
                            save_conversations_to_file()
                            st.rerun()

        st.subheader("Import/Export")
        # Bouton d'export
        if st.button("Export All Chats"):
            if st.session_state.saved_conversations:
                export_data = json.dumps(st.session_state.saved_conversations, ensure_ascii=False, indent=2)
                st.download_button(
                    "Download JSON",
                    export_data,
                    file_name=f"claude_chats_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )

        # Import de conversations
        uploaded_file = st.file_uploader("Upload JSON", type="json")
        if uploaded_file is not None:
            try:
                imported_data = json.loads(uploaded_file.read())
                if isinstance(imported_data, list):
                    existing_ids = {conv["id"] for conv in st.session_state.saved_conversations}
                    new_convs = [conv for conv in imported_data if conv["id"] not in existing_ids]

                    if new_convs:
                        st.session_state.saved_conversations.extend(new_convs)
                        save_conversations_to_file()
                        st.success(f"Importé {len(new_convs)} conversations")
                        st.rerun()
                    else:
                        st.info("Aucune nouvelle conversation")
                else:
                    st.error("Format incorrect")
            except Exception as e:
                st.error(f"Erreur import: {str(e)}")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = "You are Claude, a helpful AI assistant created by Anthropic."
    
if "saved_conversations" not in st.session_state:
    st.session_state.saved_conversations = load_saved_conversations()

if "last_save_time" not in st.session_state:
    st.session_state.last_save_time = datetime.now()

def main():
    st.title("Claude 3.7 Sonnet Chat")

    try:
        client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

        # Appel de la sidebar
        sidebar_ui()

        # Trim conversation si nécessaire
        st.session_state.messages = trim_conversation(st.session_state.messages)

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        if prompt := st.chat_input("Type your message here..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Utilisation du retry mechanism
                        response = get_claude_response_with_retry(
                            client=client,
                            model="claude-3-sonnet-20240229",
                            max_tokens=4000,
                            system=st.session_state.system_prompt,
                            messages=st.session_state.messages,
                            max_retries=5
                        )

                        assistant_response = response.content[0].text

                        st.write(assistant_response)

                        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

                        # Sauvegarde automatique
                        time_since_last_save = (datetime.now() - st.session_state.last_save_time).total_seconds()

                        should_save = (
                            (len(st.session_state.messages) % 4 == 0) or 
                            len(assistant_response) > 800 or
                            time_since_last_save > 300  # 5 minutes
                        )

                        if should_save:
                            save_id = save_conversation(force_file_save=True)
                            if save_id is not None:
                                st.toast(f"Auto-sauvegardé", icon="💾")
                                st.session_state.last_save_time = datetime.now()

                    except Exception as e:
                        st.error(f"API Error: {str(e)}")
                        # Auto-sauvegarde en cas d'erreur
                        save_conversations_to_file()

    except Exception as e:
        st.error(f"Initialization Error: {str(e)}")

if __name__ == "__main__":
    main()
