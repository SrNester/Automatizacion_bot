import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc, distinct
from sqlalchemy.exc import SQLAlchemyError

from ..models.interaction import (
    Interaction, 
    ConversationSummary, 
    ConversationStatus,
    generate_conversation_id,
    calculate_engagement_score,
    detect_conversation_pattern
)
from ..models.integration import Lead, LeadStatus
from ..core.database import get_db

logger = logging.getLogger(__name__)

class ConversationManager:
    """Gestiona el estado y contexto de las conversaciones con mejoras robustas"""
    
    def __init__(self):
        self.active_conversations = {}  # Cache en memoria para conversaciones activas
        self.context_window = 15  # Número de mensajes para contexto
        self.conversation_timeout = timedelta(hours=24)  # Tiempo para considerar conversación inactiva
        self.cache_ttl = 300  # 5 minutos para cache de contexto
        
    async def get_or_create_conversation(self, 
                                       phone_number: str, 
                                       platform: str,
                                       db: Session) -> Tuple[str, bool]:
        """Obtiene o crea una conversación para un usuario"""
        
        try:
            # Buscar conversación activa reciente
            recent_interaction = db.query(Interaction)\
                .join(Lead, Interaction.lead_id == Lead.id)\
                .filter(
                    and_(
                        Lead.phone == phone_number,
                        Interaction.platform == platform,
                        Interaction.conversation_status == ConversationStatus.ACTIVE.value,
                        Interaction.created_at > datetime.utcnow() - self.conversation_timeout
                    )
                )\
                .order_by(Interaction.created_at.desc())\
                .first()
            
            if recent_interaction:
                logger.info(f"Conversación existente encontrada: {recent_interaction.conversation_id}")
                return recent_interaction.conversation_id, False
            else:
                # Crear nueva conversación
                new_conversation_id = generate_conversation_id()
                logger.info(f"Nueva conversación creada: {new_conversation_id}")
                return new_conversation_id, True
                
        except SQLAlchemyError as e:
            logger.error(f"Error buscando/conversación: {e}")
            # Fallback: generar nueva conversación
            return generate_conversation_id(), True
    
    async def get_conversation_context(self, 
                                     conversation_id: str, 
                                     db: Session,
                                     include_metadata: bool = True,
                                     use_cache: bool = True) -> Dict[str, Any]:
        """Obtiene el contexto completo de una conversación con cache"""
        
        # Verificar cache primero
        cache_key = f"context_{conversation_id}"
        if use_cache and cache_key in self.active_conversations:
            cached_data = self.active_conversations[cache_key]
            if datetime.utcnow() - cached_data['timestamp'] < timedelta(seconds=self.cache_ttl):
                logger.debug(f"Retornando contexto desde cache: {conversation_id}")
                return cached_data['data']
        
        try:
            # Obtener interacciones de la conversación con lead information
            interactions = db.query(Interaction)\
                .options(joinedload(Interaction.lead))\
                .filter(Interaction.conversation_id == conversation_id)\
                .order_by(Interaction.created_at.desc())\
                .limit(self.context_window)\
                .all()
            
            if not interactions:
                context = self._get_empty_context(conversation_id)
            else:
                context = await self._build_conversation_context(interactions, include_metadata)
            
            # Actualizar cache
            if use_cache:
                self.active_conversations[cache_key] = {
                    'data': context,
                    'timestamp': datetime.utcnow()
                }
            
            return context
            
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo contexto de conversación {conversation_id}: {e}")
            return self._get_error_context(conversation_id)
    
    def _get_empty_context(self, conversation_id: str) -> Dict[str, Any]:
        """Retorna contexto vacío para conversación nueva"""
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "total_messages": 0,
            "duration_minutes": 0,
            "primary_intent": None,
            "intents_detected": [],
            "sentiment_trend": "neutral",
            "sentiment_score_avg": 0.0,
            "escalation_risk": False,
            "buying_signals_count": 0,
            "last_activity": None,
            "platform": None,
            "lead_info": None,
            "conversation_patterns": {}
        }
    
    def _get_error_context(self, conversation_id: str) -> Dict[str, Any]:
        """Retorna contexto de error"""
        return {
            "conversation_id": conversation_id,
            "error": True,
            "message": "Error cargando contexto de conversación",
            "messages": [],
            "total_messages": 0
        }
    
    async def _build_conversation_context(self, 
                                        interactions: List[Interaction],
                                        include_metadata: bool) -> Dict[str, Any]:
        """Construye el contexto de la conversación a partir de interacciones"""
        
        conversation_id = interactions[0].conversation_id if interactions else None
        
        # Construir historial de mensajes
        messages = []
        intents_detected = []
        sentiments = []
        buying_signals_count = 0
        escalated = False
        
        for interaction in reversed(interactions):  # Orden cronológico
            if interaction.user_message:
                messages.append({
                    "role": "user",
                    "content": interaction.user_message,
                    "timestamp": interaction.created_at.isoformat(),
                    "intent": interaction.intent_detected,
                    "sentiment": interaction.sentiment_score,
                    "confidence": interaction.confidence_score
                })
                
                if interaction.intent_detected:
                    intents_detected.append(interaction.intent_detected)
                
                if interaction.sentiment_score is not None:
                    sentiments.append(interaction.sentiment_score)
                
                if interaction.buying_signals_detected:
                    buying_signals_count += 1
            
            if interaction.bot_response:
                messages.append({
                    "role": "assistant", 
                    "content": interaction.bot_response,
                    "timestamp": interaction.created_at.isoformat(),
                    "response_time_ms": interaction.response_time_ms
                })
            
            if interaction.escalated_to_human:
                escalated = True
        
        # Calcular métricas de la conversación
        first_message = interactions[-1].created_at
        last_message = interactions[0].created_at
        duration_minutes = int((last_message - first_message).total_seconds() / 60)
        
        # Determinar intención primaria
        primary_intent = self._calculate_primary_intent(intents_detected)
        
        # Análisis de sentiment
        sentiment_analysis = self._analyze_sentiment_trend(sentiments)
        
        # Detectar patrones de conversación
        conversation_patterns = detect_conversation_pattern(interactions)
        
        # Riesgo de escalación
        escalation_risk = self._assess_escalation_risk(
            interactions, 
            duration_minutes, 
            sentiment_analysis['trend']
        )
        
        # Información del lead
        lead_info = self._extract_lead_info(interactions[0]) if interactions else None
        
        context = {
            "conversation_id": conversation_id,
            "messages": messages,
            "total_messages": len(interactions),
            "duration_minutes": duration_minutes,
            "primary_intent": primary_intent,
            "intents_detected": list(set(intents_detected)),
            "sentiment_trend": sentiment_analysis['trend'],
            "sentiment_score_avg": sentiment_analysis['average'],
            "escalation_risk": escalation_risk,
            "buying_signals_count": buying_signals_count,
            "last_activity": last_message.isoformat(),
            "platform": interactions[0].platform if interactions else None,
            "lead_info": lead_info,
            "conversation_patterns": conversation_patterns,
            "engagement_score": calculate_engagement_score(interactions)
        }
        
        if include_metadata:
            context["metadata"] = {
                "buying_signals_count": buying_signals_count,
                "average_response_time": self._calculate_avg_response_time(interactions),
                "escalated": escalated,
                "escalation_reason": interactions[0].escalation_reason if interactions else None,
                "assigned_agent": interactions[0].assigned_agent if interactions else None
            }
        
        return context
    
    def _calculate_primary_intent(self, intents_detected: List[str]) -> Optional[str]:
        """Calcula la intención primaria basada en frecuencia y prioridad"""
        if not intents_detected:
            return None
        
        # Prioridad de intenciones (mayor número = mayor prioridad)
        intent_priority = {
            "buying": 5,
            "demo": 4,
            "pricing": 3,
            "product_inquiry": 2,
            "support": 2,
            "greeting": 1
        }
        
        intent_counts = {}
        for intent in intents_detected:
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Encontrar intención más común, con desempate por prioridad
        if intent_counts:
            max_count = max(intent_counts.values())
            most_common = [intent for intent, count in intent_counts.items() if count == max_count]
            
            if len(most_common) == 1:
                return most_common[0]
            else:
                # Desempate por prioridad
                return max(most_common, key=lambda x: intent_priority.get(x, 0))
        
        return None
    
    def _analyze_sentiment_trend(self, sentiments: List[float]) -> Dict[str, Any]:
        """Analiza la tendencia de sentiment de la conversación"""
        if not sentiments:
            return {"trend": "neutral", "average": 0.0, "volatility": 0.0}
        
        average = sum(sentiments) / len(sentiments)
        
        # Calcular volatilidad (desviación estándar aproximada)
        volatility = (max(sentiments) - min(sentiments)) if sentiments else 0
        
        if average > 0.3:
            trend = "positive"
        elif average < -0.3:
            trend = "negative"
        else:
            trend = "neutral"
        
        # Analizar tendencia reciente (últimos 3 mensajes)
        recent_trend = "stable"
        if len(sentiments) >= 3:
            recent_avg = sum(sentiments[-3:]) / 3
            if recent_avg > average + 0.2:
                recent_trend = "improving"
            elif recent_avg < average - 0.2:
                recent_trend = "deteriorating"
        
        return {
            "trend": trend,
            "recent_trend": recent_trend,
            "average": round(average, 3),
            "volatility": round(volatility, 3),
            "message_count": len(sentiments)
        }
    
    def _assess_escalation_risk(self, 
                              interactions: List[Interaction],
                              duration_minutes: int,
                              sentiment_trend: str) -> bool:
        """Evalúa el riesgo de necesitar escalación"""
        
        risk_factors = [
            duration_minutes > 45,  # Conversación muy larga
            len(interactions) > 25,  # Muchos mensajes
            sentiment_trend == "negative",  # Sentiment negativo
            any(i.escalated_to_human for i in interactions),  # Ya escalada
            any("frustrat" in (i.user_message or "").lower() for i in interactions[-3:]),  # Frustración reciente
            any(i.confidence_score and i.confidence_score < 0.3 for i in interactions[-2:])  # Baja confianza reciente
        ]
        
        # Ponderar factores de riesgo
        risk_score = sum(1 for factor in risk_factors if factor)
        
        return risk_score >= 2  # Alto riesgo si 2+ factores
    
    def _extract_lead_info(self, interaction: Interaction) -> Optional[Dict[str, Any]]:
        """Extrae información relevante del lead"""
        if not interaction.lead:
            return None
        
        lead = interaction.lead
        return {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "company": lead.company,
            "score": lead.score,
            "status": lead.status,
            "is_qualified": lead.is_qualified,
            "source": lead.source,
            "first_interaction": lead.first_interaction.isoformat() if lead.first_interaction else None
        }
    
    def _calculate_avg_response_time(self, interactions: List[Interaction]) -> float:
        """Calcula el tiempo promedio de respuesta"""
        response_times = [
            i.response_time_ms for i in interactions 
            if i.response_time_ms and i.response_time_ms > 0
        ]
        
        if not response_times:
            return 0.0
        
        return sum(response_times) / len(response_times)
    
    async def update_conversation_status(self, 
                                       conversation_id: str,
                                       status: ConversationStatus,
                                       reason: str = None,
                                       assigned_agent: str = None,
                                       db: Session = None) -> bool:
        """Actualiza el estado de una conversación con manejo de errores"""
        
        try:
            # Actualizar todas las interacciones de la conversación
            update_result = db.query(Interaction)\
                .filter(Interaction.conversation_id == conversation_id)\
                .update({
                    "conversation_status": status.value,
                    "updated_at": datetime.utcnow()
                })
            
            if status == ConversationStatus.ESCALATED:
                # Marcar escalación en la última interacción
                last_interaction = db.query(Interaction)\
                    .filter(Interaction.conversation_id == conversation_id)\
                    .order_by(Interaction.created_at.desc())\
                    .first()
                
                if last_interaction:
                    last_interaction.escalated_to_human = True
                    last_interaction.escalation_reason = reason
                    if assigned_agent:
                        last_interaction.assigned_agent = assigned_agent
            
            db.commit()
            
            # Limpiar cache
            self._clear_conversation_cache(conversation_id)
            
            logger.info(f"Estado de conversación {conversation_id} actualizado a {status.value}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error actualizando estado de conversación {conversation_id}: {e}")
            db.rollback()
            return False
    
    async def close_conversation(self, 
                               conversation_id: str,
                               outcome: str,
                               conversion_value: float = 0.0,
                               db: Session = None) -> bool:
        """Cierra una conversación y genera resumen"""
        
        try:
            # Actualizar estado
            success = await self.update_conversation_status(
                conversation_id, 
                ConversationStatus.CLOSED, 
                reason=f"Conversación cerrada: {outcome}",
                db=db
            )
            
            if not success:
                return False
            
            # Generar resumen de la conversación
            await self._generate_conversation_summary(
                conversation_id, 
                outcome, 
                conversion_value,
                db
            )
            
            logger.info(f"Conversación {conversation_id} cerrada con resultado: {outcome}")
            return True
            
        except Exception as e:
            logger.error(f"Error cerrando conversación {conversation_id}: {e}")
            return False
    
    async def _generate_conversation_summary(self, 
                                           conversation_id: str,
                                           outcome: str,
                                           conversion_value: float,
                                           db: Session):
        """Genera un resumen automático de la conversación"""
        
        try:
            context = await self.get_conversation_context(conversation_id, db, include_metadata=True)
            
            if context.get("error") or context["total_messages"] == 0:
                logger.warning(f"No se pudo generar resumen para conversación {conversation_id}")
                return
            
            # Obtener información del lead
            first_interaction = db.query(Interaction)\
                .filter(Interaction.conversation_id == conversation_id)\
                .order_by(Interaction.created_at.asc())\
                .first()
            
            if not first_interaction:
                logger.error(f"No se encontró interacción inicial para {conversation_id}")
                return
            
            lead_id = first_interaction.lead_id
            
            # Crear resumen usando IA (simplificado por ahora)
            ai_summary = await self._create_ai_summary(context)
            
            # Determinar si hubo conversión
            conversion_achieved, conversion_type = self._detect_conversion(outcome, context)
            
            # Crear objeto de resumen
            summary = ConversationSummary(
                conversation_id=conversation_id,
                lead_id=lead_id,
                summary=ai_summary,
                key_points=self._extract_key_points(context),
                action_items=self._identify_action_items(context, outcome),
                total_messages=context["total_messages"],
                user_message_count=len([m for m in context["messages"] if m["role"] == "user"]),
                bot_message_count=len([m for m in context["messages"] if m["role"] == "assistant"]),
                duration_minutes=context["duration_minutes"],
                avg_response_time_seconds=context.get("metadata", {}).get("average_response_time", 0) / 1000,
                primary_intent=context["primary_intent"],
                intents_detected=context["intents_detected"],
                overall_sentiment=context["sentiment_trend"],
                sentiment_trend=context.get("sentiment_analysis", {}).get("recent_trend", "stable"),
                conversion_achieved=conversion_achieved,
                conversion_type=conversion_type,
                conversion_value=conversion_value,
                engagement_score=context["engagement_score"],
                satisfaction_score=self._calculate_satisfaction_score(context),
                lead_quality_score=self._calculate_lead_quality_score(context, lead_id, db),
                resolution_score=self._calculate_resolution_score(context, outcome),
                final_status=ConversationStatus.CLOSED.value,
                outcome=outcome,
                next_action=self._determine_next_action(context, outcome),
                follow_up_required=conversion_achieved or context["buying_signals_count"] > 0,
                follow_up_date=datetime.utcnow() + timedelta(days=7) if conversion_achieved else None,
                started_at=datetime.fromisoformat(context["messages"][0]["timestamp"]) if context["messages"] else datetime.utcnow(),
                ended_at=datetime.utcnow(),
                last_message_at=datetime.fromisoformat(context["last_activity"]) if context["last_activity"] else datetime.utcnow()
            )
            
            db.add(summary)
            db.commit()
            
            logger.info(f"Resumen generado para conversación {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error generando resumen para conversación {conversation_id}: {e}")
            db.rollback()
    
    async def _create_ai_summary(self, context: Dict) -> str:
        """Crea un resumen de la conversación usando IA"""
        
        # En una implementación real, aquí integrarías con OpenAI
        # Por ahora, un resumen básico basado en patrones
        
        summary_parts = []
        
        if context["primary_intent"]:
            summary_parts.append(f"Conversación centrada en {context['primary_intent']}.")
        
        summary_parts.append(f"Duración: {context['duration_minutes']} minutos.")
        summary_parts.append(f"Mensajes: {context['total_messages']} intercambios.")
        
        if context["buying_signals_count"] > 0:
            summary_parts.append(f"Señales de compra detectadas: {context['buying_signals_count']}.")
        
        if context["escalation_risk"]:
            summary_parts.append("Se identificó riesgo de escalación.")
        
        summary_parts.append(f"Sentiment general: {context['sentiment_trend']}.")
        
        return " ".join(summary_parts)
    
    def _detect_conversion(self, outcome: str, context: Dict) -> Tuple[bool, Optional[str]]:
        """Detecta si hubo conversión y de qué tipo"""
        conversion_keywords = {
            "demo": ["demo", "demostración", "presentación", "reunión"],
            "sale": ["comprar", "contratar", "adquirir", "ordenar", "pagar"],
            "lead": ["información", "cotización", "presupuesto", "contacto"]
        }
        
        outcome_lower = outcome.lower()
        
        for conv_type, keywords in conversion_keywords.items():
            if any(keyword in outcome_lower for keyword in keywords):
                return True, conv_type
        
        # Verificar en la conversación también
        if context["primary_intent"] in ["buying", "demo", "pricing"]:
            return True, context["primary_intent"]
        
        return False, None
    
    def _extract_key_points(self, context: Dict) -> List[str]:
        """Extrae puntos clave de la conversación"""
        key_points = []
        
        if context["primary_intent"]:
            key_points.append(f"Intención principal: {context['primary_intent']}")
        
        if context["buying_signals_count"] > 0:
            key_points.append(f"Señales de compra: {context['buying_signals_count']} detectadas")
        
        key_points.append(f"Engagement score: {context['engagement_score']:.2f}")
        key_points.append(f"Tendencia sentiment: {context['sentiment_trend']}")
        
        return key_points
    
    def _identify_action_items(self, context: Dict, outcome: str) -> List[str]:
        """Identifica acciones requeridas post-conversación"""
        actions = []
        
        if context["escalation_risk"]:
            actions.append("Seguimiento por agente humano requerido")
        
        if context["buying_signals_count"] > 0:
            actions.append("Contactar para seguimiento de ventas")
        
        if "demo" in outcome.lower():
            actions.append("Programar demostración del producto")
        
        if "soporte" in outcome.lower() or "problema" in outcome.lower():
            actions.append("Dar seguimiento técnico")
        
        return actions
    
    def _calculate_satisfaction_score(self, context: Dict) -> float:
        """Calcula score de satisfacción del cliente"""
        base_score = 0.5  # Neutro por defecto
        
        # Basado en sentiment
        sentiment_score = context.get("sentiment_score_avg", 0)
        base_score += sentiment_score * 0.3
        
        # Ajustar por tiempo de respuesta
        avg_response = context.get("metadata", {}).get("average_response_time", 0)
        if avg_response > 0:
            if avg_response < 5000:  # Bueno: menos de 5 segundos
                base_score += 0.2
            elif avg_response > 15000:  # Malo: más de 15 segundos
                base_score -= 0.2
        
        # Ajustar por escalación
        if context.get("metadata", {}).get("escalated"):
            base_score -= 0.1
        
        return max(0.0, min(1.0, base_score))
    
    def _calculate_lead_quality_score(self, context: Dict, lead_id: int, db: Session) -> float:
        """Calcula score de calidad del lead post-conversación"""
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return 0.0
            
            # Score base del lead
            base_score = lead.score / 100.0
            
            # Modificadores basados en la conversación
            modifiers = {
                "buying_signals": context["buying_signals_count"] * 0.1,
                "engagement": context["engagement_score"] * 0.3,
                "sentiment": max(0, context.get("sentiment_score_avg", 0)) * 0.2,
                "intent_quality": 0.2 if context["primary_intent"] in ["buying", "demo"] else 0.0
            }
            
            final_score = base_score + sum(modifiers.values())
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculando lead quality score: {e}")
            return 0.0
    
    def _calculate_resolution_score(self, context: Dict, outcome: str) -> float:
        """Calcula qué tan bien se resolvió la consulta"""
        resolution_keywords = ["resuelto", "solucionado", "gracias", "perfecto", "excelente"]
        
        base_score = 0.7  # Asumir resolución moderada
        
        # Mejorar si outcome indica resolución
        if any(keyword in outcome.lower() for keyword in resolution_keywords):
            base_score += 0.2
        
        # Mejorar si no hubo escalación
        if not context.get("metadata", {}).get("escalated"):
            base_score += 0.1
        
        return min(1.0, base_score)
    
    def _determine_next_action(self, context: Dict, outcome: str) -> str:
        """Determina la próxima acción recomendada"""
        if context["buying_signals_count"] > 2:
            return "Contactar para cierre de venta"
        elif "demo" in outcome.lower():
            return "Programar demostración"
        elif context["escalation_risk"]:
            return "Seguimiento por agente especializado"
        elif context["primary_intent"] == "support":
            return "Verificar resolución del problema"
        else:
            return "Seguimiento general en 7 días"
    
    def _clear_conversation_cache(self, conversation_id: str):
        """Limpia el cache de una conversación específica"""
        cache_key = f"context_{conversation_id}"
        if cache_key in self.active_conversations:
            del self.active_conversations[cache_key]
    
    async def get_conversation_metrics(self, 
                                     days: int = 30,
                                     db: Session = None) -> Dict[str, Any]:
        """Obtiene métricas agregadas de conversaciones con manejo de errores"""
        
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Consultas base con manejo de errores
            metrics = await asyncio.gather(
                self._get_basic_conversation_metrics(since_date, db),
                self._get_average_metrics(since_date, db),
                self._get_top_intents(since_date, db),
                return_exceptions=True
            )
            
            # Procesar resultados
            basic_metrics = metrics[0] if not isinstance(metrics[0], Exception) else {}
            avg_metrics = metrics[1] if not isinstance(metrics[1], Exception) else {}
            top_intents = metrics[2] if not isinstance(metrics[2], Exception) else []
            
            return {
                "period_days": days,
                "timeframe": {
                    "start": since_date.isoformat(),
                    "end": datetime.utcnow().isoformat()
                },
                "totals": basic_metrics.get("totals", {}),
                "rates": basic_metrics.get("rates", {}),
                "averages": avg_metrics,
                "top_intents": top_intents,
                "calculated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas de conversación: {e}")
            return self._get_error_metrics(days)
    
    async def _get_basic_conversation_metrics(self, since_date: datetime, db: Session) -> Dict:
        """Obtiene métricas básicas de conversaciones"""
        try:
            # Total de conversaciones en el período
            total_conversations = db.query(ConversationSummary)\
                .filter(ConversationSummary.created_at > since_date)\
                .count()
            
            # Conversaciones activas actualmente
            active_conversations = db.query(Interaction)\
                .filter(
                    and_(
                        Interaction.conversation_status == ConversationStatus.ACTIVE.value,
                        Interaction.created_at > since_date
                    )
                )\
                .distinct(Interaction.conversation_id)\
                .count()
            
            # Otras métricas
            escalated_count = db.query(ConversationSummary)\
                .filter(
                    and_(
                        ConversationSummary.created_at > since_date,
                        ConversationSummary.final_status == ConversationStatus.ESCALATED.value
                    )
                )\
                .count()
            
            converted_count = db.query(ConversationSummary)\
                .filter(
                    and_(
                        ConversationSummary.created_at > since_date,
                        ConversationSummary.conversion_achieved == True
                    )
                )\
                .count()
            
            return {
                "totals": {
                    "total_conversations": total_conversations,
                    "active_conversations": active_conversations,
                    "escalated_conversations": escalated_count,
                    "converted_conversations": converted_count
                },
                "rates": {
                    "escalation_rate": (escalated_count / total_conversations * 100) if total_conversations > 0 else 0,
                    "conversion_rate": (converted_count / total_conversations * 100) if total_conversations > 0 else 0,
                    "resolution_rate": ((total_conversations - active_conversations) / total_conversations * 100) if total_conversations > 0 else 0
                }
            }
        except Exception as e:
            logger.error(f"Error en métricas básicas: {e}")
            return {}
    
    async def _get_average_metrics(self, since_date: datetime, db: Session) -> Dict:
        """Obtiene métricas promedio"""
        try:
            avg_data = db.query(
                func.avg(ConversationSummary.duration_minutes).label('avg_duration'),
                func.avg(ConversationSummary.total_messages).label('avg_messages'),
                func.avg(ConversationSummary.engagement_score).label('avg_engagement'),
                func.avg(ConversationSummary.satisfaction_score).label('avg_satisfaction'),
                func.avg(ConversationSummary.resolution_score).label('avg_resolution')
            ).filter(ConversationSummary.created_at > since_date).first()
            
            return {
                "duration_minutes": round(float(avg_data.avg_duration or 0), 2),
                "messages_per_conversation": round(float(avg_data.avg_messages or 0), 2),
                "engagement_score": round(float(avg_data.avg_engagement or 0), 3),
                "satisfaction_score": round(float(avg_data.avg_satisfaction or 0), 3),
                "resolution_score": round(float(avg_data.avg_resolution or 0), 3)
            }
        except Exception as e:
            logger.error(f"Error en métricas promedio: {e}")
            return {}
    
    async def _get_top_intents(self, since_date: datetime, db: Session) -> List[Dict]:
        """Obtiene las intenciones más comunes"""
        try:
            top_intents = db.query(
                ConversationSummary.primary_intent,
                func.count(ConversationSummary.id).label('count')
            ).filter(
                and_(
                    ConversationSummary.created_at > since_date,
                    ConversationSummary.primary_intent.isnot(None)
                )
            ).group_by(ConversationSummary.primary_intent)\
             .order_by(desc('count'))\
             .limit(10).all()
            
            return [{"intent": intent, "count": count} for intent, count in top_intents]
        except Exception as e:
            logger.error(f"Error obteniendo intenciones: {e}")
            return []
    
    def _get_error_metrics(self, days: int) -> Dict:
        """Retorna métricas de error"""
        return {
            "error": True,
            "message": "Error calculando métricas",
            "period_days": days,
            "totals": {},
            "rates": {},
            "averages": {},
            "top_intents": []
        }
    
    async def get_active_conversations_summary(self, db: Session) -> List[Dict[str, Any]]:
        """Obtiene resumen de conversaciones activas para el dashboard"""
        
        try:
            # Obtener conversaciones activas recientes
            active_conversations = db.query(Interaction)\
                .options(joinedload(Interaction.lead))\
                .filter(
                    and_(
                        Interaction.conversation_status == ConversationStatus.ACTIVE.value,
                        Interaction.created_at > datetime.utcnow() - timedelta(hours=24)
                    )
                )\
                .order_by(Interaction.created_at.desc())\
                .all()
            
            # Agrupar por conversación
            conversations_map = {}
            
            for interaction in active_conversations:
                conv_id = interaction.conversation_id
                
                if conv_id not in conversations_map:
                    conversations_map[conv_id] = {
                        "conversation_id": conv_id,
                        "lead_info": {
                            "name": interaction.lead.name if interaction.lead else "Usuario Anónimo",
                            "phone": interaction.lead.phone if interaction.lead else interaction.phone_number,
                            "score": interaction.lead.score if interaction.lead else 0,
                            "company": interaction.lead.company if interaction.lead else None,
                            "status": interaction.lead.status if interaction.lead else None
                        },
                        "platform": interaction.platform,
                        "last_message": interaction.user_message,
                        "last_activity": interaction.created_at.isoformat(),
                        "message_count": 0,
                        "primary_intent": interaction.intent_detected,
                        "buying_signals": interaction.buying_signals_detected,
                        "escalation_risk": False,
                        "sentiment": interaction.sentiment_score or 0,
                        "duration_minutes": 0
                    }
                
                conversations_map[conv_id]["message_count"] += 1
                
                # Calcular duración
                first_interaction = db.query(Interaction)\
                    .filter(Interaction.conversation_id == conv_id)\
                    .order_by(Interaction.created_at.asc())\
                    .first()
                
                if first_interaction:
                    duration = (interaction.created_at - first_interaction.created_at).total_seconds() / 60
                    conversations_map[conv_id]["duration_minutes"] = int(duration)
                
                # Evaluar riesgo de escalación
                if (conversations_map[conv_id]["message_count"] > 15 or 
                    conversations_map[conv_id]["duration_minutes"] > 30 or
                    interaction.sentiment_score and interaction.sentiment_score < -0.5):
                    conversations_map[conv_id]["escalation_risk"] = True
            
            return list(conversations_map.values())
            
        except Exception as e:
            logger.error(f"Error obteniendo conversaciones activas: {e}")
            return []
    
    def cleanup_old_cache(self):
        """Limpia conversaciones viejas del cache en memoria"""
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.cache_ttl // 60)
        
        expired_conversations = [
            conv_id for conv_id, data in self.active_conversations.items()
            if data.get("timestamp", datetime.utcnow()) < cutoff_time
        ]
        
        for conv_id in expired_conversations:
            del self.active_conversations[conv_id]
        
        logger.info(f"Cache limpiado: {len(expired_conversations)} conversaciones eliminadas")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        return {
            "total_cached_conversations": len(self.active_conversations),
            "cache_ttl_seconds": self.cache_ttl,
            "context_window_size": self.context_window,
            "conversation_timeout_hours": self.conversation_timeout.total_seconds() / 3600
        }

# Función de utilidad para crear instancia
def create_conversation_manager() -> ConversationManager:
    return ConversationManager()