from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
import uuid

Base = declarative_base()

class ConversationStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed" 
    ESCALATED = "escalated"
    WAITING = "waiting"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    LOCATION = "location"

class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    WEB_CHAT = "web_chat"
    FACEBOOK = "facebook"

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), index=True)  # UUID para agrupar mensajes de una conversación
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    
    # Mensaje del usuario
    user_message = Column(Text)
    user_message_type = Column(String(50), default=MessageType.TEXT)
    
    # Respuesta del bot
    bot_response = Column(Text)
    response_time_ms = Column(Integer)  # Tiempo de respuesta en milisegundos
    
    # Metadatos de la plataforma
    platform = Column(String(50))  # whatsapp, telegram, web_chat
    platform_message_id = Column(String(255))  # ID del mensaje en la plataforma
    phone_number = Column(String(20))  # Para WhatsApp
    chat_id = Column(String(255))  # Para Telegram
    
    # Análisis de IA
    intent_detected = Column(String(100))  # "product_inquiry", "pricing", "support", etc.
    confidence_score = Column(Float)  # 0-1, confianza en la clasificación de intención
    buying_signals_detected = Column(Boolean, default=False)
    sentiment_score = Column(Float)  # -1 a 1, sentiment del mensaje
    
    # Estados de conversación
    conversation_status = Column(String(50), default=ConversationStatus.ACTIVE)
    escalated_to_human = Column(Boolean, default=False)
    escalation_reason = Column(String(255))
    assigned_agent = Column(String(100))
    
    # Contexto adicional
    session_context = Column(JSON)  # Contexto de la sesión (variables, estado)
    metadata = Column(JSON)  # Metadatos adicionales (ubicación, dispositivo, etc.)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead", back_populates="interactions")

class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    
    # Resumen de la conversación
    summary = Column(Text)  # Resumen generado por IA
    total_messages = Column(Integer, default=0)
    duration_minutes = Column(Integer)  # Duración total de la conversación
    
    # Análisis de la conversación
    primary_intent = Column(String(100))
    intents_detected = Column(JSON)  # Lista de todas las intenciones detectadas
    conversion_achieved = Column(Boolean, default=False)
    conversion_type = Column(String(50))  # "demo_scheduled", "purchase", "info_requested"
    
    # Scoring y métricas
    engagement_score = Column(Float)  # Qué tan comprometido estuvo el lead
    satisfaction_score = Column(Float)  # Basado en sentiment y respuestas
    lead_quality_score = Column(Float)  # Score actualizado post-conversación
    
    # Estados
    final_status = Column(String(50))
    outcome = Column(String(255))  # Resultado final de la conversación
    next_action = Column(String(255))  # Próxima acción recomendada
    
    # Timestamps
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead", back_populates="conversation_summaries")

class QuickReply(Base):
    __tablename__ = "quick_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    trigger_keywords = Column(JSON)  # Keywords que activan esta respuesta
    response_text = Column(Text)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Funciones de utilidad para el modelo

def generate_conversation_id() -> str:
    """Genera un ID único para una nueva conversación"""
    return str(uuid.uuid4())

def get_conversation_context(conversation_id: str, limit: int = 10) -> dict:
    """
    Obtiene el contexto de una conversación para la IA
    
    Args:
        conversation_id: ID de la conversación
        limit: Número máximo de mensajes a incluir
        
    Returns:
        dict: Contexto formateado para la IA
    """
    # Esta función se implementará en el servicio
    pass