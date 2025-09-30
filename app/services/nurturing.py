from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Header, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi_cache.decorator import cache
import logging
from sqlalchemy.exc import IntegrityError

from ..core.database import get_db
from ..core.config import settings
from ..services.workflow_engine import WorkflowEngine, TriggerType, ActionType, WorkflowStatus
from ..services.email_automation import EmailAutomationService
from ..services.lead_segmentation import LeadSegmentationService
from ..models.workflow import Workflow, WorkflowExecution, EmailTemplate, LeadSegment
from ..models.integration import Lead
from .lead_segmentation import LeadSegmentMembership

router = APIRouter()

# Servicios
workflow_engine = WorkflowEngine()
email_service = EmailAutomationService()
segmentation_service = LeadSegmentationService()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Logger
logger = logging.getLogger("nurturing")

# =============================================================================
# PYDANTIC MODELS PARA REQUEST/RESPONSE
# =============================================================================

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., example="Welcome Series", min_length=1, max_length=100)
    description: Optional[str] = Field(None, example="3-day welcome email sequence", max_length=500)
    trigger_type: TriggerType = Field(..., example=TriggerType.LEAD_CREATED)
    trigger_conditions: Optional[List[Dict]] = Field(None, example=[{"field": "score", "operator": ">", "value": 50}])
    steps: List[Dict[str, Any]] = Field(..., example=[{"type": "email", "delay": "1 hour", "template_id": 1}])
    conditions: Optional[List[Dict]] = None
    category: Optional[str] = Field("custom", example="onboarding")
    priority: Optional[int] = Field(2, ge=1, le=5)
    max_executions_per_lead: Optional[int] = Field(1, ge=1, le=10)

    @validator('trigger_conditions')
    def validate_trigger_conditions(cls, v, values):
        if v and values.get('trigger_type') == TriggerType.MANUAL:
            raise ValueError('Manual triggers cannot have conditions')
        return v

    @validator('steps')
    def validate_steps(cls, v):
        if not v:
            raise ValueError('Workflow must have at least one step')
        if len(v) > 20:
            raise ValueError('Workflow cannot have more than 20 steps')
        return v

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Workflow name cannot be empty')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "name": "Welcome Series",
                "description": "3-day welcome email sequence for new leads",
                "trigger_type": "lead_created",
                "steps": [
                    {"type": "email", "delay": "1 hour", "template_id": 1},
                    {"type": "email", "delay": "1 day", "template_id": 2},
                    {"type": "email", "delay": "3 days", "template_id": 3}
                ],
                "category": "onboarding",
                "priority": 2
            }
        }

class EmailTemplateCreateRequest(BaseModel):
    name: str = Field(..., example="Welcome Email", min_length=1, max_length=100)
    subject: str = Field(..., example="Welcome to Our Platform!", min_length=1, max_length=200)
    html_content: str = Field(..., example="<h1>Welcome {{name}}!</h1>")
    text_content: Optional[str] = Field(None, example="Welcome {{name}}!")
    category: Optional[str] = Field("general", example="onboarding")
    variables: Optional[List[str]] = Field(None, example=["name", "company"])
    dynamic_content: Optional[Dict] = Field(None, example={"button_color": "#007bff"})

    @validator('html_content')
    def validate_html_content(cls, v):
        if len(v) > 100000:  # 100KB max
            raise ValueError('HTML content too large')
        return v

class EmailSendRequest(BaseModel):
    template_id: int = Field(..., ge=1)
    lead_ids: List[int] = Field(..., min_items=1, max_items=1000)
    personalization_data: Optional[Dict[int, Dict]] = None
    subject_override: Optional[str] = Field(None, max_length=200)

    @validator('lead_ids')
    def validate_lead_ids(cls, v):
        if len(v) > settings.EMAIL_MAX_BATCH_SIZE:
            raise ValueError(f'Cannot send to more than {settings.EMAIL_MAX_BATCH_SIZE} leads at once')
        return v

class SegmentCreateRequest(BaseModel):
    name: str = Field(..., example="High Value Leads", min_length=1, max_length=100)
    description: str = Field(..., example="Leads with score above 80", max_length=500)
    rules: List[Dict[str, Any]] = Field(..., example=[{"field": "score", "operator": ">", "value": 80}])
    is_dynamic: bool = Field(True)
    color: Optional[str] = Field("#4169E1", regex="^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")

class CampaignCreateRequest(BaseModel):
    name: str = Field(..., example="Q4 Promotion", min_length=1, max_length=100)
    description: Optional[str] = Field(None, example="End of year promotion campaign")
    segment_ids: List[int] = Field(..., min_items=1)
    workflow_id: int = Field(..., ge=1)
    schedule_type: str = Field("immediate", regex="^(immediate|scheduled|recurring)$")
    scheduled_at: Optional[datetime] = None

class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]

# =============================================================================
# HEALTH CHECK & UTILITIES
# =============================================================================

@router.get("/health/")
async def health_check(db: Session = Depends(get_db)):
    """Health check del servicio de nurturing"""
    try:
        # Verificar conexión a BD
        db.execute("SELECT 1")
        
        # Verificar servicios dependientes
        workflow_health = await workflow_engine.health_check()
        email_health = await email_service.health_check()
        segmentation_health = await segmentation_service.health_check()
        
        return {
            "status": "healthy",
            "database": "connected",
            "workflow_engine": workflow_health,
            "email_service": email_health,
            "segmentation_service": segmentation_health,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

def verify_webhook_signature(payload: Dict, signature: str) -> bool:
    """Verifica la firma del webhook para seguridad"""
    # Implementar según tu proveedor de email (SendGrid, Mailgun, etc.)
    # Esto es un placeholder - implementar según necesidades
    if not settings.WEBHOOK_VERIFICATION_ENABLED:
        return True
        
    # Implementar lógica real de verificación
    return True

# =============================================================================
# WORKFLOW ENDPOINTS
# =============================================================================

@router.post("/workflows/", response_model=Dict[str, Any])
@limiter.limit("50/hour")
async def create_workflow(
    request: Request,
    workflow_data: WorkflowCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea un nuevo workflow de nurturing"""
    
    try:
        # Verificar si ya existe un workflow con el mismo nombre
        existing = db.query(Workflow).filter(Workflow.name == workflow_data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Workflow name already exists")

        workflow = Workflow(
            name=workflow_data.name,
            description=workflow_data.description,
            trigger_type=workflow_data.trigger_type,
            trigger_conditions=workflow_data.trigger_conditions,
            steps=workflow_data.steps,
            conditions=workflow_data.conditions,
            category=workflow_data.category,
            priority=workflow_data.priority,
            max_executions_per_lead=workflow_data.max_executions_per_lead,
            is_active=True,
            created_by="api"
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        logger.info(f"Workflow created: {workflow.id} - {workflow.name}")
        
        return {
            "success": True,
            "workflow_id": workflow.id,
            "message": f"Workflow '{workflow.name}' creado exitosamente"
        }
        
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error creating workflow: {workflow_data.name}")
        raise HTTPException(status_code=400, detail="Workflow name already exists")
    except ValueError as e:
        db.rollback()
        logger.error(f"Validation error creating workflow: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creando workflow: {str(e)}")

@router.get("/workflows/", response_model=PaginatedResponse)
@cache(expire=60)  # Cache por 1 minuto
async def list_workflows(
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de registros por página"),
    db: Session = Depends(get_db)
):
    """Lista todos los workflows con paginación"""
    
    query = db.query(Workflow)
    
    if category:
        query = query.filter(Workflow.category == category)
    
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    
    # Obtener total para paginación
    total = query.count()
    
    workflows = query.order_by(Workflow.priority, Workflow.created_at.desc())\
                    .offset(skip)\
                    .limit(limit)\
                    .all()
    
    workflow_list = []
    for workflow in workflows:
        workflow_list.append({
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "trigger_type": workflow.trigger_type,
            "category": workflow.category,
            "is_active": workflow.is_active,
            "priority": workflow.priority,
            "total_triggered": workflow.total_triggered,
            "total_completed": workflow.total_completed,
            "completion_rate": workflow.total_completed / workflow.total_triggered if workflow.total_triggered > 0 else 0,
            "created_at": workflow.created_at.isoformat(),
            "last_triggered_at": workflow.last_triggered_at.isoformat() if workflow.last_triggered_at else None
        })
    
    return {
        "data": workflow_list,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total
        }
    }

@router.get("/workflows/{workflow_id}/", response_model=Dict[str, Any])
@cache(expire=120)  # Cache por 2 minutos
async def get_workflow_details(workflow_id: int, db: Session = Depends(get_db)):
    """Obtiene detalles completos de un workflow"""
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    # Obtener ejecuciones recientes
    recent_executions = db.query(WorkflowExecution)\
        .filter(WorkflowExecution.workflow_id == workflow_id)\
        .order_by(WorkflowExecution.started_at.desc())\
        .limit(10)\
        .all()
    
    executions_data = []
    for execution in recent_executions:
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        executions_data.append({
            "id": execution.id,
            "lead_name": lead.name if lead else "Lead desconocido",
            "lead_email": lead.email if lead else "",
            "status": execution.status,
            "current_step": execution.current_step,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None
        })
    
    # Métricas del workflow
    metrics = await workflow_engine.get_workflow_metrics(workflow_id, 30, db)
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_conditions": workflow.trigger_conditions,
        "steps": workflow.steps,
        "conditions": workflow.conditions,
        "category": workflow.category,
        "is_active": workflow.is_active,
        "priority": workflow.priority,
        "created_at": workflow.created_at.isoformat(),
        "recent_executions": executions_data,
        "metrics": metrics
    }

@router.post("/workflows/{workflow_id}/trigger/", response_model=Dict[str, Any])
@limiter.limit("100/hour")
async def trigger_workflow_manually(
    request: Request,
    workflow_id: int,
    lead_id: int,
    trigger_data: Optional[Dict] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Dispara un workflow manualmente para un lead específico"""
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    if not workflow.is_active:
        raise HTTPException(status_code=400, detail="Workflow no está activo")
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Verificar si ya existe una ejecución activa para este lead
    existing_execution = db.query(WorkflowExecution)\
        .filter(WorkflowExecution.workflow_id == workflow_id)\
        .filter(WorkflowExecution.lead_id == lead_id)\
        .filter(WorkflowExecution.status == WorkflowStatus.ACTIVE)\
        .first()
    
    if existing_execution:
        raise HTTPException(status_code=400, detail="Ya existe una ejecución activa para este lead")
    
    # Disparar workflow en background
    background_tasks.add_task(
        workflow_engine.trigger_workflow,
        TriggerType.MANUAL,
        lead_id,
        trigger_data or {"manual_trigger": True},
        db
    )
    
    logger.info(f"Workflow {workflow_id} manually triggered for lead {lead_id}")
    
    return {
        "success": True,
        "message": f"Workflow '{workflow.name}' disparado para lead '{lead.name or lead.email}'"
    }

@router.put("/workflows/{workflow_id}/status/", response_model=Dict[str, Any])
async def update_workflow_status(
    workflow_id: int,
    is_active: bool,
    db: Session = Depends(get_db)
):
    """Activa o desactiva un workflow"""
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    workflow.is_active = is_active
    workflow.updated_at = datetime.utcnow()
    db.commit()
    
    status = "activado" if is_active else "desactivado"
    logger.info(f"Workflow {workflow_id} {status}")
    
    return {
        "success": True,
        "message": f"Workflow '{workflow.name}' {status} exitosamente"
    }

@router.get("/workflows/{workflow_id}/metrics/", response_model=Dict[str, Any])
@cache(expire=300)  # Cache por 5 minutos
async def get_workflow_metrics(
    workflow_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene métricas detalladas de un workflow"""
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    metrics = await workflow_engine.get_workflow_metrics(workflow_id, days, db)
    return metrics

# =============================================================================
# EMAIL TEMPLATE ENDPOINTS
# =============================================================================

@router.post("/email-templates/", response_model=Dict[str, Any])
@limiter.limit("30/hour")
async def create_email_template(
    request: Request,
    template_data: EmailTemplateCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea un nuevo template de email"""
    
    try:
        template = await email_service.create_email_template(
            name=template_data.name,
            subject=template_data.subject,
            html_content=template_data.html_content,
            text_content=template_data.text_content,
            category=template_data.category,
            variables=template_data.variables,
            dynamic_content=template_data.dynamic_content,
            created_by="api",
            db=db
        )
        
        logger.info(f"Email template created: {template.id} - {template.name}")
        
        return {
            "success": True,
            "template_id": template.id,
            "message": f"Template '{template.name}' creado exitosamente"
        }
        
    except ValueError as e:
        logger.error(f"Validation error creating email template: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating email template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creando template: {str(e)}")

@router.get("/email-templates/", response_model=PaginatedResponse)
@cache(expire=120)
async def list_email_templates(
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Lista templates de email con paginación"""
    
    query = db.query(EmailTemplate)
    
    if category:
        query = query.filter(EmailTemplate.category == category)
    
    if is_active is not None:
        query = query.filter(EmailTemplate.is_active == is_active)
    
    total = query.count()
    
    templates = query.order_by(EmailTemplate.created_at.desc())\
                    .offset(skip)\
                    .limit(limit)\
                    .all()
    
    template_list = []
    for template in templates:
        template_list.append({
            "id": template.id,
            "name": template.name,
            "subject": template.subject,
            "category": template.category,
            "sent_count": template.sent_count,
            "open_rate": template.open_rate,
            "click_rate": template.click_rate,
            "is_active": template.is_active,
            "created_at": template.created_at.isoformat()
        })
    
    return {
        "data": template_list,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total
        }
    }

@router.get("/email-templates/{template_id}/", response_model=Dict[str, Any])
@cache(expire=180)
async def get_email_template(template_id: int, db: Session = Depends(get_db)):
    """Obtiene un template específico"""
    
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "html_content": template.html_content,
        "text_content": template.text_content,
        "category": template.category,
        "variables": template.variables,
        "dynamic_content": template.dynamic_content,
        "sent_count": template.sent_count,
        "opened_count": template.opened_count,
        "clicked_count": template.clicked_count,
        "open_rate": template.open_rate,
        "click_rate": template.click_rate,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat()
    }

@router.post("/email-templates/{template_id}/send/", response_model=Dict[str, Any])
@limiter.limit("10/hour")  # Límite más estricto para envíos masivos
async def send_template_email(
    request: Request,
    template_id: int,
    email_data: EmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Envía emails usando un template a múltiples leads"""
    
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    
    if not template.is_active:
        raise HTTPException(status_code=400, detail="Template no está activo")
    
    # Verificar que los leads existen
    leads_count = db.query(Lead).filter(Lead.id.in_(email_data.lead_ids)).count()
    if leads_count != len(email_data.lead_ids):
        raise HTTPException(status_code=400, detail="Algunos leads no existen")
    
    # Enviar emails en background
    background_tasks.add_task(
        email_service.send_bulk_emails,
        template_id,
        email_data.lead_ids,
        email_data.personalization_data,
        settings.EMAIL_MAX_BATCH_SIZE,
        db
    )
    
    logger.info(f"Bulk email sending started for template {template_id} to {len(email_data.lead_ids)} leads")
    
    return {
        "success": True,
        "message": f"Se iniciará el envío de {len(email_data.lead_ids)} emails usando template '{template.name}'"
    }

@router.get("/email-analytics/", response_model=Dict[str, Any])
@cache(expire=300)
async def get_email_analytics(
    template_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=365),
    segment: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtiene analytics de emails"""
    
    analytics = await email_service.get_email_analytics(
        template_id=template_id,
        days=days,
        segment=segment,
        db=db
    )
    
    return analytics

# =============================================================================
# SEGMENTATION ENDPOINTS
# =============================================================================

@router.post("/segments/", response_model=Dict[str, Any])
@limiter.limit("20/hour")
async def create_segment(
    request: Request,
    segment_data: SegmentCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea un nuevo segmento"""
    
    try:
        segment = await segmentation_service.create_segment(
            name=segment_data.name,
            description=segment_data.description,
            rules=segment_data.rules,
            is_dynamic=segment_data.is_dynamic,
            color=segment_data.color,
            created_by="api",
            db=db
        )
        
        logger.info(f"Segment created: {segment.id} - {segment.name}")
        
        return {
            "success": True,
            "segment_id": segment.id,
            "message": f"Segmento '{segment.name}' creado exitosamente",
            "current_lead_count": segment.current_lead_count
        }
        
    except ValueError as e:
        logger.error(f"Validation error creating segment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating segment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creando segmento: {str(e)}")

@router.get("/segments/", response_model=PaginatedResponse)
@cache(expire=120)
async def list_segments(
    is_active: Optional[bool] = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Lista todos los segmentos con paginación"""
    
    query = db.query(LeadSegment)
    
    if is_active is not None:
        query = query.filter(LeadSegment.is_active == is_active)
    
    total = query.count()
    
    segments = query.order_by(LeadSegment.priority, LeadSegment.name)\
                   .offset(skip)\
                   .limit(limit)\
                   .all()
    
    segment_list = []
    for segment in segments:
        segment_list.append({
            "id": segment.id,
            "name": segment.name,
            "description": segment.description,
            "color": segment.color,
            "is_dynamic": segment.is_dynamic,
            "current_lead_count": segment.current_lead_count,
            "priority": segment.priority,
            "created_at": segment.created_at.isoformat(),
            "last_calculated_at": segment.last_calculated_at.isoformat() if segment.last_calculated_at else None
        })
    
    return {
        "data": segment_list,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total
        }
    }

@router.post("/segments/setup-predefined/", response_model=Dict[str, Any])
async def setup_predefined_segments(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Configura segmentos predeterminados"""
    
    background_tasks.add_task(segmentation_service.setup_predefined_segments, db)
    
    logger.info("Predefined segments setup started")
    
    return {
        "success": True,
        "message": "Configurando segmentos predeterminados en segundo plano"
    }

@router.post("/segments/{segment_id}/recalculate/", response_model=Dict[str, Any])
async def recalculate_segment(
    segment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Recalcula un segmento específico"""
    
    segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    
    # Recalcular en background para no bloquear la respuesta
    background_tasks.add_task(segmentation_service.recalculate_segment, segment_id, db)
    
    logger.info(f"Segment recalculation started: {segment_id}")
    
    return {
        "success": True,
        "message": f"Recalculando segmento '{segment.name}' en segundo plano"
    }

@router.post("/segments/recalculate-all/", response_model=Dict[str, Any])
async def recalculate_all_segments(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Recalcula todos los segmentos dinámicos"""
    
    background_tasks.add_task(segmentation_service.recalculate_all_segments, db)
    
    logger.info("Recalculation of all segments started")
    
    return {
        "success": True,
        "message": "Recalculando todos los segmentos dinámicos en segundo plano"
    }

@router.get("/segments/{segment_id}/analytics/", response_model=Dict[str, Any])
@cache(expire=300)
async def get_segment_analytics(
    segment_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene analytics de un segmento"""
    
    segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    
    analytics = await segmentation_service.get_segment_analytics(segment_id, days, db)
    return analytics

@router.get("/leads/{lead_id}/segments/", response_model=List[Dict[str, Any]])
@cache(expire=180)
async def get_lead_segments(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene todos los segmentos de un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    segments = await segmentation_service.get_lead_segments(lead_id, db)
    return segments

@router.post("/leads/{lead_id}/segments/{segment_id}/", response_model=Dict[str, Any])
@limiter.limit("100/hour")
async def add_lead_to_segment(
    request: Request,
    lead_id: int,
    segment_id: int,
    db: Session = Depends(get_db)
):
    """Agrega manualmente un lead a un segmento"""
    
    success = await segmentation_service.add_lead_to_segment(
        lead_id, segment_id, "api", "manual_assignment", db
    )
    
    if success:
        logger.info(f"Lead {lead_id} added to segment {segment_id}")
        return {"success": True, "message": "Lead agregado al segmento exitosamente"}
    else:
        return {"success": False, "message": "Lead ya está en el segmento o error"}

@router.delete("/leads/{lead_id}/segments/{segment_id}/", response_model=Dict[str, Any])
@limiter.limit("100/hour")
async def remove_lead_from_segment(
    request: Request,
    lead_id: int,
    segment_id: int,
    db: Session = Depends(get_db)
):
    """Remueve manualmente un lead de un segmento"""
    
    success = await segmentation_service.remove_lead_from_segment(
        lead_id, segment_id, "api_removal", db
    )
    
    if success:
        logger.info(f"Lead {lead_id} removed from segment {segment_id}")
        return {"success": True, "message": "Lead removido del segmento exitosamente"}
    else:
        return {"success": False, "message": "Lead no está en el segmento"}

# =============================================================================
# CAMPAIGN ENDPOINTS
# =============================================================================

@router.post("/campaigns/", response_model=Dict[str, Any])
@limiter.limit("5/hour")  # Límite estricto para campañas
async def create_campaign(
    request: Request,
    campaign_data: CampaignCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Crea y ejecuta una campaña de nurturing"""
    
    # Verificar que el workflow existe y está activo
    workflow = db.query(Workflow).filter(Workflow.id == campaign_data.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    if not workflow.is_active:
        raise HTTPException(status_code=400, detail="Workflow no está activo")
    
    # Obtener leads de los segmentos especificados
    from ..models.workflow import LeadSegmentMembership
    
    leads_query = db.query(Lead)\
        .join(LeadSegmentMembership)\
        .filter(LeadSegmentMembership.segment_id.in_(campaign_data.segment_ids))\
        .filter(LeadSegmentMembership.is_active == True)\
        .distinct()
    
    leads = leads_query.all()
    
    if not leads:
        return {
            "success": False,
            "message": "No se encontraron leads en los segmentos especificados"
        }
    
    # Ejecutar campaña según tipo de scheduling
    if campaign_data.schedule_type == "immediate":
        # Disparar workflows inmediatamente para todos los leads
        for lead in leads:
            background_tasks.add_task(
                workflow_engine.trigger_workflow,
                TriggerType.MANUAL,
                lead.id,
                {
                    "campaign_name": campaign_data.name,
                    "campaign_type": "segment_campaign"
                },
                db
            )
    
    elif campaign_data.schedule_type == "scheduled":
        # TODO: Implementar scheduling con Celery o similar
        pass
    
    logger.info(f"Campaign created: {campaign_data.name} for {len(leads)} leads")
    
    return {
        "success": True,
        "message": f"Campaña '{campaign_data.name}' iniciada para {len(leads)} leads",
        "leads_count": len(leads),
        "workflow_name": workflow.name
    }

# =============================================================================
# NURTURING DASHBOARD ENDPOINTS
# =============================================================================

@router.get("/dashboard/summary/", response_model=Dict[str, Any])
@cache(expire=300)  # Cache por 5 minutos
async def get_nurturing_dashboard(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene resumen completo del dashboard de nurturing"""
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Workflows stats
    total_workflows = db.query(Workflow).filter(Workflow.is_active == True).count()
    active_executions = db.query(WorkflowExecution)\
        .filter(WorkflowExecution.status == WorkflowStatus.ACTIVE)\
        .count()
    
    # Email stats
    from ..models.workflow import EmailSend
    
    emails_sent = db.query(EmailSend)\
        .filter(EmailSend.created_at > since_date)\
        .count()
    
    emails_opened = db.query(EmailSend)\
        .filter(EmailSend.created_at > since_date)\
        .filter(EmailSend.opened_at.isnot(None))\
        .count()
    
    # Segmentation stats
    total_segments = db.query(LeadSegment).filter(LeadSegment.is_active == True).count()
    total_segmented_leads = db.query(LeadSegmentMembership)\
        .filter(LeadSegmentMembership.is_active == True)\
        .distinct(LeadSegmentMembership.lead_id)\
        .count()
    
    # Top performing workflows
    top_workflows = db.query(Workflow)\
        .filter(Workflow.is_active == True)\
        .filter(Workflow.total_triggered > 0)\
        .order_by((Workflow.total_completed / Workflow.total_triggered).desc())\
        .limit(5)\
        .all()
    
    top_workflows_data = []
    for workflow in top_workflows:
        completion_rate = workflow.total_completed / workflow.total_triggered if workflow.total_triggered > 0 else 0
        top_workflows_data.append({
            "id": workflow.id,
            "name": workflow.name,
            "completion_rate": completion_rate,
            "total_triggered": workflow.total_triggered,
            "total_completed": workflow.total_completed
        })
    
    return {
        "period_days": days,
        "workflows": {
            "total_active": total_workflows,
            "active_executions": active_executions,
            "top_performing": top_workflows_data
        },
        "emails": {
            "sent": emails_sent,
            "opened": emails_opened,
            "open_rate": emails_opened / emails_sent if emails_sent > 0 else 0
        },
        "segmentation": {
            "total_segments": total_segments,
            "segmented_leads": total_segmented_leads
        },
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/dashboard/trends/", response_model=Dict[str, Any])
@cache(expire=300)
async def get_nurturing_trends(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene tendencias de nurturing para el dashboard"""
    
    from collections import defaultdict
    from ..models.workflow import EmailSend
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Obtener ejecuciones por día
    executions = db.query(WorkflowExecution)\
        .filter(WorkflowExecution.started_at > since_date)\
        .all()
    
    # Obtener emails por día
    emails = db.query(EmailSend)\
        .filter(EmailSend.created_at > since_date)\
        .all()
    
    daily_executions = defaultdict(int)
    daily_completions = defaultdict(int)
    daily_emails_sent = defaultdict(int)
    daily_emails_opened = defaultdict(int)
    
    for execution in executions:
        date_key = execution.started_at.strftime("%Y-%m-%d")
        daily_executions[date_key] += 1
        
        if execution.status == WorkflowStatus.COMPLETED:
            daily_completions[date_key] += 1
    
    for email in emails:
        date_key = email.created_at.strftime("%Y-%m-%d")
        daily_emails_sent[date_key] += 1
        
        if email.opened_at:
            daily_emails_opened[date_key] += 1
    
    # Generar serie de fechas
    dates = []
    current_date = since_date.date()
    end_date = datetime.utcnow().date()
    
    while current_date <= end_date:
        dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    # Crear series de datos
    executions_trend = [daily_executions.get(date, 0) for date in dates]
    completions_trend = [daily_completions.get(date, 0) for date in dates]
    emails_sent_trend = [daily_emails_sent.get(date, 0) for date in dates]
    emails_opened_trend = [daily_emails_opened.get(date, 0) for date in dates]
    
    # Calcular rates
    open_rates_trend = []
    for i, date in enumerate(dates):
        sent = emails_sent_trend[i]
        opened = emails_opened_trend[i]
        open_rate = opened / sent if sent > 0 else 0
        open_rates_trend.append(open_rate)
    
    return {
        "dates": dates,
        "workflow_executions": executions_trend,
        "workflow_completions": completions_trend,
        "emails_sent": emails_sent_trend,
        "emails_opened": emails_opened_trend,
        "email_open_rates": open_rates_trend
    }

# =============================================================================
# WEBHOOK PARA EVENTOS DE EMAIL
# =============================================================================

@router.post("/webhook/email-events/", response_model=Dict[str, Any])
async def handle_email_events(
    events: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    signature: str = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Maneja eventos de email desde SendGrid u otros proveedores"""
    
    # Verificar firma del webhook para seguridad
    if not verify_webhook_signature(events, signature):
        logger.warning(f"Invalid webhook signature: {signature}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    processed_events = 0
    
    for event in events:
        event_type = event.get("event")
        message_id = event.get("sg_message_id") or event.get("message_id")
        
        if event_type and message_id:
            background_tasks.add_task(
                email_service.handle_email_event,
                event_type,
                message_id,
                event,
                db
            )
            processed_events += 1
    
    logger.info(f"Processed {processed_events} email events via webhook")
    
    return {
        "success": True,
        "processed_events": processed_events,
        "message": f"Procesando {processed_events} eventos de email en segundo plano"
    }

# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@router.post("/batch/workflows/trigger/", response_model=Dict[str, Any])
@limiter.limit("20/hour")
async def trigger_workflows_batch(
    request: Request,
    workflow_leads: Dict[int, List[int]],  # {workflow_id: [lead_ids]}
    trigger_data: Optional[Dict] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Dispara múltiples workflows para múltiples leads en lote"""
    
    total_leads = 0
    triggered_workflows = 0
    
    for workflow_id, lead_ids in workflow_leads.items():
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow or not workflow.is_active:
            continue
            
        for lead_id in lead_ids[:100]:  # Límite por workflow
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                background_tasks.add_task(
                    workflow_engine.trigger_workflow,
                    TriggerType.MANUAL,
                    lead_id,
                    trigger_data or {"batch_trigger": True},
                    db
                )
                total_leads += 1
        
        triggered_workflows += 1
    
    logger.info(f"Batch trigger: {triggered_workflows} workflows for {total_leads} leads")
    
    return {
        "success": True,
        "triggered_workflows": triggered_workflows,
        "total_leads": total_leads,
        "message": f"Procesando {total_leads} leads en {triggered_workflows} workflows"
    }

@router.delete("/workflows/{workflow_id}/", response_model=Dict[str, Any])
async def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """Elimina un workflow (soft delete)"""
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
    # Soft delete - marcar como inactivo en lugar de eliminar
    workflow.is_active = False
    workflow.deleted_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Workflow soft deleted: {workflow_id}")
    
    return {
        "success": True,
        "message": f"Workflow '{workflow.name}' eliminado exitosamente"
    }