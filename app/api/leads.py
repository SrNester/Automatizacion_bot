from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..core.database import get_db
from ..models.lead import Lead, LeadStatus, Interaction
from ..services.lead_service import LeadService
from ..services.lead_scoring import LeadScoringService
from ..services.lead_segmentation import LeadSegmentationService

router = APIRouter()

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class LeadCreateRequest(BaseModel):
    email: str
    name: str
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    source: Optional[str] = "manual"
    utm_campaign: Optional[str] = None
    interests: Optional[str] = None
    budget_range: Optional[str] = None
    timeline: Optional[str] = None

class LeadUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[LeadStatus] = None
    interests: Optional[str] = None
    budget_range: Optional[str] = None
    timeline: Optional[str] = None
    is_qualified: Optional[bool] = None

class LeadFilterRequest(BaseModel):
    status: Optional[LeadStatus] = None
    source: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    is_qualified: Optional[bool] = None
    is_active: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

# =============================================================================
# LEAD CRUD ENDPOINTS
# =============================================================================

@router.post("/leads/", response_model=Dict[str, Any])
async def create_lead(
    lead_data: LeadCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Crea un nuevo lead y ejecuta scoring automático"""
    
    try:
        # Verificar si el lead ya existe
        existing_lead = db.query(Lead).filter(Lead.email == lead_data.email).first()
        if existing_lead:
            raise HTTPException(status_code=400, detail="Lead con este email ya existe")
        
        # Crear lead
        lead = Lead(
            email=lead_data.email,
            name=lead_data.name,
            phone=lead_data.phone,
            company=lead_data.company,
            job_title=lead_data.job_title,
            source=lead_data.source,
            utm_campaign=lead_data.utm_campaign,
            interests=lead_data.interests,
            budget_range=lead_data.budget_range,
            timeline=lead_data.timeline
        )
        
        db.add(lead)
        db.commit()
        db.refresh(lead)
        
        # Ejecutar scoring en background
        background_tasks.add_task(
            LeadScoringService.calculate_initial_score,
            lead.id,
            db
        )
        
        return {
            "success": True,
            "lead_id": lead.id,
            "message": "Lead creado exitosamente. Scoring en proceso."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creando lead: {str(e)}")

@router.get("/leads/", response_model=Dict[str, Any])
async def get_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[LeadStatus] = None,
    source: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    is_qualified: Optional[bool] = None,
    sort_by: str = Query("score", regex="^(score|created_at|last_interaction|name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Obtiene lista de leads con filtros y paginación"""
    
    try:
        query = db.query(Lead)
        
        # Aplicar filtros
        if status:
            query = query.filter(Lead.status == status)
        if source:
            query = query.filter(Lead.source == source)
        if min_score is not None:
            query = query.filter(Lead.score >= min_score)
        if max_score is not None:
            query = query.filter(Lead.score <= max_score)
        if is_qualified is not None:
            query = query.filter(Lead.is_qualified == is_qualified)
        
        # Aplicar ordenamiento
        if sort_by == "score":
            order_field = Lead.score
        elif sort_by == "created_at":
            order_field = Lead.created_at
        elif sort_by == "last_interaction":
            order_field = Lead.last_interaction
        elif sort_by == "name":
            order_field = Lead.name
        
        if sort_order == "desc":
            query = query.order_by(order_field.desc())
        else:
            query = query.order_by(order_field.asc())
        
        # Paginación
        total_leads = query.count()
        leads = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "success": True,
            "data": leads,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_leads": total_leads,
                "total_pages": (total_leads + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo leads: {str(e)}")

@router.get("/leads/{lead_id}/", response_model=Lead)
async def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene un lead específico por ID"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return lead

@router.put("/leads/{lead_id}/", response_model=Dict[str, Any])
async def update_lead(
    lead_id: int,
    lead_data: LeadUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Actualiza un lead existente"""
    
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
        
        # Actualizar campos
        update_data = lead_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(lead, field, value)
        
        lead.updated_at = datetime.utcnow()
        db.commit()
        
        # Recalcular scoring si hay cambios relevantes
        if any(field in update_data for field in ['status', 'is_qualified']):
            background_tasks.add_task(
                LeadScoringService.recalculate_score,
                lead_id,
                db
            )
        
        return {
            "success": True,
            "message": "Lead actualizado exitosamente",
            "lead_id": lead_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error actualizando lead: {str(e)}")

@router.delete("/leads/{lead_id}/", response_model=Dict[str, Any])
async def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    """Elimina un lead (soft delete)"""
    
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
        
        lead.is_active = False
        lead.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Lead desactivado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error desactivando lead: {str(e)}")

# =============================================================================
# LEAD SCORING ENDPOINTS
# =============================================================================

@router.post("/leads/{lead_id}/score/", response_model=Dict[str, Any])
async def score_lead(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Ejecuta scoring manual para un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    background_tasks.add_task(
        LeadScoringService.calculate_score,
        lead_id,
        db
    )
    
    return {
        "success": True,
        "message": "Scoring iniciado para el lead",
        "lead_id": lead_id
    }

@router.get("/leads/{lead_id}/score-details/", response_model=Dict[str, Any])
async def get_lead_score_details(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene detalles del scoring de un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    score_breakdown = await LeadScoringService.get_score_breakdown(lead_id, db)
    
    return {
        "success": True,
        "lead_id": lead_id,
        "current_score": lead.score,
        "status": lead.status,
        "score_breakdown": score_breakdown,
        "recommendations": await LeadScoringService.get_recommendations(lead_id, db)
    }

# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@router.post("/leads/batch/score/", response_model=Dict[str, Any])
async def batch_score_leads(
    lead_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Ejecuta scoring para múltiples leads"""
    
    background_tasks.add_task(
        LeadScoringService.batch_score_leads,
        lead_ids,
        db
    )
    
    return {
        "success": True,
        "message": f"Scoring batch iniciado para {len(lead_ids)} leads",
        "lead_count": len(lead_ids)
    }

@router.post("/leads/batch/qualify/", response_model=Dict[str, Any])
async def batch_qualify_leads(
    lead_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Califica múltiples leads como cualificados"""
    
    background_tasks.add_task(
        LeadService.batch_qualify_leads,
        lead_ids,
        db
    )
    
    return {
        "success": True,
        "message": f"Calificación batch iniciada para {len(lead_ids)} leads"
    }

# =============================================================================
# SEGMENTATION ENDPOINTS
# =============================================================================

@router.get("/leads/segments/", response_model=Dict[str, Any])
async def get_lead_segments(db: Session = Depends(get_db)):
    """Obtiene segmentos de leads disponibles"""
    
    segments = await LeadSegmentationService.get_available_segments(db)
    
    return {
        "success": True,
        "segments": segments
    }

@router.get("/leads/segments/{segment}/", response_model=Dict[str, Any])
async def get_leads_by_segment(
    segment: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Obtiene leads pertenecientes a un segmento específico"""
    
    leads, total_count = await LeadSegmentationService.get_leads_by_segment(
        segment, page, page_size, db
    )
    
    return {
        "success": True,
        "segment": segment,
        "data": leads,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_leads": total_count,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    }

# =============================================================================
# INTERACTIONS ENDPOINTS
# =============================================================================

@router.get("/leads/{lead_id}/interactions/", response_model=List[Interaction])
async def get_lead_interactions(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene historial de interacciones de un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    return lead.interactions

@router.post("/leads/{lead_id}/interactions/", response_model=Dict[str, Any])
async def log_interaction(
    lead_id: int,
    interaction_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Registra una nueva interacción para un lead"""
    
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
        
        interaction = Interaction(
            lead_id=lead_id,
            type=interaction_data.get('type', 'unknown'),
            content=interaction_data.get('content', ''),
            response=interaction_data.get('response', ''),
            sentiment_score=interaction_data.get('sentiment_score'),
            platform_message_id=interaction_data.get('platform_message_id'),
            timestamp=interaction_data.get('timestamp', datetime.utcnow())
        )
        
        db.add(interaction)
        
        # Actualizar última interacción del lead
        lead.last_interaction = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "interaction_id": interaction.id,
            "message": "Interacción registrada exitosamente"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error registrando interacción: {str(e)}")

# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@router.get("/leads/analytics/summary/", response_model=Dict[str, Any])
async def get_leads_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene resumen analítico de leads"""
    
    summary = await LeadService.get_leads_summary(days, db)
    
    return {
        "success": True,
        "period_days": days,
        "summary": summary
    }

@router.get("/leads/analytics/sources/", response_model=Dict[str, Any])
async def get_leads_by_source(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtiene distribución de leads por fuente"""
    
    distribution = await LeadService.get_leads_by_source(days, db)
    
    return {
        "success": True,
        "period_days": days,
        "distribution": distribution
    }