from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from enum import Enum

Base = declarative_base()

class TriggerType(str, Enum):
    SCORE_CHANGE = "score_change"
    TIME_DELAY = "time_delay"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    PAGE_VISITED = "page_visited"
    FORM_SUBMITTED = "form_submitted"
    CHATBOT_INTERACTION = "chatbot_interaction"
    MANUAL = "manual"
    LEAD_CREATED = "lead_created"
    STATUS_CHANGED = "status_changed"
    SEGMENT_ADDED = "segment_added"
    SEGMENT_REMOVED = "segment_removed"

class ActionType(str, Enum):
    SEND_EMAIL = "send_email"
    UPDATE_SCORE = "update_score"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    CHANGE_SEGMENT = "change_segment"
    CREATE_TASK = "create_task"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_FIELD = "update_field"
    WEBHOOK = "webhook"
    WAIT = "wait"
    CONDITION = "condition"
    SEND_SMS = "send_sms"
    SEND_WHATSAPP = "send_whatsapp"
    CREATE_DEAL = "create_deal"
    ASSIGN_AGENT = "assign_agent"

class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowExecutionStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"
    CANCELLED = "cancelled"

class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    version = Column(String(20), default="1.0")
    
    # Trigger configuration
    trigger_type = Column(String(50), nullable=False)  # TriggerType enum
    trigger_conditions = Column(JSON)  # Condiciones para activar el workflow
    trigger_delay_minutes = Column(Integer, default=0)  # Delay después del trigger
    
    # Workflow logic
    steps = Column(JSON, nullable=False)  # Lista de pasos del workflow
    conditions = Column(JSON)  # Condiciones globales para entrar al workflow
    variables = Column(JSON)  # Variables globales del workflow
    
    # Configuration
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=1)  # 1=alta, 2=media, 3=baja
    max_executions_per_lead = Column(Integer, default=1)  # Veces que un lead puede entrar
    cooldown_hours = Column(Integer, default=24)  # Tiempo de espera entre ejecuciones
    timeout_hours = Column(Integer, default=168)  # 7 días por defecto
    
    # A/B Testing
    is_ab_test = Column(Boolean, default=False)
    ab_variant = Column(String(10))  # 'A', 'B', 'C', etc.
    ab_split_percentage = Column(Float, default=100.0)  # % de leads que ven esta variante
    parent_workflow_id = Column(Integer, ForeignKey("workflows.id"))  # Para variantes A/B
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)  # Tags para organización
    category = Column(String(50))  # welcome, nurturing, re_engagement, etc.
    
    # Analytics
    total_triggered = Column(Integer, default=0)
    total_completed = Column(Integer, default=0) 
    total_failed = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # total_completed / total_triggered
    avg_completion_time_hours = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)  # Tasa de conversión del workflow
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = Column(DateTime)
    last_success_at = Column(DateTime)
    
    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow")
    steps_rel = relationship("WorkflowStep", back_populates="workflow")
    variants = relationship("Workflow", remote_side=[id])
    
    __table_args__ = (
        Index('ix_workflow_category_active', 'category', 'is_active'),
        Index('ix_workflow_priority_trigger', 'priority', 'last_triggered_at'),
    )

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    
    # Execution state
    status = Column(String(20), default=WorkflowExecutionStatus.RUNNING, index=True)
    current_step = Column(Integer, default=0)
    current_step_name = Column(String(255))
    
    # Execution data
    trigger_data = Column(JSON)  # Datos que dispararon el workflow
    context = Column(JSON)  # Contexto acumulativo durante la ejecución
    variables = Column(JSON)  # Variables personalizadas del workflow
    execution_path = Column(JSON)  # Camino tomado (para workflows condicionales)
    
    # A/B Testing
    ab_variant = Column(String(10))  # Variante asignada a esta ejecución
    control_group = Column(Boolean, default=False)  # Para grupos de control
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_executed_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
    paused_at = Column(DateTime)
    resumed_at = Column(DateTime)
    next_execution_at = Column(DateTime, index=True)  # Programado para el siguiente step
    timeout_at = Column(DateTime)  # Fecha de expiración
    
    # Analytics
    steps_completed = Column(Integer, default=0)
    total_steps = Column(Integer)
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    tasks_created = Column(Integer, default=0)
    notifications_sent = Column(Integer, default=0)
    
    # Performance
    total_execution_time_minutes = Column(Float, default=0.0)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    lead = relationship("Lead", back_populates="workflow_executions")
    step_logs = relationship("WorkflowStepLog", back_populates="execution")
    email_sends = relationship("EmailSend", back_populates="workflow_execution")
    
    __table_args__ = (
        Index('ix_workflow_execution_status_lead', 'status', 'lead_id'),
        Index('ix_workflow_execution_next_execution', 'next_execution_at', 'status'),
        Index('ix_workflow_execution_timeout', 'timeout_at', 'status'),
    )

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    
    step_number = Column(Integer, nullable=False)
    name = Column(String(255))
    description = Column(Text)
    
    # Action configuration
    action_type = Column(String(50), nullable=False)  # ActionType enum
    action_parameters = Column(JSON, nullable=False)
    action_template = Column(JSON)  # Plantilla para acciones dinámicas
    
    # Timing
    delay_minutes = Column(Integer, default=0)
    delay_conditions = Column(JSON)  # Condiciones para el delay dinámico
    execution_window_hours = Column(Integer, default=24)  # Ventana de ejecución
    
    # Conditional logic
    conditions = Column(JSON)  # Condiciones para ejecutar este step
    skip_if_conditions = Column(JSON)  # Condiciones para saltar este step
    stop_if_conditions = Column(JSON)  # Condiciones para detener el workflow
    
    # A/B Testing por step
    ab_variants = Column(JSON)  # Diferentes variantes de este step
    variant_rules = Column(JSON)  # Reglas para asignar variantes
    
    # Error handling
    retry_strategy = Column(JSON)  # Estrategia de reintentos
    fallback_action = Column(JSON)  # Acción alternativa en caso de error
    
    # Analytics
    executed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_execution_time_ms = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="steps_rel")
    logs = relationship("WorkflowStepLog", back_populates="step")
    
    __table_args__ = (
        Index('ix_workflow_step_number', 'workflow_id', 'step_number'),
        Index('ix_workflow_step_action', 'action_type', 'workflow_id'),
    )

class WorkflowStepLog(Base):
    __tablename__ = "workflow_step_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id"), nullable=False, index=True)
    step_id = Column(Integer, ForeignKey("workflow_steps.id"), index=True)
    step_number = Column(Integer, nullable=False)
    
    # Execution details
    action_type = Column(String(50), nullable=False)
    action_parameters = Column(JSON)
    variant_used = Column(String(10))  # Variante A/B utilizada
    
    # Results
    status = Column(String(20), index=True)  # success, failed, skipped, waiting
    result_data = Column(JSON)  # Resultado de la acción
    error_message = Column(Text)
    error_stack_trace = Column(Text)
    
    # Timing
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    execution_time_ms = Column(Integer)
    
    # Retry information
    retry_attempt = Column(Integer, default=0)
    max_retries = Column(Integer, default=0)
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="step_logs")
    step = relationship("WorkflowStep", back_populates="logs")
    
    __table_args__ = (
        Index('ix_step_log_execution_step', 'execution_id', 'step_number'),
        Index('ix_step_log_status_time', 'status', 'started_at'),
    )

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    preview_text = Column(Text)  # Texto de vista previa
    
    # Template content
    html_content = Column(Text, nullable=False)
    text_content = Column(Text)  # Fallback para clientes sin HTML
    dynamic_sections = Column(JSON)  # Secciones dinámicas condicionales
    
    # Personalization
    variables = Column(JSON)  # Variables disponibles para personalización
    personalization_rules = Column(JSON)  # Reglas de personalización por segmento
    
    # Configuration
    category = Column(String(50), index=True)  # welcome, nurturing, promotional, etc.
    language = Column(String(10), default='es')
    template_type = Column(String(50), default='transactional')  # transactional, marketing
    
    # A/B Testing
    is_ab_test = Column(Boolean, default=False)
    ab_variant = Column(String(10))
    parent_template_id = Column(Integer, ForeignKey("email_templates.id"))
    test_parameters = Column(JSON)  # Parámetros para A/B testing
    
    # Analytics
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    unsubscribed_count = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    complaint_count = Column(Integer, default=0)  # Spam reports
    
    # Rates calculadas
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    click_to_open_rate = Column(Float, default=0.0)  # CTR de los que abrieron
    unsubscribe_rate = Column(Float, default=0.0)
    bounce_rate = Column(Float, default=0.0)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    is_archived = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime)
    
    # Relationships
    variants = relationship("EmailTemplate", remote_side=[id])
    email_sends = relationship("EmailSend", back_populates="template")
    
    __table_args__ = (
        Index('ix_email_template_category_active', 'category', 'is_active'),
        Index('ix_email_template_usage', 'sent_count', 'open_rate'),
    )

class EmailSend(Base):
    __tablename__ = "email_sends"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    workflow_execution_id = Column(Integer, ForeignKey("workflow_executions.id"), index=True)
    
    # Send details
    to_email = Column(String(255), nullable=False, index=True)
    to_name = Column(String(255))
    subject = Column(String(255), nullable=False)
    personalization_data = Column(JSON)  # Datos usados para personalización
    
    # External IDs
    provider_message_id = Column(String(255), index=True)  # ID del proveedor (SendGrid, etc.)
    provider = Column(String(50), default='sendgrid')  # sendgrid, hubspot, etc.
    provider_response = Column(JSON)  # Respuesta completa del proveedor
    
    # Status
    status = Column(String(20), default='queued', index=True)  # queued, sent, delivered, opened, clicked, failed
    status_history = Column(JSON)  # Historial de cambios de estado
    
    # Events tracking
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    opened_at = Column(DateTime)
    first_clicked_at = Column(DateTime)
    last_clicked_at = Column(DateTime)
    unsubscribed_at = Column(DateTime)
    bounced_at = Column(DateTime)
    complained_at = Column(DateTime)  # Marcado como spam
    
    # Analytics
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    links_clicked = Column(JSON)  # URLs clickeadas con sus conteos
    device_info = Column(JSON)  # Información del dispositivo del receptor
    geo_info = Column(JSON)  # Información geográfica del receptor
    
    # A/B Testing
    ab_variant = Column(String(10))
    test_group = Column(String(50))  # Grupo de testing específico
    
    # Error handling
    error_message = Column(Text)
    error_code = Column(String(50))
    retry_count = Column(Integer, default=0)
    final_error = Column(Boolean, default=False)  # Error definitivo (no reintentar)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = relationship("EmailTemplate", back_populates="email_sends")
    lead = relationship("Lead", back_populates="email_sends")
    workflow_execution = relationship("WorkflowExecution", back_populates="email_sends")
    
    __table_args__ = (
        Index('ix_email_send_status_created', 'status', 'created_at'),
        Index('ix_email_send_lead_template', 'lead_id', 'template_id'),
        Index('ix_email_send_provider_message', 'provider', 'provider_message_id'),
    )

class LeadSegment(Base):
    __tablename__ = "lead_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    segment_type = Column(String(50), default='dynamic')  # dynamic, static, system
    
    # Segmentation rules
    rules = Column(JSON, nullable=False)  # Reglas para incluir leads
    is_dynamic = Column(Boolean, default=True)  # Se actualiza automáticamente
    update_frequency_hours = Column(Integer, default=1)  # Frecuencia de actualización
    
    # Configuration
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)
    color = Column(String(7))  # Color hex para UI
    icon = Column(String(50))  # Ícono para UI
    
    # Analytics
    current_lead_count = Column(Integer, default=0)
    total_leads_ever = Column(Integer, default=0)
    growth_trend = Column(String(20))  # increasing, decreasing, stable
    last_calculated_at = Column(DateTime)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    system_managed = Column(Boolean, default=False)  # Segmento del sistema
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead_segments = relationship("LeadSegmentMembership", back_populates="segment")
    
    __table_args__ = (
        Index('ix_lead_segment_type_active', 'segment_type', 'is_active'),
        Index('ix_lead_segment_priority', 'priority', 'current_lead_count'),
    )

class LeadSegmentMembership(Base):
    __tablename__ = "lead_segment_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    segment_id = Column(Integer, ForeignKey("lead_segments.id"), nullable=False, index=True)
    
    # Membership details
    joined_at = Column(DateTime, default=datetime.utcnow, index=True)
    left_at = Column(DateTime)  # Null si sigue en el segmento
    is_active = Column(Boolean, default=True, index=True)
    membership_duration_days = Column(Integer)  # Duración en el segmento
    
    # Metadata
    added_by = Column(String(50), default='system')  # system, manual, workflow
    added_via = Column(String(50)) 