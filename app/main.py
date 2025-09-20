from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .core.database import get_db
from .services.lead_scoring import LeadScoringService
from .services.ai_assistant import AIAssistant
from .services.nurturing import NurturingService
from .services.lead_service import get_lead

app = FastAPI(title="Sales Automation Bot", version="1.0.0")

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

@app.post("/webhook/lead")
async def capture_lead(lead_data: dict, db: Session = Depends(get_db)):
    """Captura leads desde formularios/ads"""
    
    # Crear lead en BD
    new_lead = create_lead(db, lead_data)
    
    # Calcular score inicial
    score = scoring_service.calculate_score(new_lead, [])
    
    # Actualizar status
    updated_lead = scoring_service.update_lead_status(db, new_lead.id, score)
    
    # Iniciar nurturing
    await nurturing_service.create_nurturing_sequence(
        lead_data, 
        "new_lead"
    )
    
    return {"status": "success", "lead_id": new_lead.id, "score": score}

@app.post("/chat/message")
async def chat_message(message_data: dict, db: Session = Depends(get_db)):
    """Maneja conversaciones del chatbot"""
    
    lead_id = message_data.get("lead_id")
    message = message_data.get("message")
    
    # Obtener contexto del lead
    lead = get_lead(db, lead_id)
    conversation_history = get_conversation_history(db, lead_id)
    
    # Procesar con IA
    response = await ai_assistant.process_conversation(
        message, 
        lead_dict(lead),
        conversation_history
    )
    
    # Guardar interacción
    save_interaction(db, lead_id, message, response)
    
    # Recalcular score si es necesario
    interactions = get_interactions(db, lead_id)
    new_score = scoring_service.calculate_score(lead, interactions)
    
    if abs(new_score - lead.score) > 10:  # Si cambió significativamente
        scoring_service.update_lead_status(db, lead_id, new_score)
    
    return {"response": response, "lead_score": new_score}

@app.get("/dashboard/analytics")
async def get_analytics(db: Session = Depends(get_db)):
    """Dashboard de analytics"""
    
    stats = {
        "total_leads": get_total_leads(db),
        "hot_leads": get_hot_leads_count(db),
        "conversion_rate": calculate_conversion_rate(db),
        "top_sources": get_top_lead_sources(db)
    }
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


@app.post("/hubspot/sync-lead/{lead_id}")
async def sync_lead_to_hubspot(lead_id: int, db: Session = Depends(get_db)):
    """Sincroniza un lead específico a HubSpot"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Ejecutar sincronización
    result = await hubspot_service.create_or_update_contact(lead)
    
    if result['success']:
        # Actualizar hubspot_id si se creó
        if result['hubspot_id']:
            lead.hubspot_id = result['hubspot_id']
            db.commit()
    
    return result

@app.post("/hubspot/create-deal/{lead_id}")
async def create_hubspot_deal(lead_id: int, deal_data: dict, db: Session = Depends(get_db)):
    """Crea una oportunidad en HubSpot para un lead"""
    
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Crear deal en HubSpot
    deal = await hubspot_service.create_deal(lead, deal_data)
    
    if deal:
        return {"success": True, "deal_id": deal['id'], "deal_name": deal_data.get('name')}
    else:
        raise HTTPException(status_code=400, detail="Error creando oportunidad")

@app.get("/hubspot/sync-status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Obtiene el estado de sincronización con HubSpot"""
    
    total_leads = db.query(Lead).count()
    synced_leads = db.query(Lead).filter(Lead.hubspot_id.isnot(None)).count()
    pending_sync = total_leads - synced_leads
    
    return {
        "total_leads": total_leads,
        "synced_to_hubspot": synced_leads,
        "pending_sync": pending_sync,
        "sync_percentage": (synced_leads / total_leads * 100) if total_leads > 0 else 0
    }

@app.post("/hubspot/bulk-sync")
async def trigger_bulk_sync():
    """Dispara sincronización masiva a HubSpot"""
    
    # Enviar tarea a Celery
    from .tasks.hubspot_sync import bulk_sync_to_hubspot
    task = bulk_sync_to_hubspot.delay()
    
    return {"task_id": task.id, "status": "initiated"}

# Incluir el router de webhooks
from .api.webhooks import router as webhooks_router
app.include_router(webhooks_router)