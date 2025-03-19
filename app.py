import streamlit as st
from anthropic import Anthropic
import json
from datetime import datetime
import time
import random
import os

# Page configuration
st.set_page_config(page_title="Claude Chat Debugger", layout="wide")

# Vérification des secrets Streamlit
def check_api_key():
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("❌ Clé API Anthropic MANQUANTE")
            st.info("Étapes à suivre :")
            st.info("1. Allez dans les paramètres Streamlit")
            st.info("2. Section 'Secrets'")
            st.info("3. Ajoutez ANTHROPIC_API_KEY avec votre clé")
            return False
        return True
    except Exception as e:
        st.error(f"Erreur de configuration : {e}")
        return False

# Fichier de sauvegarde permanent
SAVE_FILE = "claude_conversations_backup.json"

# Initialisation des états de session
def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = "You are Claude, a helpful AI assistant created by Anthropic."
    
    if "saved_conversations" not in st.session_state:
        st.session_state.saved_conversations = []
    
    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = datetime.now()

# Chargement des conversations sauvegardées
def load_saved_conversations():
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")
        return []

# Sauvegarde des conversations
def save_conversations_to_file():
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.saved_conversations, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur de sauvegarde : {e}")
        return False

# Gestion des tokens
def count_tokens(messages, system_prompt):
    total_chars = len(system_prompt)
    for msg in messages:
        total_chars += len(str(msg.get("content", "")))
    return total_chars // 4

def trim_conversation(messages, max_tokens=150000):
    while count_tokens(messages, st.session_state.system_prompt) > max_tokens and len(messages) > 1:
        messages.pop(0)
    return messages

# Fonction principale
def main():
    # Initialisation de l'état de session
    init_session_state()
    
    # Vérification de la clé API
    if not check_api_key():
        return

    # Titre de l'application
    st.title("Claude Chat")

    # Initialisation du client Anthropic
    try:
        client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return

    # Affichage des messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Zone de saisie du chat
    if prompt := st.chat_input("Votre message"):
        # Ajouter le message de l'utilisateur
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Afficher le message de l'utilisateur
        with st.chat_message("user"):
            st.write(prompt)
        
        # Obtenir la réponse de Claude
        with st.chat_message("assistant"):
            with st.spinner("Réflexion en cours..."):
                try:
                    # Envoi de la requête à l'API
                    response = client.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=4000,
                        system=st.session_state.system_prompt,
                        messages=st.session_state.messages
                    )
                    
                    # Récupération et affichage de la réponse
                    assistant_response = response.content[0].text
                    st.write(assistant_response)
                    
                    # Ajouter la réponse à l'historique
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                
                except Exception as e:
                    st.error(f"Erreur API : {e}")

# Point d'entrée de l'application
if __name__ == "__main__":
    main()
