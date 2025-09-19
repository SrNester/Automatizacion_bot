from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..services.integrations.hubspot_service import HubSpotService
from ..services.lead_scoring import LeadScoringService
import json
import hashlib
import hmac

router = APIRouter()
hubspot_service = HubSpotService()
scoring_service = LeadScoringService()

@router.post("/webhooks/hubspot")
async def handle_hubspot_webhook(request: Request, db: Session = get_db()):
    """Maneja webhooks entrantes de HubSpot"""
    
    # Verificar firma del webhook
    if not await _verify_hubspot_signature(request):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    body = await request.body()
    webhook_data = json.loads(body)
    
    for event in webhook_data:
        await _process_webhook_event(event, db)
    
    return {"status": "success"}

async def _verify_hubspot_signature(request: Request) -> bool:
    """Verifica la firma del webhook de HubSpot"""
    
    signature = request.headers.get('X-HubSpot-Signature-v3')
    if not signature:
        return False
    
    body = await request.body()
    timestamp = request.headers.get('X-HubSpot-Request-Timestamp')
    
    # Crear la firma esperada
    source_string = request.method + request.url.path + body.decode() + timestamp
    hash_result = hmac.new(
        settings.HUBSPOT_CLIENT_SECRET.encode(),
        source_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    expected_signature = f"sha256={hash_result}"
    
    return hmac.compare_digest(signature, expected_signature)

async def _process_webhook_event(event: Dict, db: Session):
    """Procesa un evento individual del webhook"""
    
    subscription_type = event.get('subscriptionType')
    object_id = event.get('objectId')
    
    if subscription_type == 'contact.propertyChange':
        await _handle_contact_update(object_id, event, db)
    
    elif subscription_type == 'deal.creation':
        await _handle_deal_creation(object_id, event, db)
    
    elif subscription_type == 'deal.propertyChange':
        await _handle_deal_update(object_id, event, db)

async def _handle_contact_update(contact_id: str, event: Dict, db: Session):
    """Maneja actualizaciones de contactos desde HubSpot"""
    
    # Buscar el lead local por hubspot_id
    lead = db.query(Lead).filter(Lead.hubspot_id == contact_id).first()
    
    if lead:
        # Obtener datos actualizados del contacto desde HubSpot
        contact_data = await hubspot_service.get_contact(contact_id)
        
        if contact_data:
            # Actualizar lead local con datos de HubSpot
            await _update_local_lead_from_hubspot(lead, contact_data, db)

async def _handle_deal_creation(deal_id: str, event: Dict, db: Session):
    """Maneja la creación de deals desde HubSpot"""
    
    # Obtener detalles del deal
    deal_data = await hubspot_service.get_deal(deal_id)
    
    if deal_data:
        # Crear registro local del deal si es necesario
        await _create_local_deal_record(deal_data, db)

async def _handle_deal_update(deal_id: str, event: Dict, db: Session):
    """Maneja actualizaciones de deals desde HubSpot"""
    
    # Verificar si el deal cambió de etapa
    property_name = event.get('propertyName')
    
    if property_name == 'dealstage':
        await _handle_deal_stage_change(deal_id, event, db)