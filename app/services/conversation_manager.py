from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.interaction import Interaction, ConversationSummary, ConversationStatus
from ..models.lead import Lead
from ..core.database import get_db

class ConversationManager:
    """Gestiona el estado y contexto de las conversaciones"""
    
    def __init__(self):
        self.active_conversations = {}  # Cache en memoria para conversaciones activas
        self.context_window = 10  # Número de mensajes para contexto
        
    async def get_or_create_conversation(self, 
                                       phone_number: str, 
                                       platform: str,
                                       db: Session) -> str:
        """Obtiene o crea una conversación para un usuario"""
        
        # Buscar conversación activa reciente (últimas 24 horas)
        recent_interaction = db.query(Interaction).join(Lead)\
            .filter(Lead.phone == phone_number)\
            .filter(Interaction.platform == platform)\
            .filter(Interaction.conversation_status == ConversationStatus.ACTIVE)\
            .filter(Interaction.created_at > datetime.utcnow() - timedelta(hours=24))\
            .order_by(Interaction.created_at.desc())\
            .first()
        
        if recent_interaction:
            return recent_interaction.conversation_id
        else:
            # Crear nueva conversación
            from ..models.interaction import generate_conversation_id
            return generate_conversation_id()
    
    async def get_conversation_context(self, 
                                     conversation_id: str, 
                                     db: Session,
                                     include_metadata: bool = True) -> Dict:
        """Obtiene el contexto completo de una conversación"""
        
        # Obtener interacciones de la conversación
        interactions = db.query(Interaction)\
            .filter(Interaction.conversation_id == conversation_id)\
            .order_by(Interaction.created_at.desc())\
            .limit(self.context_window)\
            .all()
        
        if not interactions:
            return {
                "messages": [],
                "total_messages": 0,
                "duration_minutes": 0,
                "primary_intent": None,
                "sentiment_trend": "neutral",
                "escalation_risk": False
            }
        
        # Construir historial de mensajes
        messages = []
        intents_detected = []
        sentiments = []
        
        for interaction in reversed(interactions):  # Orden cronológico
            if interaction.user_message:
                messages.append({
                    "role": "user",
                    "content": interaction.user_message,
                    "timestamp": interaction.created_at.isoformat()
                })
                
                if interaction.intent_detected:
                    intents_detected.append(interaction.intent_detected)
                
                if interaction.sentiment_score is not None:
                    sentiments.append(interaction.sentiment_score)
            
            if interaction.bot_response:
                messages.append({
                    "role": "assistant", 
                    "content": interaction.bot_response,
                    "timestamp": interaction.created_at.isoformat()
                })
        
        # Calcular métricas de la conversación
        first_message = interactions[-1].created_at
        last_message = interactions[0].created_at
        duration_minutes = int((last_message - first_message).total_seconds() / 60)
        
        # Determinar intención primaria
        primary_intent = max(set(intents_detected), key=intents_detected.count) if intents_detected else None
        
        # Tendencia de sentiment
        sentiment_trend = "positive" if sentiments and sum(sentiments)/len(sentiments) > 0.2 else \
                         "negative" if sentiments and sum(sentiments)/len(sentiments) < -0.2 else "neutral"
        
        # Riesgo de escalación
        escalation_risk = (
            duration_minutes > 30 or 
            len(interactions) > 15 or
            (sentiments and sum(sentiments)/len(sentiments) < -0.5)
        )
        
        context = {
            "conversation_id": conversation_id,
            "messages": messages,
            "total_messages": len(interactions),
            "duration_minutes": duration_minutes,
            "primary_intent": primary_intent,
            "intents_detected": list(set(intents_detected)),
            "sentiment_trend": sentiment_trend,
            "escalation_risk": escalation_risk,
            "last_activity": last_message.isoformat(),
            "platform": interactions[0].platform if interactions else None
        }
        
        if include_metadata:
            context["metadata"] = {
                "buying_signals_count": sum(1 for i in interactions if i.buying_signals_detected),
                "average_response_time": sum(i.response_time_ms for i in interactions if i.response_time_ms) / len(interactions),
                "escalated": any(i.escalated_to_human for i in interactions)
            }
        
        return context

    async def update_conversation_status(self, 
                                       conversation_id: str,
                                       status: ConversationStatus,
                                       reason: str = None,
                                       db: Session = None):
        """Actualiza el estado de una conversación"""
        
        # Actualizar todas las interacciones de la conversación
        db.query(Interaction)\
            .filter(Interaction.conversation_id == conversation_id)\
            .update({
                "conversation_status": status,
                "updated_at": datetime.utcnow()
            })
        
        if status == ConversationStatus.ESCALATED and reason:
            # Marcar escalación en la última interacción
            last_interaction = db.query(Interaction)\
                .filter(Interaction.conversation_id == conversation_id)\
                .order_by(Interaction.created_at.desc())\
                .first()
            
            if last_interaction:
                last_interaction.escalated_to_human = True
                last_interaction.escalation_reason = reason
        
        db.commit()

    async def close_conversation(self, 
                               conversation_id: str,
                               outcome: str,
                               db: Session):
        """Cierra una conversación y genera resumen"""
        
        # Actualizar estado
        await self.update_conversation_status(
            conversation_id, 
            ConversationStatus.CLOSED, 
            db=db
        )
        
        # Generar resumen de la conversación
        await self._generate_conversation_summary(conversation_id, outcome, db)

    async def _generate_conversation_summary(self, 
                                           conversation_id: str,
                                           outcome: str,
                                           db: Session):
        """Genera un resumen automático de la conversación"""
        
        context = await self.get_conversation_context(conversation_id, db)
        
        if context["total_messages"] == 0:
            return
        
        # Obtener información del lead
        first_interaction = db.query(Interaction)\
            .filter(Interaction.conversation_id == conversation_id)\
            .order_by(Interaction.created_at)\
            .first()
        
        lead = db.query(Lead).filter(Lead.id == first_interaction.lead_id).first()
        
        # Crear resumen
        summary = ConversationSummary(
            conversation_id=conversation_id,
            lead_id=lead.id if lead else None,
            summary=await self._create_ai_summary(context),
            total_messages=context["total_messages"],
            duration_minutes=context["duration_minutes"],
            primary_intent=context["primary_intent"],
            intents_detected=context["intents_detected"],
            engagement_score=self._calculate_engagement_score(context),
            satisfaction_score=self._calculate_satisfaction_score(context),
            final_status=ConversationStatus.CLOSED,
            outcome=outcome,
            started_at=datetime.fromisoformat(context["messages"][0]["timestamp"]) if context["messages"] else datetime.utcnow(),
            ended_at=datetime.utcnow()
        )
        
        # Determinar si hubo conversión
        conversion_signals = ["demo", "comprar", "contratar", "agendar", "reunión"]
        summary.conversion_achieved = any(
            signal in outcome.lower() or 
            signal in context["primary_intent"].lower() if context["primary_intent"] else False
            for signal in conversion_signals
        )
        
        if summary.conversion_achieved:
            summary.conversion_type = context["primary_intent"]
        
        db.add(summary)
        db.commit()

    async def _create_ai_summary(self, context: Dict) -> str:
        """Crea un resumen de la conversación usando IA"""
        
        # Extraer mensajes clave para el resumen
        key_messages = []
        for msg in context["messages"]:
            if msg["role"] == "user":
                key_messages.append(msg["content"])
        
        if not key_messages:
            return "Conversación sin mensajes del usuario"
        
        # Crear resumen básico (aquí podrías usar OpenAI para un resumen más sofisticado)
        summary_parts = [
            f"Conversación de {context['duration_minutes']} minutos con {context['total_messages']} mensajes.",
            f"Intención principal: {context['primary_intent'] or 'No detectada'}.",
            f"Tendencia de sentiment: {context['sentiment_trend']}."
        ]
        
        if context.get("metadata", {}).get("buying_signals_count", 0) > 0:
            summary_parts.append(f"Señales de compra detectadas: {context['metadata']['buying_signals_count']}.")
        
        return " ".join(summary_parts)

    def _calculate_engagement_score(self, context: Dict) -> float:
        """Calcula score de engagement basado en la conversación"""
        
        base_score = 0.0
        
        # Puntuación por número de mensajes
        message_count = context["total_messages"]
        if message_count >= 10:
            base_score += 0.4
        elif message_count >= 5:
            base_score += 0.2
        
        # Puntuación por duración
        duration = context["duration_minutes"]
        if duration >= 15:
            base_score += 0.3
        elif duration >= 5:
            base_score += 0.1
        
        # Puntuación por intenciones detectadas
        if context["primary_intent"] in ["pricing", "demo", "buying"]:
            base_score += 0.3
        
        # Reducir por sentiment negativo
        if context["sentiment_trend"] == "negative":
            base_score -= 0.2
        elif context["sentiment_trend"] == "positive":
            base_score += 0.1
        
        return max(0.0, min(1.0, base_score))

    def _calculate_satisfaction_score(self, context: Dict) -> float:
        """Calcula score de satisfacción del cliente"""
        
        base_score = 0.5  # Neutro por defecto
        
        # Basado en sentiment
        if context["sentiment_trend"] == "positive":
            base_score = 0.8
        elif context["sentiment_trend"] == "negative":
            base_score = 0.2
        
        # Ajustar por escalación
        if context.get("metadata", {}).get("escalated"):
            base_score -= 0.2
        
        # Ajustar por tiempo de respuesta promedio
        avg_response_time = context.get("metadata", {}).get("average_response_time", 2000)
        if avg_response_time < 3000:  # Menos de 3 segundos
            base_score += 0.1
        elif avg_response_time > 10000:  # Más de 10 segundos
            base_score -= 0.1
        
        return max(0.0, min(1.0, base_score))

    async def get_conversation_metrics(self, 
                                     days: int = 30,
                                     db: Session = None) -> Dict:
        """Obtiene métricas agregadas de conversaciones"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Consultas base
        total_conversations = db.query(ConversationSummary)\
            .filter(ConversationSummary.created_at > since_date)\
            .count()
        
        active_conversations = db.query(Interaction)\
            .filter(Interaction.conversation_status == ConversationStatus.ACTIVE)\
            .filter(Interaction.created_at > since_date)\
            .distinct(Interaction.conversation_id)\
            .count()
        
        escalated_conversations = db.query(ConversationSummary)\
            .filter(ConversationSummary.created_at > since_date)\
            .filter(ConversationSummary.final_status == ConversationStatus.ESCALATED)\
            .count()
        
        converted_conversations = db.query(ConversationSummary)\
            .filter(ConversationSummary.created_at > since_date)\
            .filter(ConversationSummary.conversion_achieved == True)\
            .count()
        
        # Métricas promedio
        avg_metrics = db.query(
            func.avg(ConversationSummary.duration_minutes).label('avg_duration'),
            func.avg(ConversationSummary.total_messages).label('avg_messages'),
            func.avg(ConversationSummary.engagement_score).label('avg_engagement'),
            func.avg(ConversationSummary.satisfaction_score).label('avg_satisfaction')
        ).filter(ConversationSummary.created_at > since_date).first()
        
        # Intenciones más comunes
        top_intents = db.query(
            ConversationSummary.primary_intent,
            func.count(ConversationSummary.id).label('count')
        ).filter(ConversationSummary.created_at > since_date)\
         .filter(ConversationSummary.primary_intent.isnot(None))\
         .group_by(ConversationSummary.primary_intent)\
         .order_by(func.count(ConversationSummary.id).desc())\
         .limit(5).all()
        
        return {
            "period_days": days,
            "totals": {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "escalated_conversations": escalated_conversations,
                "converted_conversations": converted_conversations
            },
            "rates": {
                "escalation_rate": escalated_conversations / total_conversations if total_conversations > 0 else 0,
                "conversion_rate": converted_conversations / total_conversations if total_conversations > 0 else 0,
                "resolution_rate": (total_conversations - active_conversations) / total_conversations if total_conversations > 0 else 0
            },
            "averages": {
                "duration_minutes": float(avg_metrics.avg_duration or 0),
                "messages_per_conversation": float(avg_metrics.avg_messages or 0),
                "engagement_score": float(avg_metrics.avg_engagement or 0),
                "satisfaction_score": float(avg_metrics.avg_satisfaction or 0)
            },
            "top_intents": [
                {"intent": intent, "count": count} 
                for intent, count in top_intents
            ]
        }

    async def get_active_conversations_summary(self, db: Session) -> List[Dict]:
        """Obtiene resumen de conversaciones activas para el dashboard"""
        
        active_interactions = db.query(Interaction).join(Lead)\
            .filter(Interaction.conversation_status == ConversationStatus.ACTIVE)\
            .filter(Interaction.created_at > datetime.utcnow() - timedelta(hours=24))\
            .order_by(Interaction.created_at.desc())\
            .all()
        
        conversations_summary = {}
        
        for interaction in active_interactions:
            conv_id = interaction.conversation_id
            
            if conv_id not in conversations_summary:
                conversations_summary[conv_id] = {
                    "conversation_id": conv_id,
                    "lead_name": interaction.lead.name if interaction.lead else "Usuario Anónimo",
                    "lead_phone": interaction.lead.phone if interaction.lead else interaction.phone_number,
                    "lead_score": interaction.lead.score if interaction.lead else 0,
                    "platform": interaction.platform,
                    "last_message": interaction.user_message,
                    "last_activity": interaction.created_at.isoformat(),
                    "message_count": 0,
                    "primary_intent": interaction.intent_detected,
                    "buying_signals": interaction.buying_signals_detected,
                    "escalation_risk": False
                }
            
            conversations_summary[conv_id]["message_count"] += 1
            
            # Actualizar riesgo de escalación
            if (interaction.created_at < datetime.utcnow() - timedelta(minutes=30) or
                conversations_summary[conv_id]["message_count"] > 10):
                conversations_summary[conv_id]["escalation_risk"] = True
        
        return list(conversations_summary.values())

    def cleanup_old_cache(self):
        """Limpia conversaciones viejas del cache en memoria"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        expired_conversations = [
            conv_id for conv_id, data in self.active_conversations.items()
            if data.get("last_activity", datetime.utcnow()) < cutoff_time
        ]
        
        for conv_id in expired_conversations:
            del self.active_conversations[conv_id]
        
        print(f"🧹 Cache limpiado: {len(expired_conversations)} conversaciones eliminadas")