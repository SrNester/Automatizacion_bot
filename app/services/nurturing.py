from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..core.database import get_db
from ..services.workflow_engine import WorkflowEngine, TriggerType, ActionType, WorkflowStatus
from ..services.email_automation import EmailAutomationService
from ..services.lead_segmentation import LeadSegmentationService
from ..models.workflow import Workflow, WorkflowExecution, EmailTemplate, LeadSegment
from ..models.lead import Lead, LeadSegmentMembership

router = APIRouter()

# Servicios
workflow_engine = WorkflowEngine()
email_service = EmailAutomationService()
segmentation_service = LeadSegmentationService()

# =============================================================================
# PYDANTIC MODELS PARA REQUEST/RESPONSE
# =============================================================================

class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: TriggerType
    trigger_conditions: Optional[List[Dict]] = None
    steps: List[Dict[str, Any]]
    conditions: Optional[List[Dict]] = None
    category: Optional[str] = "custom"
    priority: Optional[int] = 2
    max_executions_per_lead: Optional[int] = 1

class EmailTemplateCreateRequest(BaseModel):
    name: str
    subject: str
    html_content: str
    text_content: Optional[str] = None
    category: Optional[str] = "general"
    variables: Optional[List[str]] = None
    dynamic_content: Optional[Dict] = None

class EmailSendRequest(BaseModel):
    template_id: int
    lead_ids: List[int]
    personalization_data: Optional[Dict[int, Dict]] = None
    subject_override: Optional[str] = None

class SegmentCreateRequest(BaseModel):
    name: str
    description: str
    rules: List[Dict[str, Any]]
    is_dynamic: bool = True
    color: Optional[str] = "#4169E1"

class CampaignCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    segment_ids: List[int]
    workflow_id: int
    schedule_type: str = "immediate"  # immediate, scheduled, recurring
    scheduled_at: Optional[datetime] = None

# =============================================================================
# WORKFLOW ENDPOINTS
# =============================================================================

@router.post("/workflows/", response_model=Dict[str, Any])
async def create_workflow(
    workflow_data: WorkflowCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea un nuevo workflow de nurturing"""
    
    try:
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
        
        return {
            "success": True,
            "workflow_id": workflow.id,
            "message": f"Workflow '{workflow.name}' creado exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando workflow: {str(e)}")

@router.get("/workflows/", response_model=List[Dict[str, Any]])
async def list_workflows(
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Lista todos los workflows"""
    
    query = db.query(Workflow)
    
    if category:
        query = query.filter(Workflow.category == category)
    
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    
    workflows = query.order_by(Workflow.priority, Workflow.created_at.desc()).all()
    
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
    
    return workflow_list

@router.get("/workflows/{workflow_id}/", response_model=Dict[str, Any])
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
async def trigger_workflow_manually(
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
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Disparar workflow en background
    background_tasks.add_task(
        workflow_engine.trigger_workflow,
        TriggerType.MANUAL,
        lead_id,
        trigger_data or {"manual_trigger": True},
        db
    )
    
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
    return {
        "success": True,
        "message": f"Workflow '{workflow.name}' {status} exitosamente"
    }

@router.get("/workflows/{workflow_id}/metrics/", response_model=Dict[str, Any])
async def get_workflow_metrics(
    workflow_id: int,
    days: int = 30,
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
async def create_email_template(
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
        
        return {
            "success": True,
            "template_id": template.id,
            "message": f"Template '{template.name}' creado exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando template: {str(e)}")

@router.get("/email-templates/", response_model=List[Dict[str, Any]])
async def list_email_templates(
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Lista templates de email"""
    
    query = db.query(EmailTemplate)
    
    if category:
        query = query.filter(EmailTemplate.category == category)
    
    if is_active is not None:
        query = query.filter(EmailTemplate.is_active == is_active)
    
    templates = query.order_by(EmailTemplate.created_at.desc()).all()
    
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
    
    return template_list

@router.get("/email-templates/{template_id}/", response_model=Dict[str, Any])
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
async def send_template_email(
    template_id: int,
    email_data: EmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Envía emails usando un template a múltiples leads"""
    
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    
    # Enviar emails en background
    background_tasks.add_task(
        email_service.send_bulk_emails,
        template_id,
        email_data.lead_ids,
        email_data.personalization_data,
        100,  # batch_size
        db
    )
    
    return {
        "success": True,
        "message": f"Se iniciará el envío de {len(email_data.lead_ids)} emails usando template '{template.name}'"
    }

@router.get("/email-analytics/", response_model=Dict[str, Any])
async def get_email_analytics(
    template_id: Optional[int] = None,
    days: int = 30,
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
async def create_segment(
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
        
        return {
            "success": True,
            "segment_id": segment.id,
            "message": f"Segmento '{segment.name}' creado exitosamente",
            "current_lead_count": segment.current_lead_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando segmento: {str(e)}")

@router.get("/segments/", response_model=List[Dict[str, Any]])
async def list_segments(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Lista todos los segmentos"""
    
    query = db.query(LeadSegment)
    
    if is_active is not None:
        query = query.filter(LeadSegment.is_active == is_active)
    
    segments = query.order_by(LeadSegment.priority, LeadSegment.name).all()
    
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
    
    return segment_list

@router.post("/segments/setup-predefined/", response_model=Dict[str, Any])
async def setup_predefined_segments(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Configura segmentos predeterminados"""
    
    background_tasks.add_task(segmentation_service.setup_predefined_segments, db)
    
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
    
    return {
        "success": True,
        "message": "Recalculando todos los segmentos dinámicos en segundo plano"
    }

@router.get("/segments/{segment_id}/analytics/", response_model=Dict[str, Any])
async def get_segment_analytics(
    segment_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Obtiene analytics de un segmento"""
    
    segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    
    analytics = await segmentation_service.get_segment_analytics(segment_id, days, db)
    return analytics

@router.get("/leads/{lead_id}/segments/", response_model=List[Dict[str, Any]])
async def get_lead_segments(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene todos los segmentos de un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    segments = await segmentation_service.get_lead_segments(lead_id, db)
    return segments

@router.post("/leads/{lead_id}/segments/{segment_id}/", response_model=Dict[str, Any])
async def add_lead_to_segment(
    lead_id: int,
    segment_id: int,
    db: Session = Depends(get_db)
):
    """Agrega manualmente un lead a un segmento"""
    
    success = await segmentation_service.add_lead_to_segment(
        lead_id, segment_id, "api", "manual_assignment", db
    )
    
    if success:
        return {"success": True, "message": "Lead agregado al segmento exitosamente"}
    else:
        return {"success": False, "message": "Lead ya está en el segmento o error"}

@router.delete("/leads/{lead_id}/segments/{segment_id}/", response_model=Dict[str, Any])
async def remove_lead_from_segment(
    lead_id: int,
    segment_id: int,
    db: Session = Depends(get_db)
):
    """Remueve manualmente un lead de un segmento"""
    
    success = await segmentation_service.remove_lead_from_segment(
        lead_id, segment_id, "api_removal", db
    )
    
    if success:
        return {"success": True, "message": "Lead removido del segmento exitosamente"}
    else:
        return {"success": False, "message": "Lead no está en el segmento"}

# =============================================================================
# CAMPAIGN ENDPOINTS
# =============================================================================

@router.post("/campaigns/", response_model=Dict[str, Any])
async def create_campaign(
    campaign_data: CampaignCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Crea y ejecuta una campaña de nurturing"""
    
    # Verificar que el workflow existe
    workflow = db.query(Workflow).filter(Workflow.id == campaign_data.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow no encontrado")
    
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
async def get_nurturing_dashboard(
    days: int = 30,
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
async def get_nurturing_trends(
    days: int = 30,
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
    db: Session = Depends(get_db)
):
    """Maneja eventos de email desde SendGrid u otros proveedores"""
    
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
    
    return {
        "success": True,
        "processed_events": processed_events,
        "message": f"Procesando {processed_events} eventos de email en segundo plano"
    }