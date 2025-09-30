import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from openai import OpenAIError, RateLimitError, APIConnectionError, InvalidRequestError
import openai

from ..models.integration import Lead, LeadStatus, Interaction
from ..models.interaction import ConversationSummary, MessageType, Platform
from ..core.config import settings

logger = logging.getLogger(__name__)

class LeadScoringService:
    """Servicio avanzado de scoring de leads con machine learning y análisis de comportamiento"""
    
    def __init__(self):
        self._validate_openai_config()
        self.scoring_weights = self._load_scoring_weights()
        self.score_thresholds = self._load_score_thresholds()
        self.ai_cache = {}  # Cache para análisis de IA
        self.cache_ttl = 3600  # 1 hora de cache
        
    def _validate_openai_config(self):
        """Valida la configuración de OpenAI"""
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no está configurada en settings")
        
        openai.api_key = settings.OPENAI_API_KEY
        
        # Configurar base URL personalizada si existe
        if hasattr(settings, 'OPENAI_BASE_URL'):
            openai.api_base = settings.OPENAI_BASE_URL

    def _load_scoring_weights(self) -> Dict[str, float]:
        """Carga los pesos para cada categoría de scoring"""
        return {
            "demographic": 0.25,      # Información del perfil
            "behavioral": 0.30,       # Comportamiento e interacciones
            "engagement": 0.20,       # Frecuencia y recencia
            "conversation_ai": 0.15,  # Análisis de conversaciones con IA
            "external_signals": 0.10  # Señales externas (campañas, etc.)
        }

    def _load_score_thresholds(self) -> Dict[str, Dict]:
        """Carga los thresholds para cada status de lead"""
        return {
            "cold": {"min": 0, "max": 39, "color": "#6B7280", "priority": 1},
            "warm": {"min": 40, "max": 69, "color": "#F59E0B", "priority": 2},
            "hot": {"min": 70, "max": 89, "color": "#EF4444", "priority": 3},
            "qualified": {"min": 90, "max": 100, "color": "#10B981", "priority": 4}
        }

    async def calculate_lead_score(self, lead: Lead, db: Session, use_cache: bool = True) -> Dict[str, Any]:
        """
        Calcula el puntaje completo del lead con análisis detallado
        
        Returns:
            Dict con score total, scores por categoría, y metadatos
        """
        try:
            # Verificar cache primero
            cache_key = f"lead_score_{lead.id}"
            if use_cache and cache_key in self.ai_cache:
                cached_data, timestamp = self.ai_cache[cache_key]
                if (datetime.utcnow() - timestamp).total_seconds() < self.cache_ttl:
                    logger.debug(f"Retornando score desde cache para lead {lead.id}")
                    return cached_data

            # Obtener interacciones recientes del lead
            interactions = await self._get_lead_interactions(lead.id, db)
            conversations = await self._get_lead_conversations(lead.id, db)

            # Calcular scores por categoría
            demographic_score = await self._calculate_demographic_score(lead)
            behavioral_score = await self._calculate_behavioral_score(interactions, conversations)
            engagement_score = await self._calculate_engagement_score(interactions, lead)
            conversation_ai_score = await self._calculate_conversation_ai_score(conversations, interactions)
            external_signals_score = await self._calculate_external_signals_score(lead, db)

            # Aplicar pesos ponderados
            weighted_scores = {
                "demographic": demographic_score * self.scoring_weights["demographic"],
                "behavioral": behavioral_score * self.scoring_weights["behavioral"],
                "engagement": engagement_score * self.scoring_weights["engagement"],
                "conversation_ai": conversation_ai_score * self.scoring_weights["conversation_ai"],
                "external_signals": external_signals_score * self.scoring_weights["external_signals"]
            }

            total_score = sum(weighted_scores.values())
            total_score = min(100.0, max(0.0, total_score))

            # Determinar status y nivel de confianza
            lead_status, confidence = self._determine_lead_status(total_score, weighted_scores)

            result = {
                "total_score": round(total_score, 2),
                "weighted_scores": {k: round(v, 2) for k, v in weighted_scores.items()},
                "raw_scores": {
                    "demographic": demographic_score,
                    "behavioral": behavioral_score,
                    "engagement": engagement_score,
                    "conversation_ai": conversation_ai_score,
                    "external_signals": external_signals_score
                },
                "lead_status": lead_status,
                "confidence_level": confidence,
                "score_breakdown": await self._generate_score_breakdown(lead, interactions, conversations),
                "last_calculated": datetime.utcnow().isoformat(),
                "improvement_opportunities": await self._identify_improvement_opportunities(weighted_scores, lead)
            }

            # Actualizar cache
            if use_cache:
                self.ai_cache[cache_key] = (result, datetime.utcnow())

            return result

        except Exception as e:
            logger.error(f"Error calculando score para lead {lead.id}: {e}")
            return self._get_error_score(lead.id, str(e))

    async def _get_lead_interactions(self, lead_id: int, db: Session, days: int = 90) -> List[Interaction]:
        """Obtiene interacciones recientes del lead"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            interactions = db.query(Interaction)\
                .filter(
                    Interaction.lead_id == lead_id,
                    Interaction.created_at >= since_date
                )\
                .order_by(Interaction.created_at.desc())\
                .all()
            
            return interactions
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo interacciones para lead {lead_id}: {e}")
            return []

    async def _get_lead_conversations(self, lead_id: int, db: Session) -> List[ConversationSummary]:
        """Obtiene resúmenes de conversaciones del lead"""
        try:
            conversations = db.query(ConversationSummary)\
                .filter(ConversationSummary.lead_id == lead_id)\
                .order_by(ConversationSummary.started_at.desc())\
                .all()
            
            return conversations
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo conversaciones para lead {lead_id}: {e}")
            return []

    async def _calculate_demographic_score(self, lead: Lead) -> float:
        """Calcula score basado en información demográfica y de perfil"""
        score = 0.0
        max_score = 100.0
        
        # 1. Cargo/título (0-25 puntos)
        title_score = self._score_job_title(lead.job_title)
        score += title_score
        
        # 2. Tamaño de empresa (0-20 puntos)
        company_score = self._score_company(lead.company)
        score += company_score
        
        # 3. Industria/segmento (0-15 puntos)
        industry_score = self._score_industry(lead.company)
        score += industry_score
        
        # 4. Presupuesto (0-20 puntos)
        budget_score = self._score_budget(lead.budget_range)
        score += budget_score
        
        # 5. Timeline de compra (0-20 puntos)
        timeline_score = self._score_timeline(lead.timeline)
        score += timeline_score
        
        return min(max_score, score)

    def _score_job_title(self, job_title: Optional[str]) -> float:
        """Score basado en el cargo/título del lead"""
        if not job_title:
            return 0.0
        
        title_lower = job_title.lower()
        
        title_scores = {
            "executive": 25,  # CEO, CTO, Director, VP, President
            "management": 20, # Manager, Head of, Director
            "technical": 15,  # Engineer, Developer, Analyst
            "operations": 10, # Coordinator, Specialist
            "other": 5        # Otros cargos
        }
        
        # Detectar nivel del cargo
        executive_keywords = ["ceo", "cto", "cfo", "president", "vp", "director", "founder"]
        management_keywords = ["manager", "head of", "lead", "supervisor"]
        technical_keywords = ["engineer", "developer", "analyst", "architect", "data scientist"]
        operations_keywords = ["coordinator", "specialist", "assistant", "representative"]
        
        if any(keyword in title_lower for keyword in executive_keywords):
            return title_scores["executive"]
        elif any(keyword in title_lower for keyword in management_keywords):
            return title_scores["management"]
        elif any(keyword in title_lower for keyword in technical_keywords):
            return title_scores["technical"]
        elif any(keyword in title_lower for keyword in operations_keywords):
            return title_scores["operations"]
        else:
            return title_scores["other"]

    def _score_company(self, company: Optional[str]) -> float:
        """Score basado en la empresa del lead"""
        if not company:
            return 0.0
        
        # En producción, esto se integraría con una base de datos de empresas
        # Por ahora, puntuación básica basada en indicadores de tamaño
        company_lower = company.lower()
        
        # Indicadores de empresas grandes
        large_company_indicators = ["inc", "corp", "corporation", "ltd", "group", "global"]
        if any(indicator in company_lower for indicator in large_company_indicators):
            return 20.0
        
        # Indicadores de startups/scaleups
        startup_indicators = ["tech", "software", "labs", "ventures", "startup"]
        if any(indicator in company_lower for indicator in startup_indicators):
            return 15.0
        
        return 10.0  # Empresa pequeña/mediana

    def _score_industry(self, company: Optional[str]) -> float:
        """Score basado en la industria (inferida de la empresa)"""
        if not company:
            return 0.0
        
        # Mapeo de industrias de alto valor
        high_value_industries = {
            "tech": ["tech", "software", "saas", "it", "technology", "cloud"],
            "finance": ["bank", "financial", "insurance", "investment", "fintech"],
            "healthcare": ["health", "medical", "hospital", "pharma", "biotech"],
            "enterprise": ["enterprise", "corporation", "global", "international"]
        }
        
        company_lower = company.lower()
        
        for industry, keywords in high_value_industries.items():
            if any(keyword in company_lower for keyword in keywords):
                return 15.0
        
        return 8.0  # Industria estándar

    def _score_budget(self, budget_range: Optional[str]) -> float:
        """Score basado en el rango de presupuesto"""
        if not budget_range:
            return 0.0
        
        budget_scores = {
            'less_than_1k': 5,
            '1k_to_5k': 10,
            '5k_to_10k': 15,
            '10k_to_25k': 20,
            'more_than_25k': 25
        }
        
        return budget_scores.get(budget_range, 0)

    def _score_timeline(self, timeline: Optional[str]) -> float:
        """Score basado en el timeline de compra"""
        if not timeline:
            return 0.0
        
        timeline_scores = {
            'immediate': 20,      # 0-1 mes
            'short_term': 15,     # 1-3 meses
            'medium_term': 10,    # 3-6 meses
            'long_term': 5,       # 6+ meses
            'exploring': 2        # Solo explorando
        }
        
        return timeline_scores.get(timeline, 0)

    async def _calculate_behavioral_score(self, interactions: List[Interaction], 
                                        conversations: List[ConversationSummary]) -> float:
        """Calcula score basado en comportamiento e interacciones"""
        if not interactions:
            return 0.0
        
        score = 0.0
        max_score = 100.0
        
        # 1. Score por tipo de interacción (0-40 puntos)
        interaction_score = self._score_interaction_types(interactions)
        score += interaction_score
        
        # 2. Score por intenciones detectadas (0-30 puntos)
        intent_score = self._score_detected_intents(interactions)
        score += intent_score
        
        # 3. Score por señales de compra (0-20 puntos)
        buying_signals_score = self._score_buying_signals(interactions, conversations)
        score += buying_signals_score
        
        # 4. Score por conversiones (0-10 puntos)
        conversion_score = self._score_conversions(conversations)
        score += conversion_score
        
        return min(max_score, score)

    def _score_interaction_types(self, interactions: List[Interaction]) -> float:
        """Score basado en tipos de interacción"""
        score = 0.0
        
        interaction_weights = {
            "website_visit": 1,
            "form_submission": 5,
            "content_download": 8,
            "email_engagement": 3,
            "demo_request": 15,
            "pricing_inquiry": 12,
            "product_inquiry": 10,
            "support_request": 2
        }
        
        for interaction in interactions:
            intent = interaction.intent_detected
            if intent in interaction_weights:
                score += interaction_weights[intent]
        
        return min(40.0, score)

    def _score_detected_intents(self, interactions: List[Interaction]) -> float:
        """Score basado en intenciones detectadas"""
        high_value_intents = ["buying", "demo", "pricing", "implementation"]
        medium_value_intents = ["product_inquiry", "trial", "consultation"]
        
        high_intent_count = sum(1 for i in interactions if i.intent_detected in high_value_intents)
        medium_intent_count = sum(1 for i in interactions if i.intent_detected in medium_value_intents)
        
        return min(30.0, (high_intent_count * 5) + (medium_intent_count * 2))

    def _score_buying_signals(self, interactions: List[Interaction], 
                            conversations: List[ConversationSummary]) -> float:
        """Score basado en señales de compra detectadas"""
        buying_signals_count = sum(1 for i in interactions if i.buying_signals_detected)
        
        # Señales en conversaciones
        conversation_signals = sum(1 for c in conversations if c.conversion_achieved)
        
        return min(20.0, (buying_signals_count * 3) + (conversation_signals * 5))

    def _score_conversions(self, conversations: List[ConversationSummary]) -> float:
        """Score basado en conversiones logradas"""
        conversions = sum(1 for c in conversations if c.conversion_achieved)
        return min(10.0, conversions * 10)

    async def _calculate_engagement_score(self, interactions: List[Interaction], lead: Lead) -> float:
        """Calcula score basado en engagement (frecuencia, recencia, duración)"""
        if not interactions:
            return 0.0
        
        score = 0.0
        max_score = 100.0
        
        # 1. Frecuencia de interacciones (0-30 puntos)
        frequency_score = self._calculate_frequency_score(interactions)
        score += frequency_score
        
        # 2. Recencia de interacciones (0-25 puntos)
        recency_score = self._calculate_recency_score(interactions, lead)
        score += recency_score
        
        # 3. Duración del engagement (0-20 puntos)
        duration_score = self._calculate_duration_score(interactions, lead)
        score += duration_score
        
        # 4. Consistencia del engagement (0-25 puntos)
        consistency_score = self._calculate_consistency_score(interactions)
        score += consistency_score
        
        return min(max_score, score)

    def _calculate_frequency_score(self, interactions: List[Interaction]) -> float:
        """Calcula score basado en frecuencia de interacciones"""
        if len(interactions) <= 1:
            return 0.0
        
        # Interacciones en los últimos 30 días
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        recent_interactions = [i for i in interactions if i.created_at >= recent_cutoff]
        
        frequency = len(recent_interactions)
        
        if frequency >= 10:
            return 30.0
        elif frequency >= 5:
            return 20.0
        elif frequency >= 3:
            return 15.0
        elif frequency >= 1:
            return 10.0
        else:
            return 0.0

    def _calculate_recency_score(self, interactions: List[Interaction], lead: Lead) -> float:
        """Calcula score basado en recencia de interacciones"""
        if not interactions:
            return 0.0
        
        latest_interaction = max(interactions, key=lambda x: x.created_at)
        days_since_last = (datetime.utcnow() - latest_interaction.created_at).days
        
        if days_since_last == 0:
            return 25.0
        elif days_since_last <= 1:
            return 20.0
        elif days_since_last <= 3:
            return 15.0
        elif days_since_last <= 7:
            return 10.0
        elif days_since_last <= 14:
            return 5.0
        else:
            return 0.0

    def _calculate_duration_score(self, interactions: List[Interaction], lead: Lead) -> float:
        """Calcula score basado en duración del engagement"""
        if len(interactions) <= 1:
            return 0.0
        
        first_interaction = min(interactions, key=lambda x: x.created_at)
        engagement_duration = (datetime.utcnow() - first_interaction.created_at).days
        
        if engagement_duration >= 90:  # 3+ meses
            return 20.0
        elif engagement_duration >= 30:  # 1-3 meses
            return 15.0
        elif engagement_duration >= 14:  # 2 semanas - 1 mes
            return 10.0
        elif engagement_duration >= 7:   # 1-2 semanas
            return 5.0
        else:
            return 0.0

    def _calculate_consistency_score(self, interactions: List[Interaction]) -> float:
        """Calcula score basado en consistencia del engagement"""
        if len(interactions) <= 2:
            return 0.0
        
        # Agrupar interacciones por semana
        weekly_interactions = {}
        for interaction in interactions:
            week_key = interaction.created_at.strftime("%Y-%U")
            weekly_interactions[week_key] = weekly_interactions.get(week_key, 0) + 1
        
        # Calcular consistencia (semanas con al menos 1 interacción)
        active_weeks = sum(1 for count in weekly_interactions.values() if count >= 1)
        total_weeks = len(weekly_interactions)
        
        if total_weeks == 0:
            return 0.0
        
        consistency_ratio = active_weeks / total_weeks
        
        if consistency_ratio >= 0.8:  # 80%+ de consistencia
            return 25.0
        elif consistency_ratio >= 0.6:
            return 15.0
        elif consistency_ratio >= 0.4:
            return 10.0
        else:
            return 5.0

    async def _calculate_conversation_ai_score(self, conversations: List[ConversationSummary], 
                                             interactions: List[Interaction]) -> float:
        """Calcula score usando IA para análisis de conversaciones"""
        if not conversations and not interactions:
            return 0.0
        
        try:
            # Combinar contenido de conversaciones e interacciones para análisis
            analysis_text = await self._prepare_analysis_text(conversations, interactions)
            
            if not analysis_text.strip():
                return 0.0
            
            # Usar OpenAI para análisis de intención y sentimiento
            ai_score = await self._get_ai_analysis_score(analysis_text)
            return min(100.0, ai_score * 100)  # Convertir a porcentaje
            
        except Exception as e:
            logger.error(f"Error en análisis de IA: {e}")
            return 0.0

    async def _prepare_analysis_text(self, conversations: List[ConversationSummary], 
                                   interactions: List[Interaction]) -> str:
        """Prepara texto para análisis de IA"""
        text_parts = []
        
        # Agregar resúmenes de conversaciones
        for conversation in conversations:
            if conversation.summary:
                text_parts.append(f"Conversation: {conversation.summary}")
            if conversation.key_points:
                text_parts.append(f"Key points: {', '.join(conversation.key_points)}")
        
        # Agregar intenciones de interacciones recientes
        recent_interactions = sorted(interactions, key=lambda x: x.created_at, reverse=True)[:10]
        for interaction in recent_interactions:
            if interaction.user_message:
                text_parts.append(f"User: {interaction.user_message}")
            if interaction.intent_detected:
                text_parts.append(f"Detected intent: {interaction.intent_detected}")
        
        return " ".join(text_parts)

    async def _get_ai_analysis_score(self, text: str, max_retries: int = 3) -> float:
        """Obtiene score de análisis de IA con reintentos"""
        for attempt in range(max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": """Analiza el texto y evalúa el nivel de interés de compra del lead. 
                            Considera: intención de compra, urgencia, nivel de engagement, y señales positivas.
                            Responde SOLO con un número entre 0.0 y 1.0, donde:
                            0.0 = Sin interés, 0.5 = Interés moderado, 1.0 = Máximo interés de compra."""
                        },
                        {
                            "role": "user",
                            "content": f"Texto a analizar: {text[:3000]}"  # Limitar tamaño
                        }
                    ],
                    max_tokens=50,
                    temperature=0.1  # Baja temperatura para respuestas consistentes
                )
                
                score_text = response.choices[0].message.content.strip()
                
                # Extraer número flotante de la respuesta
                try:
                    score = float(score_text)
                    return max(0.0, min(1.0, score))  # Asegurar rango 0-1
                except ValueError:
                    # Fallback: buscar número en el texto
                    import re
                    numbers = re.findall(r"0\.\d+", score_text)
                    if numbers:
                        return float(numbers[0])
                    return 0.5  # Valor por defecto si no se puede parsear
                
            except RateLimitError:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff
                    logger.warning(f"Rate limit, reintentando en {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("Rate limit después de múltiples reintentos")
                    return 0.5
                    
            except (APIConnectionError, InvalidRequestError) as e:
                logger.error(f"Error de API de OpenAI: {e}")
                return 0.5
                
            except Exception as e:
                logger.error(f"Error inesperado en análisis de IA: {e}")
                return 0.5
        
        return 0.5

    async def _calculate_external_signals_score(self, lead: Lead, db: Session) -> float:
        """Calcula score basado en señales externas"""
        score = 0.0
        
        # 1. Score por fuente del lead (0-20 puntos)
        source_score = self._score_lead_source(lead.source)
        score += source_score
        
        # 2. Score por campañas activas (0-15 puntos)
        campaign_score = await self._score_campaign_participation(lead, db)
        score += campaign_score
        
        # 3. Score por integraciones externas (0-15 puntos)
        integration_score = self._score_external_integrations(lead)
        score += integration_score
        
        return min(50.0, score)

    def _score_lead_source(self, source: Optional[str]) -> float:
        """Score basado en la fuente del lead"""
        source_scores = {
            "referral": 20,
            "website_direct": 15,
            "organic_search": 12,
            "paid_ads": 10,
            "social_media": 8,
            "cold_outreach": 5
        }
        
        return source_scores.get(source, 5)

    async def _score_campaign_participation(self, lead: Lead, db: Session) -> float:
        """Score basado en participación en campañas"""
        # En producción, esto se integraría con el sistema de campañas
        # Por ahora, puntuación básica
        return 0.0  # Placeholder

    def _score_external_integrations(self, lead: Lead) -> float:
        """Score basado en integraciones externas (HubSpot, etc.)"""
        score = 0.0
        
        # Lead sincronizado con HubSpot
        if lead.hubspot_id:
            score += 5
        
        # Lead sincronizado con otros CRMs
        if lead.pipedrive_id or lead.salesforce_id:
            score += 5
        
        # Lead con datos de atribución completos
        if lead.utm_campaign and lead.source:
            score += 5
        
        return score

    def _determine_lead_status(self, total_score: float, weighted_scores: Dict[str, float]) -> Tuple[str, str]:
        """Determina el status del lead y nivel de confianza"""
        # Determinar status basado en score total
        for status, thresholds in self.score_thresholds.items():
            if thresholds["min"] <= total_score <= thresholds["max"]:
                lead_status = status
                break
        else:
            lead_status = "cold"  # Default
        
        # Calcular nivel de confianza basado en consistencia de scores
        score_variance = max(weighted_scores.values()) - min(weighted_scores.values())
        
        if score_variance <= 10:
            confidence = "high"
        elif score_variance <= 20:
            confidence = "medium"
        else:
            confidence = "low"
        
        return lead_status, confidence

    async def _generate_score_breakdown(self, lead: Lead, interactions: List[Interaction], 
                                      conversations: List[ConversationSummary]) -> Dict[str, Any]:
        """Genera un breakdown detallado del score"""
        return {
            "demographic_breakdown": {
                "job_title_score": self._score_job_title(lead.job_title),
                "company_score": self._score_company(lead.company),
                "industry_score": self._score_industry(lead.company),
                "budget_score": self._score_budget(lead.budget_range),
                "timeline_score": self._score_timeline(lead.timeline)
            },
            "behavioral_breakdown": {
                "interaction_count": len(interactions),
                "high_value_intents": sum(1 for i in interactions if i.intent_detected in ["buying", "demo", "pricing"]),
                "buying_signals": sum(1 for i in interactions if i.buying_signals_detected),
                "conversions": sum(1 for c in conversations if c.conversion_achieved)
            },
            "engagement_breakdown": {
                "frequency_score": self._calculate_frequency_score(interactions),
                "recency_score": self._calculate_recency_score(interactions, lead),
                "duration_score": self._calculate_duration_score(interactions, lead),
                "consistency_score": self._calculate_consistency_score(interactions)
            }
        }

    async def _identify_improvement_opportunities(self, weighted_scores: Dict[str, float], lead: Lead) -> List[str]:
        """Identifica oportunidades para mejorar el score del lead"""
        opportunities = []
        
        lowest_category = min(weighted_scores.items(), key=lambda x: x[1])
        
        if lowest_category[0] == "demographic" and lowest_category[1] < 10:
            opportunities.append("Completar información del perfil (cargo, empresa, presupuesto)")
        
        if lowest_category[0] == "behavioral" and lowest_category[1] < 15:
            opportunities.append("Incrementar interacciones de alto valor (demos, consultas de precios)")
        
        if lowest_category[0] == "engagement" and lowest_category[1] < 10:
            opportunities.append("Mejorar frecuencia y consistencia de engagement")
        
        if lowest_category[0] == "conversation_ai" and lowest_category[1] < 8:
            opportunities.append("Fomentar conversaciones más profundas sobre necesidades")
        
        return opportunities

    def _get_error_score(self, lead_id: int, error: str) -> Dict[str, Any]:
        """Retorna score de error"""
        return {
            "total_score": 0.0,
            "weighted_scores": {},
            "raw_scores": {},
            "lead_status": "unknown",
            "confidence_level": "low",
            "score_breakdown": {},
            "error": True,
            "error_message": error,
            "lead_id": lead_id,
            "last_calculated": datetime.utcnow().isoformat()
        }

    async def update_lead_status(self, db: Session, lead_id: int, new_score: float = None) -> Dict[str, Any]:
        """Actualiza el status del lead basado en el score con manejo robusto"""
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            # Calcular score si no se proporciona
            if new_score is None:
                score_result = await self.calculate_lead_score(lead, db)
                new_score = score_result["total_score"]
                new_status = score_result["lead_status"]
            else:
                new_status = self._determine_lead_status(new_score, {})[0]
            
            # Guardar score anterior para tracking
            old_score = lead.score
            old_status = lead.status
            
            # Actualizar lead
            lead.score = new_score
            lead.status = new_status
            lead.last_score_update = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Lead {lead_id} actualizado: {old_score}→{new_score}, {old_status}→{new_status}")
            
            return {
                "success": True,
                "lead_id": lead_id,
                "old_score": old_score,
                "new_score": new_score,
                "old_status": old_status,
                "new_status": new_status,
                "score_change": new_score - old_score,
                "status_changed": old_status != new_status
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando status del lead {lead_id}: {e}")
            db.rollback()
            return {"success": False, "error": str(e), "lead_id": lead_id}

    async def batch_update_lead_scores(self, lead_ids: List[int], db: Session, 
                                     batch_size: int = 50) -> Dict[str, Any]:
        """Actualiza scores de múltiples leads en lote"""
        results = {
            "total_leads": len(lead_ids),
            "successful_updates": 0,
            "failed_updates": 0,
            "errors": [],
            "batch_size": batch_size
        }
        
        for i in range(0, len(lead_ids), batch_size):
            batch = lead_ids[i:i + batch_size]
            
            for lead_id in batch:
                try:
                    result = await self.update_lead_status(db, lead_id)
                    if result["success"]:
                        results["successful_updates"] += 1
                    else:
                        results["failed_updates"] += 1
                        results["errors"].append(f"Lead {lead_id}: {result.get('error', 'Error desconocido')}")
                except Exception as e:
                    results["failed_updates"] += 1
                    results["errors"].append(f"Lead {lead_id}: {str(e)}")
            
            # Pequeña pausa entre lotes
            await asyncio.sleep(1)
        
        results["success_rate"] = results["successful_updates"] / results["total_leads"] if results["total_leads"] > 0 else 0
        return results

    def clear_cache(self, lead_id: Optional[int] = None):
        """Limpia la cache de scores"""
        if lead_id:
            cache_key = f"lead_score_{lead_id}"
            if cache_key in self.ai_cache:
                del self.ai_cache[cache_key]
                logger.info(f"Cache limpiado para lead {lead_id}")
        else:
            self.ai_cache.clear()
            logger.info("Cache de scores limpiado completamente")

    def get_scoring_metrics(self) -> Dict[str, Any]:
        """Retorna métricas del sistema de scoring"""
        return {
            "scoring_weights": self.scoring_weights,
            "score_thresholds": self.score_thresholds,
            "cache_size": len(self.ai_cache),
            "cache_ttl_seconds": self.cache_ttl,
            "ai_model": "gpt-3.5-turbo"
        }

# Función de utilidad para crear instancia
def create_lead_scoring_service() -> LeadScoringService:
    return LeadScoringService()