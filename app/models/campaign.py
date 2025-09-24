from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from enum import Enum

Base = declarative_base()

class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"

class CampaignType(str, Enum):
    LEAD_GENERATION = "lead_generation"
    NURTURING = "nurturing"
    RE_ENGAGEMENT = "re_engagement"
    PROMOTIONAL = "promotional"
    EDUCATIONAL = "educational"
    ONBOARDING = "onboarding"

class ChannelType(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    PUSH = "push"
    SOCIAL = "social"
    ADS = "ads"
    WEBINAR = "webinar"

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    type = Column(String(50), default=CampaignType.LEAD_GENERATION, index=True)
    
    # Configuración de la campaña
    status = Column(String(20), default=CampaignStatus.DRAFT, index=True)
    channel = Column(String(20), default=ChannelType.EMAIL)
    target_audience = Column(JSON)  # Reglas de segmentación
    exclusion_rules = Column(JSON)  # Reglas de exclusión
    
    # Presupuesto y programación
    budget = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    start_date = Column(DateTime, index=True)
    end_date = Column(DateTime, index=True)
    timezone = Column(String(50), default="UTC")
    
    # Objetivos y métricas
    goal_type = Column(String(50))  # leads, conversions, revenue, etc.
    goal_value = Column(Float, default=0.0)
    kpi_targets = Column(JSON)  # {open_rate: 20, click_rate: 5, conversion_rate: 2}
    
    # Contenido y creativos
    subject_line = Column(String(255))  # Para email
    message_content = Column(Text)
    creative_assets = Column(JSON)  # Imágenes, videos, etc.
    landing_page_url = Column(String(500))
    utm_parameters = Column(JSON)  # Parámetros UTM para tracking
    
    # Automatización
    workflow_id = Column(Integer, ForeignKey("workflows.id"))  # Workflow asociado
    is_automated = Column(Boolean, default=False)
    trigger_conditions = Column(JSON)  # Condiciones para activación automática
    
    # A/B Testing
    is_ab_test = Column(Boolean, default=False)
    ab_test_config = Column(JSON)  # Configuración del A/B test
    winning_variant = Column(String(10))  # Variante ganadora
    
    # Performance tracking
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue_generated = Column(Float, default=0.0)
    cost_per_click = Column(Float, default=0.0)
    cost_per_conversion = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    
    # Analytics
    open_rate = Column(Float, default=0.0)
    click_through_rate = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    bounce_rate = Column(Float, default=0.0)
    unsubscribe_rate = Column(Float, default=0.0)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    is_template = Column(Boolean, default=False)  # Si es una plantilla reutilizable
    template_id = Column(Integer, ForeignKey("campaigns.id"))  # Si se basa en una plantilla
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sent_at = Column(DateTime)
    
    # Relationships
    workflow = relationship("Workflow")
    template = relationship("Campaign", remote_side=[id])
    variants = relationship("Campaign", remote_side=[id])
    campaign_leads = relationship("CampaignLead", back_populates="campaign")
    segments = relationship("CampaignSegment", back_populates="campaign")
    performances = relationship("CampaignPerformance", back_populates="campaign")
    
    __table_args__ = (
        Index('ix_campaign_status_type', 'status', 'type'),
        Index('ix_campaign_dates', 'start_date', 'end_date'),
    )

class CampaignLead(Base):
    __tablename__ = "campaign_leads"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    
    # Estado de participación
    status = Column(String(20), default="targeted")  # targeted, sent, delivered, opened, clicked, converted, bounced, unsubscribed
    added_at = Column(DateTime, default=datetime.utcnow, index=True)
    removed_at = Column(DateTime)  # Si fue excluido posteriormente
    
    # Tracking de interacciones
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    opened_at = Column(DateTime)
    first_clicked_at = Column(DateTime)
    converted_at = Column(DateTime)
    bounced_at = Column(DateTime)
    unsubscribed_at = Column(DateTime)
    
    # Métricas individuales
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    conversion_value = Column(Float, default=0.0)
    
    # Datos de personalización
    personalization_data = Column(JSON)  # Datos usados para personalizar el mensaje
    dynamic_content = Column(JSON)  # Contenido dinámico mostrado a este lead
    
    # A/B Testing
    variant = Column(String(10))  # Variante A/B asignada
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_leads")
    lead = relationship("Lead", back_populates="campaign_leads")
    
    __table_args__ = (
        Index('ix_campaign_lead_status', 'campaign_id', 'status'),
        Index('ix_campaign_lead_tracking', 'lead_id', 'sent_at'),
    )

class CampaignSegment(Base):
    __tablename__ = "campaign_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    segment_id = Column(Integer, ForeignKey("lead_segments.id"), nullable=False, index=True)
    
    # Configuración de segmento en la campaña
    inclusion_type = Column(String(20), default="include")  # include, exclude
    segment_rules = Column(JSON)  # Reglas específicas para esta campaña
    
    # Estadísticas
    estimated_size = Column(Integer, default=0)  # Tamaño estimado del segmento
    actual_size = Column(Integer, default=0)  # Tamaño real después de aplicar reglas
    
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by = Column(String(100))
    
    # Relationships
    campaign = relationship("Campaign", back_populates="segments")
    segment = relationship("LeadSegment")
    
    __table_args__ = (
        Index('ix_campaign_segment', 'campaign_id', 'segment_id'),
    )

class CampaignPerformance(Base):
    __tablename__ = "campaign_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    
    # Período de reporting
    period_date = Column(DateTime, nullable=False, index=True)  # Fecha del período (diario, semanal, etc.)
    period_type = Column(String(20), default="daily")  # daily, weekly, monthly
    
    # Métricas básicas
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    
    # Métricas calculadas
    click_through_rate = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    cost_per_click = Column(Float, default=0.0)
    cost_per_conversion = Column(Float, default=0.0)
    return_on_investment = Column(Float, default=0.0)
    
    # Métricas de engagement
    open_rate = Column(Float, default=0.0)  # Para email
    bounce_rate = Column(Float, default=0.0)
    unsubscribe_rate = Column(Float, default=0.0)
    reply_rate = Column(Float, default=0.0)  # Para email/whatsapp
    
    # Métricas de calidad
    lead_quality_score = Column(Float, default=0.0)  # Score promedio de leads generados
    conversion_quality_score = Column(Float, default=0.0)  # Calidad de conversiones
    
    # Segmentación adicional
    segment_breakdown = Column(JSON)  # Desglose por segmentos
    channel_breakdown = Column(JSON)  # Desglose por canales (si campaña multi-canal)
    
    # Timestamps
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="performances")
    
    __table_args__ = (
        Index('ix_campaign_performance_date', 'campaign_id', 'period_date'),
        Index('ix_performance_period_type', 'period_type', 'period_date'),
    )

class CampaignTemplate(Base):
    __tablename__ = "campaign_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    category = Column(String(50))  # welcome, nurturing, promotional, etc.
    
    # Configuración de la plantilla
    channel = Column(String(20), default=ChannelType.EMAIL)
    target_audience = Column(JSON)  # Audiencia objetivo por defecto
    default_content = Column(JSON)  # Contenido por defecto
    
    # Configuración de workflow
    workflow_template = Column(JSON)  # Plantilla de workflow asociada
    automation_rules = Column(JSON)  # Reglas de automatización
    
    # Variables de personalización
    available_variables = Column(JSON)  # Variables disponibles para personalización
    dynamic_sections = Column(JSON)  # Secciones dinámicas configurables
    
    # Metadata
    is_active = Column(Boolean, default=True)
    version = Column(String(20), default="1.0")
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # Tasa de éxito histórica
    
    created_by = Column(String(100))
    tags = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime)
    
    __table_args__ = (
        Index('ix_template_category_channel', 'category', 'channel'),
        Index('ix_template_usage', 'usage_count', 'is_active'),
    )

class A_BTest(Base):
    __tablename__ = "ab_tests"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    test_name = Column(String(255), nullable=False)
    
    # Configuración del test
    test_type = Column(String(50))  # subject_line, content, timing, etc.
    variants = Column(JSON, nullable=False)  # Lista de variantes
    traffic_allocation = Column(JSON)  # % de tráfico por variante
    
    # Métricas de evaluación
    primary_metric = Column(String(50))  # click_rate, conversion_rate, etc.
    secondary_metrics = Column(JSON)  # Métricas secundarias a considerar
    confidence_level = Column(Float, default=0.95)  # Nivel de confianza estadística
    
    # Resultados
    winner = Column(String(10))  # Variante ganadora
    confidence = Column(Float)  # Confianza del resultado
    improvement = Column(Float)  #% de mejora vs control
    is_significant = Column(Boolean)  # Si el resultado es estadísticamente significativo
    
    # Timing
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    duration_days = Column(Integer)
    
    # Estadísticas
    sample_size = Column(Integer, default=0)
    conversions_control = Column(Integer, default=0)
    conversions_variant = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    campaign = relationship("Campaign")
    
    __table_args__ = (
        Index('ix_ab_test_campaign', 'campaign_id', 'test_type'),
        Index('ix_ab_test_dates', 'start_date', 'end_date'),
    )

# Funciones de utilidad para campañas
def create_utm_parameters(campaign_name: str, source: str, medium: str, content: str = None) -> dict:
    """Crea parámetros UTM para tracking de campañas"""
    
    import urllib.parse
    from datetime import datetime
    
    utm_params = {
        'utm_source': source,
        'utm_medium': medium,
        'utm_campaign': urllib.parse.quote(campaign_name.lower().replace(' ', '_')),
        'utm_id': f"campaign_{datetime.utcnow().strftime('%Y%m%d')}"
    }
    
    if content:
        utm_params['utm_content'] = content
    
    return utm_params

def calculate_campaign_roi(revenue: float, cost: float) -> float:
    """Calcula el ROI de una campaña"""
    if cost == 0:
        return float('inf') if revenue > 0 else 0.0
    return ((revenue - cost) / cost) * 100

def estimate_campaign_size(segments: list, exclusion_rules: list = None) -> int:
    """Estima el tamaño de una campaña basado en segmentos"""
    # Esta función se integraría con el servicio de segmentación
    # Por ahora retorna un estimado básico
    estimated_size = sum(segment.get('estimated_size', 0) for segment in segments)
    
    # Aplicar exclusiones (reducción estimada del 10%)
    if exclusion_rules:
        estimated_size *= 0.9
    
    return int(estimated_size)

def validate_campaign_schedule(start_date: datetime, end_date: datetime) -> dict:
    """Valida las fechas de una campaña"""
    now = datetime.utcnow()
    validation = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    if start_date < now:
        validation['is_valid'] = False
        validation['errors'].append("Start date cannot be in the past")
    
    if end_date <= start_date:
        validation['is_valid'] = False
        validation['errors'].append("End date must be after start date")
    
    campaign_duration = (end_date - start_date).days
    if campaign_duration > 90:
        validation['warnings'].append("Campaign duration exceeds 90 days")
    
    if start_date.weekday() in [5, 6]:  # Weekend
        validation['warnings'].append("Campaign starts on a weekend")
    
    return validation

def generate_campaign_performance_report(campaign_id: int, start_date: datetime, end_date: datetime) -> dict:
    """Genera un reporte de performance para una campaña"""
    # Esta función se implementaría con queries reales a la base de datos
    # Por ahora retorna una estructura básica
    
    report = {
        'campaign_id': campaign_id,
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': (end_date - start_date).days
        },
        'summary': {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'revenue': 0.0,
            'cost': 0.0,
            'roi': 0.0
        },
        'daily_breakdown': [],
        'segment_performance': [],
        'recommendations': []
    }
    
    return report