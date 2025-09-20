from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
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

class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Trigger configuration
    trigger_type = Column(String(50), nullable=False)  # TriggerType enum
    trigger_conditions = Column(JSON)  # Condiciones para activar el workflow
    
    # Workflow logic
    steps = Column(JSON, nullable=False)  # Lista de pasos del workflow
    conditions = Column(JSON)  # Condiciones globales para entrar al workflow
    
    # Configuration
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 1=alta, 2=media, 3=baja
    max_executions_per_lead = Column(Integer, default=1)  # Veces que un lead puede entrar
    cooldown_hours = Column(Integer, default=24)  # Tiempo de espera entre ejecuciones
    
    # A/B Testing
    is_ab_test = Column(Boolean, default=False)
    ab_variant = Column(String(10))  # 'A', 'B', 'C', etc.
    ab_split_percentage = Column(Float, default=100.0)  # % de leads que ven esta variante
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)  # Tags para organización
    category = Column(String(50))  # welcome, nurturing, re_engagement, etc.
    
    # Analytics
    total_triggered = Column(Integer, default=0)
    total_completed = Column(Integer, default=0) 
    total_failed = Column(Integer, default=0)
    avg_completion_time_hours = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = Column(DateTime)
    
    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow")
    steps_rel = relationship("WorkflowStep", back_populates="workflow")

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    
    # Execution state
    status = Column(String(20), default=WorkflowStatus.ACTIVE)
    current_step = Column(Integer, default=0)
    
    # Execution data
    trigger_data = Column(JSON)  # Datos que dispararon el workflow
    context = Column(JSON)  # Contexto acumulativo durante la ejecución
    variables = Column(JSON)  # Variables personalizadas del workflow
    
    # A/B Testing
    ab_variant = Column(String(10))  # Variante asignada a esta ejecución
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    last_executed_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
    paused_at = Column(DateTime)
    resumed_at = Column(DateTime)
    next_execution_at = Column(DateTime)  # Programado para el siguiente step
    
    # Analytics
    steps_completed = Column(Integer, default=0)
    total_steps = Column(Integer)
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    lead = relationship("Lead", back_populates="workflow_executions")
    step_logs = relationship("WorkflowStepLog", back_populates="execution")

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    
    step_number = Column(Integer, nullable=False)
    name = Column(String(255))
    description = Column(Text)
    
    # Action configuration
    action_type = Column(String(50), nullable=False)  # ActionType enum
    action_parameters = Column(JSON, nullable=False)
    
    # Timing
    delay_minutes = Column(Integer, default=0)
    delay_conditions = Column(JSON)  # Condiciones para el delay dinámico
    
    # Conditional logic
    conditions = Column(JSON)  # Condiciones para ejecutar este step
    skip_if_conditions = Column(JSON)  # Condiciones para saltar este step
    
    # A/B Testing por step
    ab_variants = Column(JSON)  # Diferentes variantes de este step
    
    # Analytics
    executed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_execution_time_ms = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="steps_rel")
    logs = relationship("WorkflowStepLog", back_populates="step")

class WorkflowStepLog(Base):
    __tablename__ = "workflow_step_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("workflow_steps.id"))
    step_number = Column(Integer, nullable=False)
    
    # Execution details
    action_type = Column(String(50), nullable=False)
    action_parameters = Column(JSON)
    
    # Results
    status = Column(String(20))  # success, failed, skipped
    result_data = Column(JSON)  # Resultado de la acción
    error_message = Column(Text)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    execution_time_ms = Column(Integer)
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="step_logs")
    step = relationship("WorkflowStep", back_populates="logs")

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    
    # Template content
    html_content = Column(Text, nullable=False)
    text_content = Column(Text)  # Fallback para clientes sin HTML
    
    # Personalization
    variables = Column(JSON)  # Variables disponibles para personalización
    dynamic_content = Column(JSON)  # Contenido dinámico basado en segmentos
    
    # Configuration
    category = Column(String(50))  # welcome, nurturing, promotional, etc.
    language = Column(String(10), default='es')
    
    # A/B Testing
    is_ab_test = Column(Boolean, default=False)
    ab_variant = Column(String(10))
    parent_template_id = Column(Integer, ForeignKey("email_templates.id"))
    
    # Analytics
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    unsubscribed_count = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    
    # Rates calculadas
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    unsubscribe_rate = Column(Float, default=0.0)
    bounce_rate = Column(Float, default=0.0)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    variants = relationship("EmailTemplate", remote_side=[id])
    email_sends = relationship("EmailSend", back_populates="template")

class EmailSend(Base):
    __tablename__ = "email_sends"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    workflow_execution_id = Column(Integer, ForeignKey("workflow_executions.id"))
    
    # Send details
    to_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    
    # External IDs
    provider_message_id = Column(String(255))  # ID del proveedor (SendGrid, etc.)
    provider = Column(String(50), default='sendgrid')  # sendgrid, hubspot, etc.
    
    # Status
    status = Column(String(20), default='queued')  # queued, sent, delivered, opened, clicked, failed
    
    # Events tracking
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    opened_at = Column(DateTime)
    first_clicked_at = Column(DateTime)
    unsubscribed_at = Column(DateTime)
    bounced_at = Column(DateTime)
    
    # Analytics
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    links_clicked = Column(JSON)  # URLs clickeadas
    
    # A/B Testing
    ab_variant = Column(String(10))
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = relationship("EmailTemplate", back_populates="email_sends")
    lead = relationship("Lead", back_populates="email_sends")
    workflow_execution = relationship("WorkflowExecution")

class LeadSegment(Base):
    __tablename__ = "lead_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Segmentation rules
    rules = Column(JSON, nullable=False)  # Reglas para incluir leads
    is_dynamic = Column(Boolean, default=True)  # Se actualiza automáticamente
    
    # Configuration
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    color = Column(String(7))  # Color hex para UI
    
    # Analytics
    current_lead_count = Column(Integer, default=0)
    total_leads_ever = Column(Integer, default=0)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_calculated_at = Column(DateTime)
    
    # Relationships
    lead_segments = relationship("LeadSegmentMembership", back_populates="segment")

class LeadSegmentMembership(Base):
    __tablename__ = "lead_segment_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("lead_segments.id"), nullable=False)
    
    # Membership details
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime)  # Null si sigue en el segmento
    is_active = Column(Boolean, default=True)
    
    # Metadata
    added_by = Column(String(50), default='system')  # system, manual, workflow
    reason = Column(String(255))  # Razón por la cual se agregó al segmento
    
    # Relationships
    lead = relationship("Lead", back_populates="segment_memberships")
    segment = relationship("LeadSegment", back_populates="lead_segments")

# Funciones de utilidad para workflows

def create_simple_email_workflow(name: str, 
                                trigger_type: TriggerType,
                                email_template_id: int,
                                delay_minutes: int = 0,
                                conditions: list = None) -> dict:
    """Crea un workflow simple de un email"""
    
    workflow_data = {
        "name": name,
        "trigger_type": trigger_type,
        "steps": [
            {
                "step_number": 1,
                "action_type": ActionType.SEND_EMAIL,
                "parameters": {
                    "template_id": email_template_id
                },
                "delay_minutes": delay_minutes
            }
        ],
        "conditions": conditions or [],
        "is_active": True,
        "category": "simple_email"
    }
    
    return workflow_data

def create_nurturing_sequence_workflow(name: str,
                                     email_templates: list,
                                     delays_days: list,
                                     trigger_conditions: dict = None) -> dict:
    """Crea un workflow de secuencia de nurturing"""
    
    steps = []
    for i, (template_id, delay_days) in enumerate(zip(email_templates, delays_days)):
        steps.append({
            "step_number": i + 1,
            "action_type": ActionType.SEND_EMAIL,
            "parameters": {
                "template_id": template_id
            },
            "delay_minutes": delay_days * 24 * 60  # Convertir días a minutos
        })
    
    workflow_data = {
        "name": name,
        "trigger_type": TriggerType.SCORE_CHANGE,
        "steps": steps,
        "conditions": [trigger_conditions] if trigger_conditions else [],
        "is_active": True,
        "category": "nurturing_sequence"
    }
    
    return workflow_data

def create_scoring_workflow(name: str,
                           score_threshold: int,
                           actions: list) -> dict:
    """Crea un workflow basado en score threshold"""
    
    workflow_data = {
        "name": name,
        "trigger_type": TriggerType.SCORE_CHANGE,
        "conditions": [
            {
                "field": "score",
                "operator": "gte",
                "value": score_threshold
            }
        ],
        "steps": actions,
        "is_active": True,
        "category": "scoring_based"
    }
    
    return workflow_data