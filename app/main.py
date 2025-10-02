from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import logging

from .models.integration import Lead
from .services.integrations import hubspot_service
from .core.database import get_db
from .services.lead_scoring import LeadScoringService
from .services.ai_assistant import AIAssistant, get_conversation_history
from .services.nurturing import NurturingService
from .services.lead_service import (
    calculate_conversion_rate, get_hot_leads_count, get_lead, 
    get_top_lead_sources, get_total_leads, lead_dict, 
    create_lead, save_interaction, get_interactions,
    update_lead_score
)
from .api.dashboard import router as dashboard_router
from .api.reports import router as reports_router
from .api.webhooks import router as webhooks_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sales Automation Bot", 
    version="1.0.0",
    description="Sistema de automatización de ventas con IA integrada",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Incluir routers
app.include_router(webhooks_router)
app.include_router(dashboard_router)
app.include_router(reports_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar servicios
scoring_service = LeadScoringService()
ai_assistant = AIAssistant()
nurturing_service = NurturingService()

@app.on_event("startup")
async def startup_event():
    """Evento al iniciar la aplicación"""
    logger.info("Sales Automation Bot iniciado correctamente")
    
@app.on_event("shutdown")
async def shutdown_event():
    """Evento al cerrar la aplicación"""
    logger.info("Sales Automation Bot finalizado")

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Sales Automation Bot API", 
        "version": "1.0.0",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

@app.post("/webhook/lead")
async def capture_lead(
    lead_data: dict, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Captura leads desde formularios/ads"""
    
    try:
        # Crear lead en BD
        new_lead = create_lead(db, lead_data)
        logger.info(f"Nuevo lead creado: {new_lead.id}")
        
        # Calcular score inicial
        score = scoring_service.calculate_score(new_lead, [])
        
        # Actualizar score del lead
        updated_lead = update_lead_score(db, new_lead.id, score)
        
        # Ejecutar nurturing en background
        background_tasks.add_task(
            nurturing_service.create_nurturing_sequence,
            lead_data, 
            "new_lead"
        )
        
        # Sincronizar con HubSpot en background si está configurado
        if hubspot_service.is_configured():
            background_tasks.add_task(
                hubspot_service.create_or_update_contact,
                updated_lead
            )
        
        return {
            "status": "success", 
            "lead_id": new_lead.id, 
            "score": score,
            "message": "Lead capturado exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error capturando lead: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/chat/message")
async def chat_message(
    message_data: dict, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Maneja conversaciones del chatbot"""
    
    try:
        lead_id = message_data.get("lead_id")
        message = message_data.get("message")
        
        if not lead_id or not message:
            raise HTTPException(status_code=400, detail="lead_id y message son requeridos")
        
        # Obtener contexto del lead
        lead = get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
            
        conversation_history = get_conversation_history(db, lead_id)
        
        # Procesar con IA
        response = await ai_assistant.process_conversation(
            message, 
            lead_dict(lead),
            conversation_history
        )
        
        # Guardar interacción
        save_interaction(db, lead_id, message, response)
        
        # Recalcular score en background
        background_tasks.add_task(
            recalculate_lead_score,
            db,
            lead_id,
            lead,
            scoring_service
        )
        
        return {
            "response": response, 
            "lead_score": lead.score,
            "conversation_id": message_data.get("conversation_id")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Error procesando mensaje")

async def recalculate_lead_score(
    db: Session, 
    lead_id: int, 
    lead: Lead, 
    scoring_service: LeadScoringService
):
    """Recalcula el score del lead en background"""
    try:
        interactions = get_interactions(db, lead_id)
        new_score = scoring_service.calculate_score(lead, interactions)
        
        if abs(new_score - lead.score) > 10:  # Si cambió significativamente
            scoring_service.update_lead_status(db, lead_id, new_score)
            logger.info(f"Score actualizado para lead {lead_id}: {new_score}")
    except Exception as e:
        logger.error(f"Error recalculando score: {str(e)}")

@app.get("/dashboard/analytics")
async def get_analytics(db: Session = Depends(get_db)):
    """Dashboard de analytics"""
    
    try:
        stats = {
            "total_leads": get_total_leads(db),
            "hot_leads": get_hot_leads_count(db),
            "conversion_rate": calculate_conversion_rate(db),
            "top_sources": get_top_lead_sources(db),
            "average_score": scoring_service.get_average_lead_score(db)
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@app.post("/hubspot/sync-lead/{lead_id}")
async def sync_lead_to_hubspot(
    lead_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Sincroniza un lead específico a HubSpot"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Ejecutar sincronización en background
    background_tasks.add_task(
        execute_hubspot_sync,
        lead,
        db
    )
    
    return {"status": "sync_initiated", "message": "Sincronización en proceso"}

async def execute_hubspot_sync(lead: Lead, db: Session):
    """Ejecuta la sincronización con HubSpot"""
    try:
        result = await hubspot_service.create_or_update_contact(lead)
        
        if result['success']:
            # Actualizar hubspot_id si se creó
            if result['hubspot_id']:
                lead.hubspot_id = result['hubspot_id']
                db.commit()
                logger.info(f"Lead {lead.id} sincronizado con HubSpot: {result['hubspot_id']}")
        else:
            logger.error(f"Error sincronizando lead {lead.id}: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error en sync HubSpot para lead {lead.id}: {str(e)}")

@app.post("/hubspot/create-deal/{lead_id}")
async def create_hubspot_deal(
    lead_id: int, 
    deal_data: dict, 
    db: Session = Depends(get_db)
):
    """Crea una oportunidad en HubSpot para un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    if not lead.hubspot_id:
        raise HTTPException(status_code=400, detail="Lead no sincronizado con HubSpot")
    
    # Crear deal en HubSpot
    deal = await hubspot_service.create_deal(lead, deal_data)
    
    if deal:
        return {
            "success": True, 
            "deal_id": deal['id'], 
            "deal_name": deal_data.get('deal_name'),
            "hubspot_deal_id": deal.get('hubspot_deal_id')
        }
    else:
        raise HTTPException(status_code=400, detail="Error creando oportunidad en HubSpot")

@app.get("/hubspot/sync-status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Obtiene el estado de sincronización con HubSpot"""
    
    try:
        total_leads = db.query(Lead).count()
        synced_leads = db.query(Lead).filter(Lead.hubspot_id.isnot(None)).count()
        pending_sync = total_leads - synced_leads
        
        return {
            "total_leads": total_leads,
            "synced_to_hubspot": synced_leads,
            "pending_sync": pending_sync,
            "sync_percentage": round((synced_leads / total_leads * 100), 2) if total_leads > 0 else 0,
            "hubspot_configured": hubspot_service.is_configured()
        }
    except Exception as e:
        logger.error(f"Error obteniendo sync status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado de sincronización")

@app.post("/hubspot/bulk-sync")
async def trigger_bulk_sync(background_tasks: BackgroundTasks):
    """Dispara sincronización masiva a HubSpot"""
    
    try:
        # Enviar tarea a background
        background_tasks.add_task(
            execute_bulk_sync
        )
        
        return {
            "status": "initiated", 
            "message": "Sincronización masiva iniciada en background"
        }
        
    except Exception as e:
        logger.error(f"Error iniciando bulk sync: {str(e)}")
        raise HTTPException(status_code=500, detail="Error iniciando sincronización masiva")

async def execute_bulk_sync():
    """Ejecuta sincronización masiva con HubSpot"""
    try:
        # Implementar lógica de sincronización masiva
        logger.info("Iniciando sincronización masiva con HubSpot")
        # Aquí iría la lógica para sincronizar todos los leads pendientes
        await hubspot_service.bulk_sync_contacts()
        logger.info("Sincronización masiva completada")
    except Exception as e:
        logger.error(f"Error en bulk sync: {str(e)}")

@app.get("/leads/{lead_id}")
async def get_lead_details(lead_id: int, db: Session = Depends(get_db)):
    """Obtiene detalles de un lead específico"""
    
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    interactions = get_interactions(db, lead_id)
    
    return {
        "lead": lead_dict(lead),
        "interactions": interactions,
        "score_breakdown": scoring_service.get_score_breakdown(lead, interactions)
    }

@app.post("/leads/{lead_id}/nurture")
async def trigger_nurturing_sequence(
    lead_id: int,
    sequence_type: str = "default",
    db: Session = Depends(get_db)
):
    """Dispara una secuencia de nurturing para un lead"""
    
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    try:
        await nurturing_service.create_nurturing_sequence(
            lead_dict(lead),
            sequence_type
        )
        
        return {"status": "success", "message": "Secuencia de nurturing iniciada"}
        
    except Exception as e:
        logger.error(f"Error iniciando nurturing: {str(e)}")
        raise HTTPException(status_code=500, detail="Error iniciando secuencia de nurturing")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,  # Solo para desarrollo
        log_level="info"
    )