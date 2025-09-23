from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from enum import Enum

Base = declarative_base()

class MetricType(str, Enum):
    COUNT = "count"
    RATE = "rate"
    AVERAGE = "average"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    DURATION = "duration"

class AnalyticsPeriod(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class Metric(Base):
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    value = Column(Float, nullable=False)
    type = Column(String(50), default=MetricType.COUNT)
    unit = Column(String(50))
    description = Column(Text)
    
    # Contexto y segmentación
    period = Column(String(20), default=AnalyticsPeriod.DAILY)
    segment = Column(String(100))  # Por canal, fuente, etc.
    source_system = Column(String(50))  # leads, interactions, workflows
    
    # Relaciones para drill-down
    campaign_id = Column(Integer, ForeignKey("external_campaigns.id"))
    workflow_id = Column(Integer, ForeignKey("workflows.id"))
    
    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    
    # Relationships
    campaign = relationship("ExternalCampaign")
    workflow = relationship("Workflow")

class KPI(Base):
    __tablename__ = "kpis"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    current_value = Column(Float, nullable=False)
    target_value = Column(Float)
    previous_value = Column(Float)
    
    # Métricas de performance
    period = Column(String(20), default=AnalyticsPeriod.DAILY)
    trend = Column(String(20))  # improving, declining, stable
    trend_percentage = Column(Float)  # % de cambio vs período anterior
    
    # Umbrales y alertas
    warning_threshold = Column(Float)
    critical_threshold = Column(Float)
    is_met = Column(Boolean, default=False)
    health_status = Column(String(20))  # healthy, warning, critical
    
    # Metadata
    category = Column(String(50))  # conversion, engagement, revenue, etc.
    calculation_formula = Column(Text)
    last_calculated_at = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Funnel(Base):
    __tablename__ = "funnels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Configuración del funnel
    stages = Column(JSON, nullable=False)  # [{name: "Awareness", criteria: {...}}]
    conversion_window_days = Column(Integer, default=30)
    
    # Performance
    total_conversions = Column(Integer, default=0)
    overall_conversion_rate = Column(Float, default=0.0)
    avg_conversion_time_days = Column(Float, default=0.0)
    
    # Segmentación
    segment_filters = Column(JSON)  # Filtros aplicados al funnel
    date_range = Column(JSON)  # {start_date: ..., end_date: ...}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FunnelStageSnapshot(Base):
    __tablename__ = "funnel_stage_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id"), nullable=False)
    stage_name = Column(String(255), nullable=False)
    stage_order = Column(Integer, nullable=False)
    
    # Métricas de la etapa
    entries_count = Column(Integer, default=0)
    exits_count = Column(Integer, default=0)
    conversions_count = Column(Integer, default=0)
    
    # Tasas de conversión
    conversion_rate = Column(Float, default=0.0)  # vs etapa anterior
    dropoff_rate = Column(Float, default=0.0)
    
    # Tiempos promedio
    avg_time_in_stage_hours = Column(Float, default=0.0)
    
    # Timestamp del snapshot
    snapshot_date = Column(DateTime, nullable=False, index=True)
    period = Column(String(20), default=AnalyticsPeriod.DAILY)
    
    # Relationships
    funnel = relationship("Funnel")

class AnalyticsReport(Base):
    __tablename__ = "analytics_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Configuración del reporte
    report_type = Column(String(50))  # executive, detailed, custom
    period = Column(String(20), default=AnalyticsPeriod.MONTHLY)
    filters = Column(JSON)  # Filtros aplicados
    included_metrics = Column(JSON)  # Métricas a incluir
    
    # Datos del reporte
    report_data = Column(JSON, nullable=False)
    summary_insights = Column(JSON)  # Insights generados por IA
    recommendations = Column(JSON)  # Recomendaciones automáticas
    
    # Generación y distribución
    generated_by = Column(String(100))
    generated_at = Column(DateTime, default=datetime.utcnow)
    scheduled = Column(Boolean, default=False)
    schedule_frequency = Column(String(20))  # daily, weekly, monthly
    
    # Metadata
    is_public = Column(Boolean, default=False)
    shared_with = Column(JSON)  # Usuarios/grupos con acceso
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)