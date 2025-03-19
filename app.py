import streamlit as st
from anthropic import Anthropic
import json
from datetime import datetime
import time
import random
import os
import sys
import traceback  # Ajoutez ces imports en haut du fichier

# Le reste de votre code existant reste identique...

def main():
    st.title("Claude 3.7 Sonnet Chat")

    try:
        # Chargement explicite des conversations
        if not st.session_state.saved_conversations:
            st.session_state.saved_conversations = load_saved_conversations()
    except Exception as e:
        st.error(f"Erreur de chargement initial : {e}")

    try:
        client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

        # Sauvegarde systématique avant chaque opération critique
        save_conversations_to_file()

        # Reste de votre code de main()...
        sidebar_ui()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        if prompt := st.chat_input("Type your message here..."):
            # Sauvegarde avant chaque nouvel message
            save_conversation(force_file_save=True)

            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
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
                        st.error(f"Erreur API : {e}")
                        # Trace complète de l'erreur
                        error_details = traceback.format_exc()
                        st.error(error_details)
                        
                        # Sauvegarde des conversations même en cas d'erreur
                        save_conversations_to_file()

    except Exception as e:
        # Gestion d'erreur détaillée
        st.error(f"Erreur critique : {e}")
        
        # Trace complète de l'erreur
        error_details = traceback.format_exc()
        st.error(error_details)
        
        # Sauvegarde des conversations même en cas d'erreur
        save_conversations_to_file()

        # Option de redémarrage
        if st.button("Redémarrer l'application"):
            st.experimental_rerun()

# Modification du point d'entrée
if __name__ == "__main__":
    try:
        # Sauvegarde initiale
        save_conversations_to_file()
        
        # Lancement principal
        main()
    except Exception as e:
        st.error(f"Erreur de démarrage : {e}")
        traceback.print_exc()
