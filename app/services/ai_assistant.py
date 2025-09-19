import openai
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from ..core.config import settings
from ..models.interaction import Interaction, ConversationSummary, generate_conversation_id
from ..models.lead import Lead
from ..services.lead_scoring import LeadScoringService

class AIAssistant:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.knowledge_base = self._load_knowledge_base()
        self.scoring_service = LeadScoringService()
        
    def _load_knowledge_base(self) -> Dict:
        """Carga la base de conocimiento de la empresa"""
        return {
            "products": [
                {
                    "name": "Automatización CRM",
                    "price": "desde $299/mes",
                    "features": ["Lead scoring automático", "Email automation", "Reporting avanzado", "Integración WhatsApp"],
                    "description": "Sistema completo de automatización de ventas y marketing"
                },
                {
                    "name": "Chatbot IA Premium", 
                    "price": "desde $199/mes",
                    "features": ["Soporte 24/7", "Multi-idioma", "Integración WhatsApp/Telegram", "IA personalizada"],
                    "description": "Chatbot inteligente para atención al cliente y calificación de leads"
                },
                {
                    "name": "Analytics Suite",
                    "price": "desde $149/mes", 
                    "features": ["Dashboard en tiempo real", "Reportes personalizados", "Métricas de conversión", "ROI tracking"],
                    "description": "Análisis completo de performance de ventas y marketing"
                }
            ],
            "faqs": [
                {
                    "question": "¿Cuánto tiempo toma la implementación?",
                    "answer": "La implementación básica toma entre 1-2 semanas. Para configuraciones avanzadas, hasta 4 semanas."
                },
                {
                    "question": "¿Ofrecen prueba gratuita?",
                    "answer": "Sí, ofrecemos 14 días de prueba gratuita sin compromiso."
                },
                {
                    "question": "¿Qué integraciones soportan?",
                    "answer": "Soportamos HubSpot, Pipedrive, Salesforce, WhatsApp Business, Telegram, Meta Ads, Google Ads y más."
                }
            ],
            "intents": {
                "greeting": ["hola", "buenos días", "buenas tardes", "hey", "hi"],
                "product_inquiry": ["producto", "servicio", "qué ofrecen", "información", "detalles"],
                "pricing": ["precio", "costo", "cuánto", "presupuesto", "tarifa"],
                "demo": ["demo", "demostración", "prueba", "ver funcionando", "presentación"],
                "support": ["ayuda", "soporte", "problema", "error", "no funciona"],
                "buying": ["comprar", "contratar", "adquirir", "implementar", "empezar"]
            }
        }

    async def process_message(self, 
                            message: str,
                            phone_number: str,
                            platform: str,
                            conversation_id: Optional[str] = None,
                            db: Session = None) -> Dict:
        """
        Procesa un mensaje entrante y genera respuesta inteligente
        
        Returns:
            dict: {
                "response": str,
                "conversation_id": str,
                "intent": str,
                "confidence": float,
                "escalate": bool,
                "buying_signals": bool
            }
        """
        start_time = time.time()
        
        # Obtener o crear lead
        lead = await self._get_or_create_lead(phone_number, db)
        
        # Generar conversation_id si no existe
        if not conversation_id:
            conversation_id = generate_conversation_id()
        
        # Obtener contexto de conversación
        conversation_history = await self._get_conversation_history(conversation_id, db)
        
        # Clasificar intención del mensaje
        intent, confidence = self._classify_intent(message)
        
        # Detectar señales de compra
        buying_signals = self._detect_buying_signals(message)
        
        # Analizar sentiment
        sentiment = await self._analyze_sentiment(message)
        
        # Generar respuesta con IA
        ai_response = await self._generate_ai_response(
            message, lead, conversation_history, intent
        )
        
        # Determinar si escalar a humano
        should_escalate = self._should_escalate(message, intent, confidence, conversation_history)
        
        # Calcular tiempo de respuesta
        response_time = int((time.time() - start_time) * 1000)
        
        # Guardar interacción en BD
        interaction = await self._save_interaction(
            conversation_id=conversation_id,
            lead_id=lead.id,
            user_message=message,
            bot_response=ai_response,
            platform=platform,
            phone_number=phone_number,
            intent=intent,
            confidence=confidence,
            buying_signals=buying_signals,
            sentiment=sentiment,
            response_time=response_time,
            escalated=should_escalate,
            db=db
        )
        
        # Actualizar score del lead si hay señales de compra
        if buying_signals:
            await self._update_lead_score(lead, interaction, db)
            await self._trigger_sales_alert(lead, interaction)
        
        return {
            "response": ai_response,
            "conversation_id": conversation_id,
            "intent": intent,
            "confidence": confidence,
            "escalate": should_escalate,
            "buying_signals": buying_signals,
            "sentiment": sentiment,
            "lead_score": lead.score if lead else 0
        }

    def _classify_intent(self, message: str) -> Tuple[str, float]:
        """Clasifica la intención del mensaje usando keywords y patrones"""
        message_lower = message.lower()
        
        intent_scores = {}
        
        for intent, keywords in self.knowledge_base["intents"].items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            
            if score > 0:
                intent_scores[intent] = score / len(keywords)
        
        if not intent_scores:
            return "general", 0.3
        
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
        
        return best_intent, min(confidence, 1.0)

    async def _generate_ai_response(self, 
                                  message: str,
                                  lead: Lead,
                                  history: List[Dict],
                                  intent: str) -> str:
        """Genera respuesta usando OpenAI"""
        
        # Construir contexto personalizado
        context = self._build_enhanced_context(lead, history, intent)
        
        system_prompt = f"""
        Eres Sofia, una asistente de ventas experta en automatización empresarial. 

        Información del cliente:
        - Nombre: {lead.name if lead.name else 'Cliente'}
        - Empresa: {lead.company if lead.company else 'No especificada'}
        - Teléfono: {lead.phone}
        - Score actual: {lead.score}/100
        - Interés detectado: {intent}

        Productos que ofrecemos:
        {json.dumps(self.knowledge_base['products'], indent=2, ensure_ascii=False)}

        INSTRUCCIONES IMPORTANTES:
        1. Sé profesional pero cercana y empática
        2. Haz preguntas de calificación inteligentes
        3. Ofrece productos específicos basados en necesidades
        4. Si detectas interés en compra, agenda una demo
        5. Si no sabes algo, deriva con un especialista humano
        6. Mantén respuestas concisas (máximo 2-3 párrafos)
        7. Usa emojis moderadamente para ser más humana
        8. Si es la primera interacción, preséntate brevemente

        Contexto de la conversación:
        {context}
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=400,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error en OpenAI: {e}")
            return self._get_fallback_response(intent)

    def _get_fallback_response(self, intent: str) -> str:
        """Respuestas de respaldo cuando OpenAI falla"""
        fallbacks = {
            "greeting": "¡Hola! Soy Sofia, tu asistente de automatización. ¿En qué puedo ayudarte hoy? 😊",
            "product_inquiry": "Te puedo ayudar con información sobre nuestras soluciones de automatización CRM y chatbots IA. ¿Qué te interesa más?",
            "pricing": "Nuestros planes comienzan desde $149/mes. ¿Te gustaría que agendemos una llamada para revisar opciones específicas para tu empresa?",
            "demo": "¡Perfecto! Me encantaría mostrarte nuestras soluciones. ¿Cuándo tienes 30 minutos disponibles para una demo personalizada?",
            "support": "Entiendo tu consulta. Te voy a conectar con nuestro equipo técnico para resolver esto rápidamente.",
            "buying": "¡Excelente! Te voy a conectar con nuestro especialista en implementaciones para iniciar el proceso. 🚀"
        }
        
        return fallbacks.get(intent, "Gracias por contactarnos. Un especialista te atenderá pronto. ¿Hay algo específico en lo que pueda ayudarte mientras tanto?")

    def _should_escalate(self, message: str, intent: str, confidence: float, history: List) -> bool:
        """Determina si la conversación debe escalarse a un humano"""
        
        escalation_triggers = [
            confidence < 0.4,  # Baja confianza en intención
            intent == "support" and any(word in message.lower() for word in ["urgente", "problema grave", "no funciona"]),
            intent == "buying" and any(word in message.lower() for word in ["contratar", "comprar ahora", "empezar"]),
            len(history) > 10,  # Conversación muy larga
            "hablar con humano" in message.lower(),
            "gerente" in message.lower() or "supervisor" in message.lower()
        ]
        
        return any(escalation_triggers)

    async def _get_or_create_lead(self, phone_number: str, db: Session) -> Lead:
        """Obtiene o crea un lead basado en el número de teléfono"""
        lead = db.query(Lead).filter(Lead.phone == phone_number).first()
        
        if not lead:
            lead = Lead(
                phone=phone_number,
                source="chatbot",
                status="new",
                score=25,  # Score inicial para nuevos leads de chatbot
                created_at=datetime.utcnow()
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
        
        return lead

    async def _get_conversation_history(self, conversation_id: str, db: Session, limit: int = 8) -> List[Dict]:
        """Obtiene el historial de conversación reciente"""
        interactions = db.query(Interaction)\
            .filter(Interaction.conversation_id == conversation_id)\
            .order_by(Interaction.created_at.desc())\
            .limit(limit)\
            .all()
        
        history = []
        for interaction in reversed(interactions):  # Orden cronológico
            if interaction.user_message:
                history.append({"role": "user", "content": interaction.user_message})
            if interaction.bot_response:
                history.append({"role": "assistant", "content": interaction.bot_response})
        
        return history

    def _build_enhanced_context(self, lead: Lead, history: List[Dict], intent: str) -> str:
        """Construye contexto enriquecido para la IA"""
        context_parts = []
        
        if history:
            recent_messages = history[-4:] if len(history) > 4 else history
            context_parts.append("Conversación reciente:")
            for msg in recent_messages:
                context_parts.append(f"- {msg['role']}: {msg['content']}")
        else:
            context_parts.append("Primera interacción con este cliente")
        
        if lead.company:
            context_parts.append(f"Empresa del cliente: {lead.company}")
        
        if lead.score > 70:
            context_parts.append("🔥 LEAD CALIENTE - Alta probabilidad de conversión")
        elif lead.score > 40:
            context_parts.append("⚡ Lead prometedor - Necesita más calificación")
        
        return "\n".join(context_parts)

    def _detect_buying_signals(self, message: str) -> bool:
        """Detecta señales de compra más sofisticadas"""
        buying_signals = [
            'precio', 'costo', 'cuánto', 'presupuesto', 'comprar', 'contratar',
            'implementar', 'cuando podemos empezar', 'demo', 'prueba', 'reunión',
            'cotización', 'propuesta', 'plan', 'comenzar', 'iniciar',
            'me interesa', 'perfecto', 'exactamente lo que busco'
        ]
        
        message_lower = message.lower()
        signal_count = sum(1 for signal in buying_signals if signal in message_lower)
        
        # Múltiples señales o señales muy específicas
        return signal_count >= 1 and any(strong_signal in message_lower 
                                       for strong_signal in ['comprar', 'contratar', 'empezar', 'cotización'])

    async def _analyze_sentiment(self, message: str) -> float:
        """Análisis básico de sentiment (-1 a 1)"""
        positive_words = ['excelente', 'perfecto', 'genial', 'bueno', 'interesante', 'gracias']
        negative_words = ['malo', 'terrible', 'problema', 'error', 'no sirve', 'frustrante']
        
        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            return min(0.8, positive_count * 0.3)
        elif negative_count > positive_count:
            return max(-0.8, -negative_count * 0.3)
        else:
            return 0.0

    async def _save_interaction(self, **kwargs) -> Interaction:
        """Guarda la interacción en la base de datos"""
        interaction = Interaction(**kwargs)
        kwargs['db'].add(interaction)
        kwargs['db'].commit()
        kwargs['db'].refresh(interaction)
        return interaction

    async def _update_lead_score(self, lead: Lead, interaction: Interaction, db: Session):
        """Actualiza el score del lead basado en la interacción"""
        score_boost = 0
        
        if interaction.buying_signals_detected:
            score_boost += 15
        
        if interaction.intent_detected in ['pricing', 'demo', 'buying']:
            score_boost += 10
        
        if interaction.sentiment_score > 0.5:
            score_boost += 5
        
        lead.score = min(100, lead.score + score_boost)
        db.commit()

    async def _trigger_sales_alert(self, lead: Lead, interaction: Interaction):
        """Dispara alerta al equipo de ventas"""
        if lead.score > 70 or interaction.buying_signals_detected:
            alert_data = {
                "type": "hot_lead",
                "lead_id": lead.id,
                "lead_name": lead.name or lead.phone,
                "company": lead.company,
                "score": lead.score,
                "last_message": interaction.user_message,
                "intent": interaction.intent_detected,
                "platform": interaction.platform,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Aquí integrarías con Slack, Teams, email, etc.
            print(f"🚨 ALERTA DE VENTAS: {json.dumps(alert_data, indent=2)}")
            
            # TODO: Implementar notificaciones reales
            # await send_slack_alert(alert_data)
            # await send_email_alert(alert_data)