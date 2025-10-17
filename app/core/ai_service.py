import streamlit as st
from typing import Dict, Any, List, Optional
import json
import logging

class AIService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar lead con IA real"""
        try:
            client, provider = st.session_state.get('ai_client', (None, None))
            if not client:
                return self._get_fallback_analysis(lead_data)
            
            prompt = self._create_lead_analysis_prompt(lead_data)
            
            if provider == 'openai':
                response = client.chat.completions.create(
                    model=st.session_state.get('ai_model', 'gpt-3.5-turbo'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=st.session_state.get('ai_temperature', 0.7),
                    max_tokens=st.session_state.get('ai_max_tokens', 1000)
                )
                analysis_text = response.choices[0].message.content
            
            elif provider == 'anthropic':
                response = client.messages.create(
                    model=st.session_state.get('ai_model', 'claude-3-sonnet'),
                    max_tokens=st.session_state.get('ai_max_tokens', 1000),
                    temperature=st.session_state.get('ai_temperature', 0.7),
                    messages=[{"role": "user", "content": prompt}]
                )
                analysis_text = response.content[0].text
            
            elif provider == 'google':
                model = client.GenerativeModel(st.session_state.get('ai_model', 'gemini-pro'))
                response = model.generate_content(prompt)
                analysis_text = response.text
            
            elif provider == 'cohere':
                response = client.generate(
                    model=st.session_state.get('ai_model', 'command'),
                    prompt=prompt,
                    temperature=st.session_state.get('ai_temperature', 0.7),
                    max_tokens=st.session_state.get('ai_max_tokens', 1000)
                )
                analysis_text = response.generations[0].text
            
            return self._parse_ai_response(analysis_text, lead_data)
            
        except Exception as e:
            self.logger.error(f"Error en análisis de lead: {e}")
            return self._get_fallback_analysis(lead_data)
    
    def _create_lead_analysis_prompt(self, lead_data: Dict[str, Any]) -> str:
        """Crear prompt para análisis de lead"""
        return f"""
        Analiza el siguiente lead de ventas y proporciona un análisis detallado en formato JSON:

        DATOS DEL LEAD:
        {json.dumps(lead_data, indent=2, ensure_ascii=False)}

        Responde EXCLUSIVAMENTE con un JSON válido que contenga:
        {{
            "score": 0-100,
            "priority": "high|medium|low",
            "recommended_actions": ["acción1", "acción2", ...],
            "personalized_message": "mensaje personalizado para el lead",
            "key_insights": ["insight1", "insight2", ...],
            "estimated_conversion_probability": 0-100
        }}

        Considera:
        - Comportamiento e interacciones previas
        - Información demográfica y profesional
        - Potencial de conversión
        - Urgencia del lead
        """
    
    def _parse_ai_response(self, response_text: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parsear respuesta de IA"""
        try:
            # Buscar JSON en la respuesta
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            json_str = response_text[start_idx:end_idx]
            
            analysis = json.loads(json_str)
            analysis['ai_analyzed'] = True
            analysis['raw_response'] = response_text
            
            return analysis
            
        except json.JSONDecodeError:
            return self._get_fallback_analysis(lead_data)
    
    def _get_fallback_analysis(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis de fallback cuando la IA no está disponible"""
        return {
            "score": 50,
            "priority": "medium",
            "recommended_actions": ["Contactar por email", "Seguir en 3 días"],
            "personalized_message": "Gracias por su interés. Nos pondremos en contacto pronto.",
            "key_insights": ["Lead requiere análisis manual"],
            "estimated_conversion_probability": 30,
            "ai_analyzed": False
        }
    
    def generate_chat_response(self, conversation_history: List[Dict], lead_context: Dict) -> str:
        """Generar respuesta de chat con IA real"""
        try:
            client, provider = st.session_state.get('ai_client', (None, None))
            if not client:
                return "Actualmente estoy en modo de demostración. Configure la IA para respuestas inteligentes."
            
            prompt = self._create_chat_prompt(conversation_history, lead_context)
            
            if provider == 'openai':
                response = client.chat.completions.create(
                    model=st.session_state.get('ai_model', 'gpt-3.5-turbo'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=st.session_state.get('ai_temperature', 0.7),
                    max_tokens=st.session_state.get('ai_max_tokens', 500)
                )
                return response.choices[0].message.content
            
            elif provider == 'anthropic':
                response = client.messages.create(
                    model=st.session_state.get('ai_model', 'claude-3-sonnet'),
                    max_tokens=st.session_state.get('ai_max_tokens', 500),
                    temperature=st.session_state.get('ai_temperature', 0.7),
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            # Implementaciones similares para otros proveedores...
            
        except Exception as e:
            self.logger.error(f"Error en chat con IA: {e}")
            return "Lo siento, hubo un error al procesar tu mensaje. Por favor intenta nuevamente."
    
    def _create_chat_prompt(self, conversation_history: List[Dict], lead_context: Dict) -> str:
        """Crear prompt para chat de ventas"""
        history_text = "\n".join([
            f"Lead: {msg['message']}\nAsistente: {msg.get('response', '')}" 
            for msg in conversation_history[-5:]  # Últimos 5 mensajes
        ])
        
        return f"""
        Eres un asistente de ventas inteligente. Responde al lead de manera natural y útil.

        CONTEXTO DEL LEAD:
        {json.dumps(lead_context, indent=2, ensure_ascii=False)}

        HISTORIAL DE CONVERSACIÓN:
        {history_text}

        Responde de manera:
        - Natural y conversacional
        - Centrada en ayudar al lead
        - Sugiriendo próximos pasos cuando sea apropiado
        - Manteniendo un tono profesional pero amigable

        Responde únicamente con el texto de la respuesta, sin formato adicional.
        """
