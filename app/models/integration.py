from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

Base = declarative_base()

class IntegrationProvider(str, Enum):
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    LINKEDIN_ADS = "linkedin_ads"
    HUBSPOT = "hubspot"
    PIPEDRIVE = "pipedrive"
    SALESFORCE = "salesforce"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SMS_TWILIO = "sms_twilio"
    ZAPIER = "zapier"
    MAKE = "make"
    SLACK = "slack"
    TEAMS = "teams"

class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"

class SyncDirection(str, Enum):
    PUSH = "push"  # Internal → External
    PULL = "pull"  # External → Internal
    BIDIRECTIONAL = "bidirectional"

class LeadStatus(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    phone = Column(String)
    company = Column(String)
    job_title = Column(String)
    
    # Lead Scoring
    score = Column(Float, default=0.0)
    status = Column(String, default=LeadStatus.COLD)
    
    # Tracking
    source = Column(String)  # meta_ads, google_ads, linkedin, website
    utm_campaign = Column(String)
    first_interaction = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    
    # Preferences
    interests = Column(Text)  # JSON string
    budget_range = Column(String)
    timeline = Column(String)
    
    # Flags
    is_qualified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Integrations IDs
    hubspot_id = Column(String, index=True)
    pipedrive_id = Column(String, index=True)
    salesforce_id = Column(String, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    interactions = relationship("Interaction", back_populates="lead")
    external_leads = relationship("ExternalLead", back_populates="lead")
    crm_syncs = relationship("CRMSync", back_populates="lead")
    workflow_executions = relationship("WorkflowExecution", back_populates="lead")
    email_sends = relationship("EmailSend", back_populates="lead")
    segment_memberships = relationship("LeadSegmentMembership", back_populates="lead")
    campaign_leads = relationship("CampaignLead", back_populates="lead")  # ✅ NUEVA RELACIÓN

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)  # IntegrationProvider enum
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Configuration
    config = Column(JSON, nullable=False)  # API keys, endpoints, settings
    is_active = Column(Boolean, default=True)
    is_webhook_configured = Column(Boolean, default=False)
    webhook_url = Column(String(500))
    
    # Health monitoring
    last_health_check = Column(DateTime)
    health_status = Column(String(20), default="unknown")  # healthy, unhealthy, unknown
    last_error = Column(Text)
    
    # Usage statistics
    total_syncs = Column(Integer, default=0)
    successful_syncs = Column(Integer, default=0)
    failed_syncs = Column(Integer, default=0)
    last_sync_at = Column(DateTime)
    
    # Rate limiting
    rate_limit_per_hour = Column(Integer, default=1000)
    current_hour_usage = Column(Integer, default=0)
    rate_limit_reset_at = Column(DateTime)
    
    # Metadata
    created_by = Column(String(100))
    tags = Column(JSON)  # Para organización
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sync_logs = relationship("SyncLog", back_populates="integration")
    external_leads = relationship("ExternalLead", back_populates="integration")

class ExternalLead(Base):
    __tablename__ = "external_leads"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # External system data
    external_id = Column(String(255), nullable=False, index=True)
    external_source = Column(String(50), nullable=False)  # meta_ads, google_ads, etc.
    external_form_id = Column(String(255))  # Form ID, Campaign ID, etc.
    external_campaign_id = Column(String(255))
    external_ad_id = Column(String(255))
    
    # Lead data from external system
    raw_data = Column(JSON)  # Datos originales sin procesar
    processed_data = Column(JSON)  # Datos procesados y mapeados
    
    # Attribution data
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(255))
    utm_content = Column(String(255))
    utm_term = Column(String(255))
    
    # Quality metrics
    data_quality_score = Column(Float, default=0.0)  # 0-1 based on completeness
    attribution_confidence = Column(Float, default=1.0)  # Confidence in attribution
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_errors = Column(JSON)  # Errores durante el procesamiento
    
    # Timestamps
    external_created_at = Column(DateTime)  # When created in external system
    processed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead", back_populates="external_leads")
    integration = relationship("Integration", back_populates="external_leads")

class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"))
    
    # Sync details
    integration_type = Column(String(50), nullable=False, index=True)
    operation = Column(String(100), nullable=False)  # create_lead, update_contact, etc.
    sync_direction = Column(String(20), default=SyncDirection.PUSH)
    
    # Record references
    internal_id = Column(Integer, index=True)  # ID del registro interno
    external_id = Column(String(255), index=True)  # ID del registro externo
    
    # Status and results
    status = Column(String(20), default=SyncStatus.PENDING, index=True)
    details = Column(JSON)  # Detalles del sync (campos, cambios, etc.)
    error_message = Column(Text)
    
    # Performance metrics
    duration_ms = Column(Integer)  # Duración del sync en milisegundos
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    next_retry_at = Column(DateTime)
    
    # Relationships
    integration = relationship("Integration", back_populates="sync_logs")

class CRMSync(Base):
    __tablename__ = "crm_syncs"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    
    # CRM details
    crm_provider = Column(String(50), nullable=False)  # hubspot, pipedrive, salesforce
    crm_id = Column(String(255), nullable=False, index=True)  # ID en el CRM
    crm_type = Column(String(50), default="contact")  # contact, lead, deal
    
    # Sync configuration
    sync_direction = Column(String(20), default=SyncDirection.BIDIRECTIONAL)
    is_active = Column(Boolean, default=True)
    auto_sync = Column(Boolean, default=True)
    
    # Field mapping
    field_mappings = Column(JSON)  # Custom field mappings for this record
    ignored_fields = Column(JSON)  # Fields to ignore during sync
    
    # Conflict resolution
    conflict_resolution_strategy = Column(String(50), default="last_modified_wins")
    manual_resolution_required = Column(Boolean, default=False)
    pending_conflicts = Column(JSON)  # Conflictos que requieren resolución manual
    
    # Sync status
    last_synced_at = Column(DateTime)
    last_sync_direction = Column(String(20))
    sync_errors = Column(JSON)
    consecutive_failures = Column(Integer, default=0)
    
    # Data comparison
    internal_checksum = Column(String(64))  # Hash de datos internos
    external_checksum = Column(String(64))  # Hash de datos externos
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead", back_populates="crm_syncs")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # Event details
    event_id = Column(String(255), unique=True, index=True)  # ID único del evento
    event_type = Column(String(100), nullable=False)  # lead.created, contact.updated, etc.
    source_system = Column(String(50), nullable=False)
    
    # Payload
    raw_payload = Column(JSON, nullable=False)
    headers = Column(JSON)  # HTTP headers del webhook
    signature = Column(String(500))  # Signature para validación
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(20), default="pending")
    processing_result = Column(JSON)
    processing_errors = Column(JSON)
    retry_count = Column(Integer, default=0)
    
    # Deduplication
    duplicate_of = Column(Integer, ForeignKey("webhook_events.id"))
    is_duplicate = Column(Boolean, default=False)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)
    next_retry_at = Column(DateTime)
    
    # Relationships
    integration = relationship("Integration")
    duplicate_events = relationship("WebhookEvent", remote_side=[id])

class APIQuota(Base):
    __tablename__ = "api_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # Quota details
    quota_type = Column(String(50), nullable=False)  # daily, hourly, monthly
    quota_limit = Column(Integer, nullable=False)
    quota_used = Column(Integer, default=0)
    quota_remaining = Column(Integer)
    
    # Reset information
    quota_reset_at = Column(DateTime, nullable=False)
    quota_period_start = Column(DateTime, nullable=False)
    
    # Monitoring
    is_quota_exceeded = Column(Boolean, default=False)
    last_request_at = Column(DateTime)
    requests_this_period = Column(Integer, default=0)
    
    # Rate limiting
    rate_limit_window_seconds = Column(Integer, default=3600)  # 1 hour default
    requests_in_window = Column(Integer, default=0)
    window_start = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    integration = relationship("Integration")

class ExternalCampaign(Base):
    __tablename__ = "external_campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # Campaign identification
    external_campaign_id = Column(String(255), nullable=False, index=True)
    campaign_name = Column(String(500))
    campaign_type = Column(String(100))  # lead_generation, traffic, conversions
    
    # Campaign details
    status = Column(String(50))  # active, paused, completed, archived
    objective = Column(String(100))
    platform = Column(String(50))  # facebook, google, linkedin
    
    # Budget and spend
    daily_budget = Column(Float)
    lifetime_budget = Column(Float)
    total_spend = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    
    # Performance metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    leads_generated = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    
    # Calculated metrics
    ctr = Column(Float, default=0.0)  # Click-through rate
    cpm = Column(Float, default=0.0)  # Cost per mille
    cpc = Column(Float, default=0.0)  # Cost per click
    cost_per_lead = Column(Float, default=0.0)
    cost_per_conversion = Column(Float, default=0.0)
    
    # Attribution window
    attribution_window_days = Column(Integer, default=7)
    
    # Campaign dates
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Last sync
    last_synced_at = Column(DateTime)
    sync_frequency_hours = Column(Integer, default=6)  # Sync every 6 hours
    
    # Raw data
    raw_campaign_data = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    integration = relationship("Integration")

class IntegrationHealth(Base):
    __tablename__ = "integration_health"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # Health check details
    check_type = Column(String(50), nullable=False)  # connection, webhook, sync, quota
    status = Column(String(20), nullable=False)  # healthy, warning, critical, unknown
    
    # Metrics
    response_time_ms = Column(Integer)
    success_rate = Column(Float)  # 0-1
    error_rate = Column(Float)    # 0-1
    
    # Details
    message = Column(Text)
    details = Column(JSON)
    error_details = Column(JSON)
    
    # Thresholds
    warning_threshold = Column(Float)
    critical_threshold = Column(Float)
    
    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    
    # Alerting
    alert_sent = Column(Boolean, default=False)
    alert_sent_at = Column(DateTime)
    escalation_level = Column(Integer, default=0)  # 0=no escalation, 1=team, 2=manager
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    integration = relationship("Integration")

class DataMapping(Base):
    __tablename__ = "data_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False)
    
    # Mapping configuration
    source_system = Column(String(50), nullable=False)
    target_system = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False)  # lead, contact, deal, etc.
    
    # Field mappings
    field_mappings = Column(JSON, nullable=False)  # {source_field: target_field}
    transformation_rules = Column(JSON)  # Custom transformation logic
    validation_rules = Column(JSON)  # Validation rules for mapped data
    
    # Default values
    default_values = Column(JSON)  # Default values for missing fields
    required_fields = Column(JSON)  # Required fields list
    
    # Mapping metadata
    is_active = Column(Boolean, default=True)
    is_bidirectional = Column(Boolean, default=False)
    priority = Column(Integer, default=1)  # For conflict resolution
    
    # Usage statistics
    times_used = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    last_used_at = Column(DateTime)
    
    # Version control
    version = Column(String(20), default="1.0")
    previous_version_id = Column(Integer, ForeignKey("data_mappings.id"))
    
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    integration = relationship("Integration")
    previous_version = relationship("DataMapping", remote_side=[id])

# Funciones de utilidad para integraciones

def create_integration_config(provider: IntegrationProvider, **kwargs) -> dict:
    """Crea configuración base para una integración"""
    
    base_config = {
        "provider": provider,
        "created_at": datetime.utcnow().isoformat(),
        "version": "1.0"
    }
    
    # Configuraciones específicas por proveedor
    if provider == IntegrationProvider.META_ADS:
        base_config.update({
            "access_token": kwargs.get("access_token"),
            "app_secret": kwargs.get("app_secret"),
            "ad_account_id": kwargs.get("ad_account_id"),
            "webhook_verify_token": kwargs.get("webhook_verify_token"),
            "webhook_fields": ["leadgen"],
            "rate_limit_per_hour": 200
        })
    
    elif provider == IntegrationProvider.HUBSPOT:
        base_config.update({
            "access_token": kwargs.get("access_token"),
            "portal_id": kwargs.get("portal_id"),
            "client_id": kwargs.get("client_id"),
            "client_secret": kwargs.get("client_secret"),
            "webhook_endpoint": kwargs.get("webhook_endpoint"),
            "rate_limit_per_hour": 1000
        })
    
    elif provider == IntegrationProvider.PIPEDRIVE:
        base_config.update({
            "api_token": kwargs.get("api_token"),
            "company_domain": kwargs.get("company_domain"),
            "webhook_endpoint": kwargs.get("webhook_endpoint"),
            "rate_limit_per_hour": 5000
        })
    
    elif provider == IntegrationProvider.WHATSAPP:
        base_config.update({
            "access_token": kwargs.get("access_token"),
            "phone_number_id": kwargs.get("phone_number_id"),
            "webhook_verify_token": kwargs.get("webhook_verify_token"),
            "webhook_secret": kwargs.get("webhook_secret"),
            "rate_limit_per_hour": 1000
        })
    
    # Agregar configuraciones personalizadas
    base_config.update(kwargs.get("custom_config", {}))
    
    return base_config

def calculate_data_quality_score(raw_data: dict) -> float:
    """Calcula un score de calidad de datos de 0 a 1"""
    
    if not raw_data:
        return 0.0
    
    # Campos importantes para scoring
    important_fields = ["email", "name", "phone", "company"]
    optional_fields = ["job_title", "city", "country", "website"]
    
    score = 0.0
    max_score = 0.0
    
    # Scoring por campos importantes (peso 0.7)
    for field in important_fields:
        max_score += 0.175  # 0.7 / 4 fields
        value = raw_data.get(field)
        
        if value and str(value).strip():
            if field == "email" and "@" in str(value):
                score += 0.175
            elif field == "phone" and len(str(value).replace(" ", "").replace("-", "")) >= 10:
                score += 0.175
            elif field in ["name", "company"] and len(str(value).strip()) >= 2:
                score += 0.175
            elif value:
                score += 0.1  # Partial credit
    
    # Scoring por campos opcionales (peso 0.3)
    for field in optional_fields:
        max_score += 0.075  # 0.3 / 4 fields
        value = raw_data.get(field)
        
        if value and str(value).strip() and len(str(value).strip()) >= 2:
            score += 0.075
    
    return min(score, 1.0)

def generate_external_lead_checksum(lead_data: dict) -> str:
    """Genera checksum para detectar cambios en datos de lead externo"""
    
    import hashlib
    import json
    
    # Campos relevantes para el checksum (excluir timestamps y IDs)
    relevant_fields = {
        k: v for k, v in lead_data.items() 
        if k not in ["id", "created_at", "updated_at", "last_sync", "timestamps"]
    }
    
    # Normalizar y ordenar para consistencia
    normalized = json.dumps(relevant_fields, sort_keys=True, default=str)
    
    return hashlib.sha256(normalized.encode()).hexdigest()

def detect_lead_changes(old_data: dict, new_data: dict) -> dict:
    """Detecta cambios entre versiones de datos de lead"""
    
    changes = {
        "added": {},
        "modified": {},
        "removed": {},
        "unchanged": {}
    }
    
    # Encontrar campos agregados y modificados
    for key, new_value in new_data.items():
        if key not in old_data:
            changes["added"][key] = new_value
        elif old_data[key] != new_value:
            changes["modified"][key] = {
                "old": old_data[key],
                "new": new_value
            }
        else:
            changes["unchanged"][key] = new_value
    
    # Encontrar campos removidos
    for key, old_value in old_data.items():
        if key not in new_data:
            changes["removed"][key] = old_value
    
    return changes

def validate_webhook_signature(payload: str, signature: str, secret: str, algorithm: str = "sha256") -> bool:
    """Valida la firma de un webhook"""
    
    import hmac
    import hashlib
    
    if algorithm == "sha256":
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Diferentes formatos de signature
        if signature.startswith("sha256="):
            signature = signature[7:]
        
        return hmac.compare_digest(expected, signature)
    
    return False

def create_standard_field_mapping(source_system: str, target_system: str) -> dict:
    """Crea mapeo estándar de campos entre sistemas"""
    
    # Mapeos estándar más comunes
    standard_mappings = {
        ("meta_ads", "internal"): {
            "email": "email",
            "full_name": "name",
            "first_name": "first_name", 
            "last_name": "last_name",
            "phone_number": "phone",
            "company_name": "company",
            "job_title": "job_title",
            "city": "city",
            "country": "country"
        },
        ("internal", "hubspot"): {
            "name": "firstname",  # Se procesará para dividir
            "email": "email",
            "phone": "phone",
            "company": "company",
            "job_title": "jobtitle",
            "source": "hs_lead_source",
            "score": "hs_score"
        },
        ("internal", "pipedrive"): {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "company": "org_name",
            "job_title": "job_title",
            "source": "lead_source",
            "score": "lead_score"
        }
    }
    
    return standard_mappings.get((source_system, target_system), {})