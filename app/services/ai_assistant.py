import openai
from typing import Dict, List, Optional
from ..core.config import settings

class AIAssistant:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.knowledge_base = self._load_knowledge_base()
    
    def _load_knowledge_base(self) -> Dict:
        """Carga la base de conocimiento de la empresa"""
        return {
            "products": [
                {
                    "name": "Automatización CRM",
                    "price": "desde $299/mes",
                    "features": ["Lead scoring", "Email automation", "Reporting"]
                },
                {
                    "name": "Chatbot IA",
                    "price": "desde $199/mes", 
                    "features": ["24/7 support", "Multi-idioma", "Integración WhatsApp"]
                }
            ],
            "faqs": [
                {
                    "question": "¿Cuánto tiempo toma la implementación?",
                    "answer": "La implementación básica toma entre 1-2 semanas."
                }
            ]
        }
    
    async def process_conversation(self, 
                                 message: str, 
                                 lead_context: Dict,
                                 conversation_history: List[Dict]) -> str:
        """Procesa una conversación y genera respuesta inteligente"""
        
        # Construir contexto para la IA
        context = self._build_context(lead_context, conversation_history)
        
        system_prompt = f"""
        Eres un asistente de ventas experto. Tu empresa ofrece soluciones de automatización.
        
        Contexto del lead:
        - Nombre: {lead_context.get('name', 'Usuario')}
        - Empresa: {lead_context.get('company', 'No especificada')}
        - Interés: {lead_context.get('interests', 'General')}
        - Score: {lead_context.get('score', 0)}/100
        
        Productos disponibles: {self.knowledge_base['products']}
        
        Instrucciones:
        1. Sé profesional pero cercano
        2. Haz preguntas de calificación cuando sea apropiado
        3. Ofrece productos relevantes basados en necesidades
        4. Si no sabes algo, deriva con un humano
        5. Detecta señales de compra y actúa en consecuencia
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *conversation_history,
                    {"role": "user", "content": message}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Detectar intención de compra
            if self._detect_buying_signals(message, ai_response):
                await self._trigger_sales_alert(lead_context)
            
            return ai_response
            
        except Exception as e:
            return "Disculpa, tengo problemas técnicos. Te conectaré con un humano enseguida."
    
    def _build_context(self, lead_context: Dict, history: List[Dict]) -> str:
        """Construye contexto para la IA"""
        recent_history = history[-5:] if len(history) > 5 else history
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
    
    def _detect_buying_signals(self, user_message: str, ai_response: str) -> bool:
        """Detecta señales de compra en la conversación"""
        buying_signals = [
            'precio', 'costo', 'cuánto', 'presupuesto', 'comprar', 
            'contratar', 'implementar', 'cuando podemos empezar',
            'demo', 'prueba', 'reunión'
        ]
        
        message_lower = user_message.lower()
        return any(signal in message_lower for signal in buying_signals)
    
    async def _trigger_sales_alert(self, lead_context: Dict):
        """Dispara alerta al equipo de ventas"""
        # Aquí integrarías con Slack, Teams, o email
        alert_message = f"""
        🔥 LEAD CALIENTE DETECTADO!
        
        Lead: {lead_context.get('name')}
        Empresa: {lead_context.get('company')}
        Score: {lead_context.get('score')}/100
        
        ¡Señales de compra detectadas en la conversación!
        """
        
        # Enviar alerta (implementar según tu sistema)
        print(alert_message)  # Placeholder