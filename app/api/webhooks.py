from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
import hashlib
import hmac
import asyncio
from datetime import datetime

from ..core.database import get_db
from ..core.config import settings
from ..services.ai_assistant import AIAssistant
from ..services.integrations.hubspot_service import HubSpotService
from ..services.integrations.whatsapp_service import WhatsAppService
from ..services.lead_scoring import LeadScoringService
from ..models.lead import Lead
from ..models.interaction import Interaction

router = APIRouter()

# Servicios
ai_assistant = AIAssistant()
hubspot_service = HubSpotService()
whatsapp_service = WhatsAppService()
scoring_service = LeadScoringService()

# ============================================================================
# WEBHOOK WHATSAPP BUSINESS API
# ============================================================================

@router.post("/webhooks/whatsapp")
async def handle_whatsapp_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Maneja webhooks entrantes de WhatsApp Business API"""
    
    # Verificar firma del webhook
    if not await _verify_whatsapp_signature(request):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    body = await request.body()
    webhook_data = json.loads(body)
    
    # Procesar cada entrada del webhook
    for entry in webhook_data.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') == 'messages':
                # Procesar mensajes en background
                background_tasks.add_task(
                    _process_whatsapp_message, 
                    change.get('value', {}),
                    db
                )
    
    return {"status": "success"}

@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """Verificación del webhook de WhatsApp"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(challenge)
    else:
        raise HTTPException(status_code=403, detail="Invalid verification token")

async def _verify_whatsapp_signature(request: Request) -> bool:
    """Verifica la firma del webhook de WhatsApp"""
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return False
    
    body = await request.body()
    expected_signature = hmac.new(
        settings.WHATSAPP_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)

async def _process_whatsapp_message(message_data: Dict, db: Session):
    """Procesa un mensaje entrante de WhatsApp"""
    try:
        messages = message_data.get('messages', [])
        
        for message in messages:
            # Extraer información del mensaje
            phone_number = message.get('from')
            message_id = message.get('id')
            message_text = message.get('text', {}).get('body', '')
            message_type = message.get('type', 'text')
            timestamp = message.get('timestamp')
            
            # Solo procesar mensajes de texto por ahora
            if message_type != 'text' or not message_text:
                continue
            
            # Verificar si es un mensaje duplicado
            existing = db.query(Interaction)\
                .filter(Interaction.platform_message_id == message_id)\
                .first()
            
            if existing:
                continue  # Mensaje ya procesado
            
            # Procesar con IA Assistant
            ai_response = await ai_assistant.process_message(
                message=message_text,
                phone_number=phone_number,
                platform="whatsapp",
                conversation_id=None,  # Se generará automáticamente
                db=db
            )
            
            # Enviar respuesta por WhatsApp
            if ai_response.get('escalate'):
                # Escalación a humano
                escalation_message = (
                    "Te voy a conectar con uno de nuestros especialistas "
                    "que te podrá ayudar mejor. En un momento te contactará. 👤"
                )
                await whatsapp_service.send_message(phone_number, escalation_message)
                
                # Notificar al equipo
                await _notify_escalation(phone_number, message_text, ai_response)
                
            else:
                # Respuesta automática
                await whatsapp_service.send_message(
                    phone_number, 
                    ai_response['response']
                )
            
            print(f"✅ Mensaje procesado de {phone_number}: {ai_response['intent']}")
            
    except Exception as e:
        print(f"❌ Error procesando mensaje WhatsApp: {e}")

# ============================================================================
# WEBHOOK TELEGRAM
# ============================================================================

@router.post("/webhooks/telegram/{bot_token}")
async def handle_telegram_webhook(
    bot_token: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Maneja webhooks entrantes de Telegram"""
    
    # Verificar token del bot
    if bot_token != settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid bot token")
    
    body = await request.body()
    update_data = json.loads(body)
    
    # Procesar update en background
    background_tasks.add_task(_process_telegram_update, update_data, db)
    
    return {"status": "success"}

async def _process_telegram_update(update_data: Dict, db: Session):
    """Procesa un update entrante de Telegram"""
    try:
        message = update_data.get('message', {})
        
        if not message:
            return  # No es un mensaje
        
        # Extraer información
        chat_id = str(message.get('chat', {}).get('id'))
        user_id = str(message.get('from', {}).get('id'))
        text = message.get('text', '')
        message_id = str(message.get('message_id'))
        
        if not text:
            return  # Solo procesar mensajes de texto
        
        # Verificar mensaje duplicado
        existing = db.query(Interaction)\
            .filter(Interaction.platform_message_id == message_id)\
            .first()
        
        if existing:
            return
        
        # Procesar con IA
        ai_response = await ai_assistant.process_message(
            message=text,
            phone_number=user_id,  # Usar user_id como identificador
            platform="telegram",
            conversation_id=f"tg_{chat_id}",
            db=db
        )
        
        # Enviar respuesta
        if ai_response.get('escalate'):
            escalation_msg = "Te conectaré con un especialista humano. Un momento por favor... 🤖➡️👤"
            await _send_telegram_message(chat_id, escalation_msg)
            await _notify_escalation(user_id, text, ai_response, platform="telegram")
        else:
            await _send_telegram_message(chat_id, ai_response['response'])
        
        print(f"✅ Mensaje Telegram procesado: {chat_id} - {ai_response['intent']}")
        
    except Exception as e:
        print(f"❌ Error procesando Telegram: {e}")

async def _send_telegram_message(chat_id: str, text: str):
    """Envía un mensaje por Telegram"""
    import aiohttp
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })

# ============================================================================
# WEBHOOK HUBSPOT (MEJORADO)
# ============================================================================

@router.post("/webhooks/hubspot")
async def handle_hubspot_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Maneja webhooks entrantes de HubSpot"""
    
    if not await _verify_hubspot_signature(request):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    body = await request.body()
    webhook_data = json.loads(body)
    
    # Procesar eventos en background
    for event in webhook_data:
        background_tasks.add_task(_process_hubspot_event, event, db)
    
    return {"status": "success"}

async def _verify_hubspot_signature(request: Request) -> bool:
    """Verifica la firma del webhook de HubSpot"""
    signature = request.headers.get('X-HubSpot-Signature-v3')
    if not signature:
        return False
    
    body = await request.body()
    timestamp = request.headers.get('X-HubSpot-Request-Timestamp')
    
    source_string = request.method + str(request.url) + body.decode() + timestamp
    expected_signature = hmac.new(
        settings.HUBSPOT_CLIENT_SECRET.encode(),
        source_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, f"sha256={expected_signature}")

async def _process_hubspot_event(event: Dict, db: Session):
    """Procesa un evento individual del webhook de HubSpot"""
    try:
        subscription_type = event.get('subscriptionType')
        object_id = event.get('objectId')
        
        if subscription_type == 'contact.propertyChange':
            await _handle_hubspot_contact_update(object_id, event, db)
        elif subscription_type == 'deal.creation':
            await _handle_hubspot_deal_creation(object_id, event, db)
        elif subscription_type == 'deal.propertyChange':
            await _handle_hubspot_deal_update(object_id, event, db)
            
        print(f"✅ Evento HubSpot procesado: {subscription_type}")
        
    except Exception as e:
        print(f"❌ Error procesando evento HubSpot: {e}")

async def _handle_hubspot_contact_update(contact_id: str, event: Dict, db: Session):
    """Maneja actualizaciones de contactos desde HubSpot"""
    lead = db.query(Lead).filter(Lead.hubspot_id == contact_id).first()
    
    if lead:
        # Obtener datos actualizados
        contact_data = await hubspot_service.get_contact(contact_id)
        
        if contact_data:
            # Actualizar lead local
            lead.name = contact_data.get('firstname', '') + ' ' + contact_data.get('lastname', '')
            lead.email = contact_data.get('email')
            lead.company = contact_data.get('company')
            lead.updated_at = datetime.utcnow()
            
            db.commit()

async def _handle_hubspot_deal_creation(deal_id: str, event: Dict, db: Session):
    """Maneja la creación de deals desde HubSpot"""
    deal_data = await hubspot_service.get_deal(deal_id)
    
    if deal_data:
        # Actualizar score del lead asociado si existe
        contact_ids = deal_data.get('associations', {}).get('contacts', [])
        
        for contact_id in contact_ids:
            lead = db.query(Lead).filter(Lead.hubspot_id == contact_id).first()
            if lead:
                lead.score = min(100, lead.score + 20)  # Boost por deal creado
                db.commit()

async def _handle_hubspot_deal_update(deal_id: str, event: Dict, db: Session):
    """Maneja actualizaciones de deals desde HubSpot"""
    property_name = event.get('propertyName')
    
    if property_name == 'dealstage':
        deal_data = await hubspot_service.get_deal(deal_id)
        stage = deal_data.get('dealstage')
        
        # Actualizar score basado en la etapa
        score_updates = {
            'qualifiedtobuy': 30,
            'presentationscheduled': 50,
            'decisionmakerboughtin': 70,
            'contractsent': 85,
            'closedwon': 100
        }
        
        if stage in score_updates:
            contact_ids = deal_data.get('associations', {}).get('contacts', [])
            
            for contact_id in contact_ids:
                lead = db.query(Lead).filter(Lead.hubspot_id == contact_id).first()
                if lead:
                    lead.score = score_updates[stage]
                    db.commit()

# ============================================================================
# WEBHOOK GENÉRICO PARA TESTING
# ============================================================================

@router.post("/webhooks/test")
async def test_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook para testing del chatbot"""
    
    body = await request.json()
    
    test_message = body.get('message', 'Hola, quiero información')
    test_phone = body.get('phone', '+1234567890')
    test_platform = body.get('platform', 'test')
    
    # Simular procesamiento con IA
    ai_response = await ai_assistant.process_message(
        message=test_message,
        phone_number=test_phone,
        platform=test_platform,
        db=next(get_db())
    )
    
    return {
        "status": "success",
        "input": {
            "message": test_message,
            "phone": test_phone,
            "platform": test_platform
        },
        "ai_response": ai_response
    }

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

async def _notify_escalation(
    phone_number: str, 
    message: str, 
    ai_response: Dict,
    platform: str = "whatsapp"
):
    """Notifica escalación al equipo de ventas"""
    
    notification_data = {
        "type": "escalation",
        "phone": phone_number,
        "platform": platform,
        "message": message,
        "intent": ai_response.get('intent'),
        "confidence": ai_response.get('confidence'),
        "lead_score": ai_response.get('lead_score'),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Aquí integrar con Slack, Teams, email, etc.
    print(f"🚨 ESCALACIÓN REQUERIDA: {json.dumps(notification_data, indent=2)}")
    
    # TODO: Implementar notificaciones reales
    # await send_slack_notification(notification_data)
    # await send_email_notification(notification_data)

async def _log_webhook_activity(
    platform: str,
    event_type: str,
    phone_number: str = None,
    status: str = "success",
    details: Dict = None
):
    """Registra actividad de webhooks para monitoring"""
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "platform": platform,
        "event_type": event_type,
        "phone_number": phone_number,
        "status": status,
        "details": details or {}
    }
    
    # Guardar en logs o sistema de monitoring
    print(f"📊 WEBHOOK LOG: {json.dumps(log_entry)}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/webhooks/health")
async def webhook_health_check():
    """Health check para los webhooks"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "ai_assistant": "online",
            "whatsapp": "configured" if hasattr(settings, 'WHATSAPP_ACCESS_TOKEN') else "not_configured",
            "telegram": "configured" if hasattr(settings, 'TELEGRAM_BOT_TOKEN') else "not_configured",
            "hubspot": "configured" if hasattr(settings, 'HUBSPOT_ACCESS_TOKEN') else "not_configured"
        }
    }
    
    return health_status