import openai
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from functools import lru_cache
from sqlalchemy.orm import Session
from ..core.config import settings
from ..models.interaction import Interaction, ConversationSummary, generate_conversation_id, SentimentLabel
from ..models.integration import Lead, LeadStatus
from ..services.lead_scoring import LeadScoringService

# Configurar logging
logger = logging.getLogger(__name__)

class AIAssistant:
    def __init__(self):
        self._validate_openai_config()
        self.knowledge_base = self._load_knowledge_base()
        self.scoring_service = LeadScoringService()
        self.model_config = self._initialize_model_config()
        self.conversation_cache = {}
        
    def _validate_openai_config(self):
        """Valida la configuración de OpenAI"""
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no está configurada en settings")
        
        openai.api_key = settings.OPENAI_API_KEY
        
        # Configurar base URL personalizada si existe
        if hasattr(settings, 'OPENAI_BASE_URL'):
            openai.api_base = settings.OPENAI_BASE_URL

    def _initialize_model_config(self) -> Dict[str, Any]:
        """Configuración flexible de modelos"""
        return {
            "primary_model": getattr(settings, 'AI_PRIMARY_MODEL', "gpt-4"),
            "fallback_model": getattr(settings, 'AI_FALLBACK_MODEL', "gpt-3.5-turbo"),
            "max_tokens": getattr(settings, 'AI_MAX_TOKENS', 400),
            "temperature": getattr(settings, 'AI_TEMPERATURE', 0.7),
            "timeout": getattr(settings, 'AI_TIMEOUT', 30),
            "max_retries": getattr(settings, 'AI_MAX_RETRIES', 3)
        }

    def _load_knowledge_base(self) -> Dict:
        """Carga la base de conocimiento de la empresa con mejor estructura"""
        return {
            "company_info": {
                "name": "Sofia AI",
                "description": "Sistema de automatización de ventas y marketing con IA",
                "industry": "SaaS - Automatización Empresarial",
                "founded_year": 2024
            },
            "products": [
                {
                    "id": "crm_automation",
                    "name": "Automatización CRM",
                    "price_range": "$299-$999/mes",
                    "features": ["Lead scoring automático", "Email automation", "Reporting avanzado", "Integración WhatsApp"],
                    "description": "Sistema completo de automatización de ventas y marketing",
                    "target_audience": ["Empresas B2B", "Equipos de ventas", "Agencias de marketing"],
                    "implementation_time": "1-2 semanas"
                },
                {
                    "id": "chatbot_premium",
                    "name": "Chatbot IA Premium", 
                    "price_range": "$199-$599/mes",
                    "features": ["Soporte 24/7", "Multi-idioma", "Integración WhatsApp/Telegram", "IA personalizada"],
                    "description": "Chatbot inteligente para atención al cliente y calificación de leads",
                    "target_audience": ["E-commerce", "Servicio al cliente", "Startups"],
                    "implementation_time": "3-5 días"
                },
                {
                    "id": "analytics_suite",
                    "name": "Analytics Suite",
                    "price_range": "$149-$399/mes", 
                    "features": ["Dashboard en tiempo real", "Reportes personalizados", "Métricas de conversión", "ROI tracking"],
                    "description": "Análisis completo de performance de ventas y marketing",
                    "target_audience": ["Equipos de marketing", "Data analysts", "Directores"],
                    "implementation_time": "1 semana"
                }
            ],
            "faqs": [
                {
                    "category": "implementación",
                    "question": "¿Cuánto tiempo toma la implementación?",
                    "answer": "La implementación básica toma entre 1-2 semanas. Para configuraciones avanzadas, hasta 4 semanas."
                },
                {
                    "category": "precios",
                    "question": "¿Ofrecen prueba gratuita?",
                    "answer": "Sí, ofrecemos 14 días de prueba gratuita sin compromiso y sin requerir tarjeta de crédito."
                },
                {
                    "category": "integración",
                    "question": "¿Qué integraciones soportan?",
                    "answer": "Soportamos HubSpot, Pipedrive, Salesforce, WhatsApp Business, Telegram, Meta Ads, Google Ads y más de 50 integraciones adicionales."
                },
                {
                    "category": "soporte",
                    "question": "¿Qué tipo de soporte ofrecen?",
                    "answer": "Ofrecemos soporte prioritario por chat, email y videollamadas. También tenemos documentación extensa y webinars semanales."
                }
            ],
            "intents": {
                "greeting": {
                    "keywords": ["hola", "buenos días", "buenas tardes", "hey", "hi", "hello", "saludos"],
                    "priority": 1,
                    "requires_followup": False
                },
                "product_inquiry": {
                    "keywords": ["producto", "servicio", "qué ofrecen", "información", "detalles", "solución", "software"],
                    "priority": 2,
                    "requires_followup": True
                },
                "pricing": {
                    "keywords": ["precio", "costo", "cuánto", "presupuesto", "tarifa", "plan", "subscriptión"],
                    "priority": 3,
                    "requires_followup": True
                },
                "demo": {
                    "keywords": ["demo", "demostración", "prueba", "ver funcionando", "presentación", "videollamada"],
                    "priority": 4,
                    "requires_followup": True
                },
                "support": {
                    "keywords": ["ayuda", "soporte", "problema", "error", "no funciona", "tengo una duda", "consultar"],
                    "priority": 5,
                    "requires_followup": False
                },
                "buying": {
                    "keywords": ["comprar", "contratar", "adquirir", "implementar", "empezar", "quiero comenzar", "ordenar"],
                    "priority": 6,
                    "requires_followup": True
                }
            },
            "response_templates": {
                "escalation": "He detectado que necesitas atención personalizada. Te voy a conectar con {specialist} quien te ayudará inmediatamente. 📞",
                "followup": "Perfecto, ¿te parece si agendamos una breve llamada para {purpose}? ¿Qué día y hora te viene mejor? 🗓️",
                "offline": "Estamos experimentando problemas técnicos momentáneos. Por favor, intenta nuevamente en unos minutos o contáctanos por email a soporte@sofiaai.com"
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
                "buying_signals": bool,
                "sentiment": float,
                "lead_score": float,
                "response_time_ms": int,
                "needs_followup": bool
            }
        """
        start_time = time.time()
        
        try:
            # Validaciones iniciales
            if not message or not message.strip():
                raise ValueError("Mensaje vacío recibido")
                
            if not db:
                raise ValueError("Sesión de base de datos requerida")

            # Obtener o crear lead
            lead = await self._get_or_create_lead(phone_number, db)
            
            # Generar conversation_id si no existe
            if not conversation_id:
                conversation_id = generate_conversation_id()
            
            # Obtener contexto de conversación (con cache)
            conversation_history = await self._get_conversation_history(conversation_id, db)
            
            # Clasificar intención del mensaje
            intent, confidence, intent_details = self._classify_intent_advanced(message)
            
            # Detectar señales de compra
            buying_signals, buying_confidence = self._detect_buying_signals_advanced(message)
            
            # Analizar sentiment mejorado
            sentiment_score, sentiment_label = await self._analyze_sentiment_advanced(message)
            
            # Detectar idioma
            detected_language = self._detect_language(message)
            
            # Generar respuesta con IA (con reintentos)
            ai_response = await self._generate_ai_response_with_retry(
                message, lead, conversation_history, intent, detected_language
            )
            
            # Determinar si escalar a humano
            should_escalate, escalation_reason = self._should_escalate_advanced(
                message, intent, confidence, conversation_history, sentiment_score
            )
            
            # Determinar si necesita follow-up
            needs_followup = self._requires_followup(intent, confidence, buying_signals)
            
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
                intent_detected=intent,
                confidence_score=confidence,
                buying_signals_detected=buying_signals,
                buying_signal_strength=buying_confidence,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                response_time_ms=response_time,
                escalated_to_human=should_escalate,
                escalation_reason=escalation_reason,
                language_detected=detected_language,
                db=db
            )
            
            # Actualizar score del lead
            score_updated = await self._update_lead_score_advanced(lead, interaction, db)
            
            # Disparar alertas si es necesario
            if buying_signals or should_escalate or score_updated:
                await self._trigger_advanced_alert(lead, interaction, should_escalate)
            
            # Actualizar cache de conversación
            self._update_conversation_cache(conversation_id, interaction)
            
            logger.info(f"Message processed - Intent: {intent}, Confidence: {confidence:.2f}, "
                       f"ResponseTime: {response_time}ms, LeadScore: {lead.score}")
            
            return {
                "response": ai_response,
                "conversation_id": conversation_id,
                "intent": intent,
                "confidence": confidence,
                "escalate": should_escalate,
                "escalation_reason": escalation_reason,
                "buying_signals": buying_signals,
                "buying_confidence": buying_confidence,
                "sentiment": sentiment_score,
                "sentiment_label": sentiment_label,
                "lead_score": lead.score if lead else 0,
                "response_time_ms": response_time,
                "needs_followup": needs_followup,
                "language": detected_language,
                "interaction_id": interaction.id
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return await self._get_error_response(message, e, conversation_id)

    def _classify_intent_advanced(self, message: str) -> Tuple[str, float, Dict]:
        """Clasificación avanzada de intención con múltiples factores"""
        message_lower = message.lower().strip()
        
        if not message_lower:
            return "unknown", 0.1, {"reason": "empty_message"}
        
        intent_scores = {}
        intent_details = {}
        
        for intent, config in self.knowledge_base["intents"].items():
            score = 0
            matched_keywords = []
            
            # Scoring por keywords
            for keyword in config["keywords"]:
                if keyword in message_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            # Bonus por matches múltiples
            if len(matched_keywords) > 1:
                score += len(matched_keywords) * 0.5
            
            # Bonus por patrones específicos
            pattern_bonus = self._check_intent_patterns(intent, message_lower)
            score += pattern_bonus
            
            if score > 0:
                # Normalizar score
                normalized_score = min(score / (len(config["keywords"]) + 2), 1.0)
                intent_scores[intent] = normalized_score
                intent_details[intent] = {
                    "keywords_matched": matched_keywords,
                    "pattern_bonus": pattern_bonus,
                    "priority": config["priority"]
                }
        
        if not intent_scores:
            return "general", 0.3, {"reason": "no_keywords_matched"}
        
        # Aplicar prioridades
        for intent, score in intent_scores.items():
            priority = self.knowledge_base["intents"][intent]["priority"]
            intent_scores[intent] = score * (1 + priority * 0.1)
        
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
        
        return best_intent, min(confidence, 1.0), intent_details.get(best_intent, {})

    def _check_intent_patterns(self, intent: str, message: str) -> float:
        """Verifica patrones específicos para cada intención"""
        patterns = {
            "pricing": [
                r"cuánto cuesta",
                r"precio de",
                r"costo de",
                r"vale el"
            ],
            "demo": [
                r"ver demo",
                r"probarlo",
                r"probar el",
                r"demostración"
            ],
            "buying": [
                r"quiero comprar",
                r"deseo contratar",
                r"empezar ya",
                r"comenzar ahora"
            ]
        }
        
        import re
        bonus = 0.0
        
        for pattern in patterns.get(intent, []):
            if re.search(pattern, message, re.IGNORECASE):
                bonus += 0.5
        
        return bonus

    async def _generate_ai_response_with_retry(self, 
                                             message: str,
                                             lead: Lead,
                                             history: List[Dict],
                                             intent: str,
                                             language: str = "es") -> str:
        """Genera respuesta con reintentos y fallback"""
        
        for attempt in range(self.model_config["max_retries"]):
            try:
                return await self._generate_ai_response_advanced(
                    message, lead, history, intent, language
                )
            except openai.error.RateLimitError:
                if attempt < self.model_config["max_retries"] - 1:
                    wait_time = (2 ** attempt) + 1  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Rate limit exceeded after retries")
                    return self._get_fallback_response(intent, language)
            except openai.error.APIConnectionError as e:
                logger.error(f"API connection error: {e}")
                if attempt < self.model_config["max_retries"] - 1:
                    time.sleep(1)
                    continue
                else:
                    return self._get_offline_response(language)
            except openai.error.InvalidRequestError as e:
                logger.error(f"Invalid request: {e}")
                return self._get_fallback_response(intent, language)
            except Exception as e:
                logger.error(f"Unexpected error in AI response: {e}")
                return self._get_fallback_response(intent, language)
        
        return self._get_fallback_response(intent, language)

    async def _generate_ai_response_advanced(self, 
                                           message: str,
                                           lead: Lead,
                                           history: List[Dict],
                                           intent: str,
                                           language: str) -> str:
        """Genera respuesta avanzada usando OpenAI"""
        
        # Construir contexto enriquecido
        context = self._build_enhanced_context(lead, history, intent, language)
        
        # Ajustar personalidad basada en el idioma
        personality = self._get_personality_by_language(language)
        
        system_prompt = f"""
        Eres Sofia, {personality['introduction']}

        INFORMACIÓN DEL CLIENTE:
        - Nombre: {lead.name if lead.name else 'Cliente'}
        - Empresa: {lead.company if lead.company else 'No especificada'}
        - Teléfono: {lead.phone}
        - Score actual: {lead.score}/100
        - Interés detectado: {intent}
        - Idioma preferido: {language}

        PRODUCTOS DISPONIBLES:
        {json.dumps(self.knowledge_base['products'], indent=2, ensure_ascii=False)}

        INSTRUCCIONES ESPECÍFICAS:
        {personality['instructions']}

        CONTEXTO DE CONVERSACIÓN:
        {context}

        {personality['closing']}
        """

        try:
            response = openai.ChatCompletion.create(
                model=self.model_config["primary_model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=self.model_config["max_tokens"],
                temperature=self.model_config["temperature"],
                presence_penalty=0.1,
                frequency_penalty=0.1,
                timeout=self.model_config["timeout"]
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _get_personality_by_language(self, language: str) -> Dict:
        """Define la personalidad del asistente por idioma"""
        personalities = {
            "es": {
                "introduction": "una asistente de ventas experta en automatización empresarial, cálida y profesional",
                "instructions": """1. Sé empática y cercana, pero mantén profesionalismo
2. Haz preguntas de calificación inteligentes
3. Ofrece soluciones específicas basadas en necesidades
4. Si detectas interés real, agenda una demo
5. Mantén respuestas concisas (máximo 2 párrafos)
6. Usa emojis moderadamente 😊
7. Adapta el lenguaje al cliente""",
                "closing": "Recuerda: El objetivo es ayudar, no vender agresivamente."
            },
            "en": {
                "introduction": "an expert sales assistant in business automation, warm and professional",
                "instructions": """1. Be empathetic and approachable, but maintain professionalism
2. Ask intelligent qualification questions  
3. Offer specific solutions based on needs
4. If you detect real interest, schedule a demo
5. Keep responses concise (max 2 paragraphs)
6. Use emojis moderately 😊
7. Adapt language to the client""",
                "closing": "Remember: The goal is to help, not to sell aggressively."
            },
            "pt": {
                "introduction": "uma assistente de vendas especialista em automação empresarial, calorosa e profissional",
                "instructions": """1. Seja empática e próxima, mas mantenha profissionalismo
2. Faça perguntas de qualificação inteligentes
3. Ofereça soluções específicas baseadas em necessidades  
4. Se detectar interesse real, agende uma demo
5. Mantenha respostas concisas (máximo 2 parágrafos)
6. Use emojis com moderação 😊
7. Adapte a linguagem ao cliente""",
                "closing": "Lembre-se: O objetivo é ajudar, não vender agressivamente."
            }
        }
        
        return personalities.get(language, personalities["es"])

    def _detect_language(self, text: str) -> str:
        """Detección básica de idioma"""
        # Implementación simple - en producción usaría langdetect
        text_lower = text.lower()
        
        spanish_indicators = ['hola', 'gracias', 'por favor', 'qué', 'cómo']
        english_indicators = ['hello', 'thanks', 'please', 'what', 'how']
        portuguese_indicators = ['olá', 'obrigado', 'por favor', 'que', 'como']
        
        spanish_count = sum(1 for word in spanish_indicators if word in text_lower)
        english_count = sum(1 for word in english_indicators if word in text_lower)  
        portuguese_count = sum(1 for word in portuguese_indicators if word in text_lower)
        
        if english_count > spanish_count and english_count > portuguese_count:
            return "en"
        elif portuguese_count > spanish_count and portuguese_count > english_count:
            return "pt"
        else:
            return "es"  # Default

    async def _analyze_sentiment_advanced(self, message: str) -> Tuple[float, str]:
        """Análisis de sentiment mejorado"""
        try:
            # Intentar con OpenAI para análisis más preciso
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Analiza el sentiment de este mensaje. Devuelve ONLY un número entre -1 (muy negativo) y 1 (muy positivo) y una etiqueta: positive, neutral, negative"},
                    {"role": "user", "content": f"Mensaje: '{message}'"}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            if "positive" in result.lower():
                return 0.7, SentimentLabel.POSITIVE
            elif "negative" in result.lower():
                return -0.7, SentimentLabel.NEGATIVE
            else:
                return 0.0, SentimentLabel.NEUTRAL
                
        except Exception as e:
            logger.warning(f"OpenAI sentiment analysis failed, using fallback: {e}")
            # Fallback a análisis por keywords
            return self._analyze_sentiment_fallback(message)

    def _analyze_sentiment_fallback(self, message: str) -> Tuple[float, str]:
        """Fallback para análisis de sentiment"""
        positive_words = ['excelente', 'perfecto', 'genial', 'bueno', 'interesante', 'gracias', 'fantástico', 'maravilloso']
        negative_words = ['malo', 'terrible', 'problema', 'error', 'no sirve', 'frustrante', 'horrible', 'pésimo']
        
        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            score = min(0.8, positive_count * 0.2)
            return score, SentimentLabel.POSITIVE
        elif negative_count > positive_count:
            score = max(-0.8, -negative_count * 0.2)
            return score, SentimentLabel.NEGATIVE
        else:
            return 0.0, SentimentLabel.NEUTRAL

    def _should_escalate_advanced(self, message: str, intent: str, confidence: float, 
                                history: List, sentiment: float) -> Tuple[bool, str]:
        """Determina si escalar a humano con razones específicas"""
        
        escalation_rules = [
            (confidence < 0.3, "Baja confianza en la intención del mensaje"),
            (intent == "support" and any(word in message.lower() for word in ["urgente", "problema grave", "no funciona", "error crítico"]), "Problema técnico urgente"),
            (intent == "buying" and any(word in message.lower() for word in ["contratar", "comprar ahora", "empezar hoy"]), "Lead caliente listo para comprar"),
            (len(history) > 15, "Conversación muy extensa que requiere atención humana"),
            ("hablar con humano" in message.lower() or "agente" in message.lower(), "Cliente solicita explícitamente atención humana"),
            (sentiment < -0.6, "Cliente frustrado que necesita atención especial"),
            ("gerente" in message.lower() or "supervisor" in message.lower(), "Solicitud de gerencia/supervisión")
        ]
        
        for condition, reason in escalation_rules:
            if condition:
                return True, reason
                
        return False, "No requiere escalación"

    def _requires_followup(self, intent: str, confidence: float, buying_signals: bool) -> bool:
        """Determina si la conversación necesita follow-up"""
        intent_config = self.knowledge_base["intents"].get(intent, {})
        return intent_config.get("requires_followup", False) and confidence > 0.5

    @lru_cache(maxsize=100)
    async def _get_conversation_history(self, conversation_id: str, db: Session, limit: int = 10) -> List[Dict]:
        """Obtiene historial de conversación con cache"""
        # Verificar cache primero
        if conversation_id in self.conversation_cache:
            cached_time, history = self.conversation_cache[conversation_id]
            if time.time() - cached_time < 300:  # 5 minutos de cache
                return history
        
        # Obtener de la base de datos
        interactions = db.query(Interaction)\
            .filter(Interaction.conversation_id == conversation_id)\
            .order_by(Interaction.created_at.desc())\
            .limit(limit)\
            .all()
        
        history = []
        for interaction in reversed(interactions):
            if interaction.user_message:
                history.append({"role": "user", "content": interaction.user_message})
            if interaction.bot_response:
                history.append({"role": "assistant", "content": interaction.bot_response})
        
        # Actualizar cache
        self.conversation_cache[conversation_id] = (time.time(), history)
        
        return history

    def _update_conversation_cache(self, conversation_id: str, interaction: Interaction):
        """Actualiza el cache de conversación con nueva interacción"""
        if conversation_id in self.conversation_cache:
            cached_time, history = self.conversation_cache[conversation_id]
            # Agregar nueva interacción al historial
            if interaction.user_message:
                history.append({"role": "user", "content": interaction.user_message})
            if interaction.bot_response:
                history.append({"role": "assistant", "content": interaction.bot_response})
            
            # Mantener límite de historial
            if len(history) > 20:
                history = history[-20:]
            
            self.conversation_cache[conversation_id] = (time.time(), history)

    async def _get_or_create_lead(self, phone_number: str, db: Session) -> Lead:
        """Obtiene o crea un lead con validación mejorada"""
        try:
            lead = db.query(Lead).filter(Lead.phone == phone_number).first()
            
            if not lead:
                lead = Lead(
                    phone=phone_number,
                    source="chatbot",
                    status=LeadStatus.COLD,
                    score=25,  # Score inicial para nuevos leads de chatbot
                    first_interaction=datetime.utcnow(),
                    last_interaction=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                db.add(lead)
                db.commit()
                db.refresh(lead)
                logger.info(f"New lead created: {lead.id}")
            else:
                # Actualizar última interacción
                lead.last_interaction = datetime.utcnow()
                db.commit()
            
            return lead
            
        except Exception as e:
            logger.error(f"Error getting/creating lead: {e}")
            raise

    async def _update_lead_score_advanced(self, lead: Lead, interaction: Interaction, db: Session) -> bool:
        """Actualización avanzada del score del lead"""
        try:
            score_boost = 0
            
            # Factores de scoring
            if interaction.buying_signals_detected:
                score_boost += min(20, interaction.buying_signal_strength * 25)
            
            if interaction.intent_detected in ['pricing', 'demo', 'buying']:
                score_boost += 12
            
            if interaction.confidence_score > 0.8:
                score_boost += 8
            
            if interaction.sentiment_score > 0.5:
                score_boost += 5
            elif interaction.sentiment_score < -0.3:
                score_boost -= 5  # Penalizar sentiment negativo
            
            # Bonus por engagement (muchas interacciones)
            interaction_count = db.query(Interaction).filter(Interaction.lead_id == lead.id).count()
            if interaction_count > 5:
                score_boost += min(10, (interaction_count - 5) * 2)
            
            # Aplicar cambios
            old_score = lead.score
            lead.score = max(0, min(100, lead.score + score_boost))
            
            # Actualizar status basado en score
            if lead.score >= 80:
                lead.status = LeadStatus.HOT
            elif lead.score >= 50:
                lead.status = LeadStatus.WARM
            elif lead.score >= 25:
                lead.status = LeadStatus.COLD
            
            db.commit()
            
            if old_score != lead.score:
                logger.info(f"Lead {lead.id} score updated: {old_score} -> {lead.score}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error updating lead score: {e}")
            return False

    async def _trigger_advanced_alert(self, lead: Lead, interaction: Interaction, escalated: bool):
        """Sistema de alertas avanzado"""
        try:
            alert_data = {
                "lead_id": lead.id,
                "lead_name": lead.name or lead.phone,
                "company": lead.company,
                "score": lead.score,
                "status": lead.status,
                "last_message": interaction.user_message,
                "intent": interaction.intent_detected,
                "buying_signals": interaction.buying_signals_detected,
                "sentiment": interaction.sentiment_score,
                "platform": interaction.platform,
                "escalated": escalated,
                "interaction_id": interaction.id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Determinar tipo de alerta
            if lead.score >= 80:
                alert_data["type"] = "hot_lead"
                alert_data["priority"] = "high"
            elif escalated:
                alert_data["type"] = "escalation_required"
                alert_data["priority"] = "high"
            elif interaction.buying_signals_detected:
                alert_data["type"] = "buying_signals"
                alert_data["priority"] = "medium"
            else:
                alert_data["type"] = "lead_activity"
                alert_data["priority"] = "low"
            
            # Log de alerta (en producción integrar con Slack/Teams/Email)
            logger.info(f"ALERT: {json.dumps(alert_data, indent=2)}")
            
            # TODO: Implementar integraciones reales
            # await self._send_slack_alert(alert_data)
            # await self._send_email_alert(alert_data)
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")

    def _get_fallback_response(self, intent: str, language: str = "es") -> str:
        """Respuestas de respaldo por idioma"""
        fallbacks = {
            "es": {
                "greeting": "¡Hola! Soy Sofia, tu asistente de automatización. ¿En qué puedo ayudarte hoy? 😊",
                "product_inquiry": "Te puedo ayudar con información sobre nuestras soluciones de automatización CRM y chatbots IA. ¿Qué te interesa más?",
                "pricing": "Nuestros planes comienzan desde $149/mes. ¿Te gustaría que agendemos una llamada para revisar opciones específicas para tu empresa?",
                "demo": "¡Perfecto! Me encantaría mostrarte nuestras soluciones. ¿Cuándo tienes 30 minutos disponibles para una demo personalizada?",
                "support": "Entiendo tu consulta. Te voy a conectar con nuestro equipo técnico para resolver esto rápidamente.",
                "buying": "¡Excelente! Te voy a conectar con nuestro especialista en implementaciones para iniciar el proceso. 🚀",
                "general": "Gracias por contactarnos. Un especialista te atenderá pronto. ¿Hay algo específico en lo que pueda ayudarte mientras tanto?"
            },
            "en": {
                "greeting": "Hello! I'm Sofia, your automation assistant. How can I help you today? 😊",
                "product_inquiry": "I can help you with information about our CRM automation and AI chatbot solutions. What interests you most?",
                "pricing": "Our plans start from $149/month. Would you like to schedule a call to review specific options for your business?",
                "demo": "Perfect! I'd love to show you our solutions. When do you have 30 minutes available for a personalized demo?",
                "support": "I understand your query. I'll connect you with our technical team to resolve this quickly.",
                "buying": "Excellent! I'll connect you with our implementation specialist to start the process. 🚀",
                "general": "Thank you for contacting us. A specialist will assist you shortly. Is there anything specific I can help you with in the meantime?"
            },
            "pt": {
                "greeting": "Olá! Sou Sofia, sua assistente de automação. Como posso ajudá-lo hoje? 😊",
                "product_inquiry": "Posso ajudá-lo com informações sobre nossas soluções de automação de CRM e chatbots de IA. O que mais lhe interessa?",
                "pricing": "Nossos planos começam em $149/mês. Gostaria de agendar uma chamada para revisar opções específicas para sua empresa?",
                "demo": "Perfeito! Adoraria mostrar nossas soluções. Quando você tem 30 minutos disponíveis para uma demonstração personalizada?",
                "support": "Entendo sua consulta. Vou conectá-lo com nossa equipe técnica para resolver isso rapidamente.",
                "buying": "Excelente! Vou conectá-lo com nosso especialista em implementação para iniciar o processo. 🚀",
                "general": "Obrigado por entrar em contato. Um especialista irá atendê-lo em breve. Há algo específico com que eu possa ajudá-lo enquanto isso?"
            }
        }
        
        lang_fallbacks = fallbacks.get(language, fallbacks["es"])
        return lang_fallbacks.get(intent, lang_fallbacks["general"])

    def _get_offline_response(self, language: str) -> str:
        """Respuesta cuando el sistema está offline"""
        offline_responses = {
            "es": "Estamos experimentando problemas técnicos momentáneos. Por favor, intenta nuevamente en unos minutos o contáctanos por email a soporte@sofiaai.com",
            "en": "We're experiencing temporary technical issues. Please try again in a few minutes or contact us by email at support@sofiaai.com",
            "pt": "Estamos enfrentando problemas técnicos temporários. Por favor, tente novamente em alguns minutos ou entre em contato conosco por email em support@sofiaai.com"
        }
        return offline_responses.get(language, offline_responses["es"])

    async def _get_error_response(self, message: str, error: Exception, conversation_id: str) -> Dict:
        """Respuesta de error estandarizada"""
        logger.error(f"Error processing message: {message}, Error: {error}")
        
        return {
            "response": "Lo siento, estoy experimentando problemas técnicos momentáneos. Por favor, intenta nuevamente en unos minutos.",
            "conversation_id": conversation_id or generate_conversation_id(),
            "intent": "error",
            "confidence": 0.0,
            "escalate": False,
            "escalation_reason": "Error técnico",
            "buying_signals": False,
            "buying_confidence": 0.0,
            "sentiment": 0.0,
            "sentiment_label": "neutral",
            "lead_score": 0,
            "response_time_ms": 0,
            "needs_followup": False,
            "language": "es",
            "interaction_id": None,
            "error": str(error)
        }

    async def _save_interaction(self, **kwargs) -> Interaction:
        """Guarda la interacción en la base de datos con manejo de errores"""
        try:
            interaction = Interaction(**{k: v for k, v in kwargs.items() if k != 'db'})
            kwargs['db'].add(interaction)
            kwargs['db'].commit()
            kwargs['db'].refresh(interaction)
            return interaction
        except Exception as e:
            logger.error(f"Error saving interaction: {e}")
            kwargs['db'].rollback()
            raise

    def get_performance_metrics(self) -> Dict:
        """Obtiene métricas de performance del asistente"""
        return {
            "cache_size": len(self.conversation_cache),
            "model_config": self.model_config,
            "knowledge_base_stats": {
                "products": len(self.knowledge_base["products"]),
                "faqs": len(self.knowledge_base["faqs"]),
                "intents": len(self.knowledge_base["intents"])
            }
        }

# Función de utilidad para crear instancia del asistente
def create_ai_assistant() -> AIAssistant:
    """Factory function para crear instancia de AIAssistant"""
    return AIAssistant()