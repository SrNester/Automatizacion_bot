from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float, Index
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
    ARCHIVED = "archived"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    BUTTON = "button"
    QUICK_REPLY = "quick_reply"

class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    WEB_CHAT = "web_chat"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    SMS = "sms"
    EMAIL = "email"

class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), index=True)  # UUID para agrupar mensajes de una conversación
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    
    # Mensaje del usuario
    user_message = Column(Text)
    user_message_type = Column(String(50), default=MessageType.TEXT)
    user_message_language = Column(String(10))  # es, en, pt, etc.
    
    # Respuesta del sistema
    bot_response = Column(Text)
    response_time_ms = Column(Integer)  # Tiempo de respuesta en milisegundos
    response_language = Column(String(10))
    
    # Metadatos de la plataforma
    platform = Column(String(50))  # whatsapp, telegram, web_chat
    platform_message_id = Column(String(255), index=True)  # ID del mensaje en la plataforma
    phone_number = Column(String(20))  # Para WhatsApp
    chat_id = Column(String(255))  # Para Telegram
    user_agent = Column(Text)  # Información del dispositivo/navegador
    
    # Análisis de IA
    intent_detected = Column(String(100))  # "product_inquiry", "pricing", "support", etc.
    confidence_score = Column(Float)  # 0-1, confianza en la clasificación de intención
    secondary_intents = Column(JSON)  # Otras intenciones detectadas con sus scores
    buying_signals_detected = Column(Boolean, default=False)
    buying_signal_strength = Column(Float)  # 0-1, fuerza de la señal de compra
    sentiment_score = Column(Float)  # -1 a 1, sentiment del mensaje
    sentiment_label = Column(String(20))  # positive, neutral, negative
    
    # Estados de conversación
    conversation_status = Column(String(50), default=ConversationStatus.ACTIVE)
    escalated_to_human = Column(Boolean, default=False)
    escalation_reason = Column(String(255))
    escalation_priority = Column(String(20), default="medium")  # low, medium, high, urgent
    assigned_agent = Column(String(100))
    agent_response = Column(Text)  # Respuesta del agente humano
    
    # Contexto adicional
    session_context = Column(JSON)  # Contexto de la sesión (variables, estado)
    metadata = Column(JSON)  # Metadatos adicionales (ubicación, dispositivo, etc.)
    tags = Column(JSON)  # Etiquetas para categorización
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_timestamp = Column(DateTime)  # Timestamp original del mensaje
    
    # Relationships
    lead = relationship("Lead", back_populates="interactions")
    intent_classifications = relationship("IntentClassification", back_populates="interaction")
    
    # Índices para mejor performance
    __table_args__ = (
        Index('ix_interaction_conversation_platform', 'conversation_id', 'platform'),
        Index('ix_interaction_lead_timestamp', 'lead_id', 'created_at'),
        Index('ix_interaction_intent_status', 'intent_detected', 'conversation_status'),
    )

class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    
    # Resumen de la conversación
    summary = Column(Text)  # Resumen generado por IA
    key_points = Column(JSON)  # Puntos clave extraídos
    action_items = Column(JSON)  # Acciones identificadas
    
    # Métricas de la conversación
    total_messages = Column(Integer, default=0)
    user_message_count = Column(Integer, default=0)
    bot_message_count = Column(Integer, default=0)
    duration_minutes = Column(Float)  # Duración total de la conversación
    avg_response_time_seconds = Column(Float)  # Tiempo promedio de respuesta
    
    # Análisis de la conversación
    primary_intent = Column(String(100))
    intents_detected = Column(JSON)  # Lista de todas las intenciones detectadas
    overall_sentiment = Column(String(20))
    sentiment_trend = Column(JSON)  # Evolución del sentiment durante la conversación
    
    # Resultados de la conversación
    conversion_achieved = Column(Boolean, default=False)
    conversion_type = Column(String(50))  # "demo_scheduled", "purchase", "info_requested"
    conversion_value = Column(Float, default=0.0)  # Valor estimado de la conversión
    
    # Scoring y métricas
    engagement_score = Column(Float)  # Qué tan comprometido estuvo el lead (0-1)
    satisfaction_score = Column(Float)  # Basado en sentiment y respuestas (0-1)
    lead_quality_score = Column(Float)  # Score actualizado post-conversación (0-100)
    resolution_score = Column(Float)  # Qué tan bien se resolvió la consulta (0-1)
    
    # Estados
    final_status = Column(String(50))
    outcome = Column(String(255))  # Resultado final de la conversación
    next_action = Column(String(255))  # Próxima acción recomendada
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(DateTime)
    
    # Timestamps
    started_at = Column(DateTime, index=True)
    ended_at = Column(DateTime)
    last_message_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead", back_populates="conversation_summaries")
    tags = relationship("ConversationTag", back_populates="conversation")
    
    __table_args__ = (
        Index('ix_conversation_lead_status', 'lead_id', 'final_status'),
        Index('ix_conversation_date_outcome', 'started_at', 'outcome'),
    )

class IntentClassification(Base):
    __tablename__ = "intent_classifications"
    
    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, ForeignKey("interactions.id"), nullable=False)
    intent = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    model_version = Column(String(50))
    features_used = Column(JSON)  # Características usadas para la clasificación
    classification_metadata = Column(JSON)  # Metadatos adicionales del modelo
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    interaction = relationship("Interaction", back_populates="intent_classifications")
    
    __table_args__ = (
        Index('ix_intent_classification_interaction', 'interaction_id', 'intent'),
    )

class ConversationTag(Base):
    __tablename__ = "conversation_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), ForeignKey("conversation_summaries.conversation_id"), nullable=False)
    tag = Column(String(100), nullable=False, index=True)
    tag_category = Column(String(50))  # topic, sentiment, action, custom
    confidence = Column(Float, default=1.0)  # Para tags generados por IA
    added_by = Column(String(100), default='system')  # system, agent, ai
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = relationship("ConversationSummary", back_populates="tags")
    
    __table_args__ = (
        Index('ix_conversation_tag_category', 'tag', 'tag_category'),
    )

class QuickReply(Base):
    __tablename__ = "quick_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    trigger_keywords = Column(JSON)  # Keywords que activan esta respuesta
    response_text = Column(Text, nullable=False)
    response_type = Column(String(50), default="text")  # text, buttons, list, etc.
    response_buttons = Column(JSON)  # Botones para respuestas rápidas
    platform = Column(String(50))  # Plataforma específica o "all"
    
    # Configuración
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    category = Column(String(50))  # greeting, pricing, support, etc.
    
    # Analytics
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # Basado en engagement posterior
    last_used_at = Column(DateTime)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_quick_reply_platform_category', 'platform', 'category'),
        Index('ix_quick_reply_usage_active', 'usage_count', 'is_active'),
    )

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    platform = Column(String(50), nullable=False)
    
    # Estado de la sesión
    status = Column(String(20), default="active")  # active, idle, closed, timeout
    page_url = Column(Text)  # URL donde inició la sesión
    referrer = Column(Text)  # Página de referencia
    
    # Métricas de la sesión
    message_count = Column(Integer, default=0)
    session_duration_seconds = Column(Integer, default=0)
    first_response_time_seconds = Column(Integer)
    
    # Contexto de la sesión
    initial_intent = Column(String(100))
    browser_info = Column(JSON)
    geo_location = Column(JSON)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_activity_at = Column(DateTime)
    ended_at = Column(DateTime)
    
    # Relationships
    lead = relationship("Lead")
    
    __table_args__ = (
        Index('ix_chat_session_platform_status', 'platform', 'status'),
        Index('ix_chat_session_activity', 'last_activity_at', 'status'),
    )

# Funciones de utilidad para el modelo
def generate_conversation_id() -> str:
    """Genera un ID único para una nueva conversación"""
    return f"conv_{uuid.uuid4().hex[:16]}"

def calculate_engagement_score(interactions: list) -> float:
    """
    Calcula un score de engagement basado en las interacciones
    
    Args:
        interactions: Lista de interacciones de la conversación
        
    Returns:
        float: Score de engagement entre 0 y 1
    """
    if not interactions:
        return 0.0
    
    # Factores que afectan el engagement
    factors = {
        'message_count': min(len(interactions) / 10, 1.0),  # Máx 10 mensajes
        'response_time': 0.0,  # Se calculará
        'message_length': 0.0,  # Se calculará
        'intent_variety': 0.0,  # Se calculará
    }
    
    # Calcular longitud promedio de mensajes
    total_length = sum(len(interaction.user_message or '') for interaction in interactions)
    avg_length = total_length / len(interactions)
    factors['message_length'] = min(avg_length / 100, 1.0)  # Máx 100 caracteres
    
    # Calcular variedad de intenciones
    intents = set(interaction.intent_detected for interaction in interactions if interaction.intent_detected)
    factors['intent_variety'] = min(len(intents) / 5, 1.0)  # Máx 5 intenciones diferentes
    
    # Ponderar los factores
    weights = {
        'message_count': 0.3,
        'message_length': 0.2,
        'intent_variety': 0.3,
        'response_time': 0.2
    }
    
    engagement_score = sum(factors[factor] * weights[factor] for factor in factors)
    return min(engagement_score, 1.0)

def detect_conversation_pattern(interactions: list) -> dict:
    """
    Detecta patrones en una conversación
    
    Args:
        interactions: Lista de interacciones ordenadas por tiempo
        
    Returns:
        dict: Patrones detectados
    """
    patterns = {
        'quick_question': False,
        'extended_discussion': False,
        'escalation_pattern': False,
        'buying_signals': False,
        'frustration_signals': False
    }
    
    if len(interactions) <= 3:
        patterns['quick_question'] = True
    
    if len(interactions) >= 10:
        patterns['extended_discussion'] = True
    
    # Detectar señales de compra
    buying_intents = ['pricing', 'demo', 'trial', 'purchase', 'buy']
    for interaction in interactions:
        if interaction.intent_detected in buying_intents:
            patterns['buying_signals'] = True
            break
    
    # Detectar frustración (sentiment negativo consecutivo)
    negative_count = 0
    for interaction in interactions[-3:]:  # Últimas 3 interacciones
        if interaction.sentiment_label == SentimentLabel.NEGATIVE:
            negative_count += 1
    
    if negative_count >= 2:
        patterns['frustration_signals'] = True
    
    return patterns