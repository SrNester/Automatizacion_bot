import streamlit as st
from typing import Dict, Any, List
import os

class AIConfigManager:
    def __init__(self):
        self.providers = {
            "openai": {
                "name": "OpenAI GPT",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                "required_env": "OPENAI_API_KEY"
            },
            "anthropic": {
                "name": "Claude (Anthropic)",
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "required_env": "ANTHROPIC_API_KEY"
            },
            "google": {
                "name": "Google Gemini",
                "models": ["gemini-pro", "gemini-1.5-pro"],
                "required_env": "GOOGLE_API_KEY"
            },
            "cohere": {
                "name": "Cohere",
                "models": ["command", "command-r"],
                "required_env": "COHERE_API_KEY"
            }
        }
    
    def render_ai_settings(self):
        """Renderizar configuración de IA"""
        st.subheader("🤖 Configuración de IA")
        
        # Selección de proveedor
        provider_options = {f"{k} - {v['name']}": k for k, v in self.providers.items()}
        selected_provider = st.selectbox(
            "Proveedor de IA",
            options=list(provider_options.keys()),
            index=0
        )
        
        provider_key = provider_options[selected_provider]
        provider_info = self.providers[provider_key]
        
        # Configuración de API Key
        api_key = st.text_input(
            f"API Key de {provider_info['name']}",
            type="password",
            help=f"Variable de entorno: {provider_info['required_env']}"
        )
        
        # Selección de modelo
        selected_model = st.selectbox(
            "Modelo",
            options=provider_info["models"],
            index=0
        )
        
        # Configuración avanzada
        with st.expander("Configuración Avanzada"):
            temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
            max_tokens = st.number_input("Max Tokens", 100, 4000, 1000)
        
        if st.button("💾 Guardar Configuración IA"):
            if api_key:
                # Guardar en variables de entorno de la sesión
                os.environ[provider_info["required_env"]] = api_key
                st.session_state.ai_provider = provider_key
                st.session_state.ai_model = selected_model
                st.session_state.ai_temperature = temperature
                st.session_state.ai_max_tokens = max_tokens
                st.success("✅ Configuración de IA guardada")
            else:
                st.error("❌ Por favor ingresa una API Key válida")
        
        return {
            "provider": provider_key,
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    
    def get_ai_client(self):
        """Obtener cliente de IA basado en la configuración"""
        provider = st.session_state.get('ai_provider', 'openai')
        
        try:
            if provider == 'openai':
                from openai import OpenAI
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OpenAI API Key no configurada")
                return OpenAI(api_key=api_key), 'openai'
            
            elif provider == 'anthropic':
                from anthropic import Anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError("Anthropic API Key no configurada")
                return Anthropic(api_key=api_key), 'anthropic'
            
            elif provider == 'google':
                import google.generativeai as genai
                api_key = os.getenv('GOOGLE_API_KEY')
                if not api_key:
                    raise ValueError("Google API Key no configurada")
                genai.configure(api_key=api_key)
                return genai, 'google'
            
            elif provider == 'cohere':
                import cohere
                api_key = os.getenv('COHERE_API_KEY')
                if not api_key:
                    raise ValueError("Cohere API Key no configurada")
                return cohere.Client(api_key), 'cohere'
            
        except ImportError as e:
            st.error(f"❌ Librería no instalada: {e}")
            return None, None
        except Exception as e:
            st.error(f"❌ Error configurando IA: {e}")
            return None, None
