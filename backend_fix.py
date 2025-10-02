# backend_fix.py
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import random

# Configurar variables de entorno mínimas requeridas
os.environ['ALLOWED_HOSTS'] = '["localhost", "127.0.0.1", "0.0.0.0"]'
os.environ['CORS_ORIGINS'] = '["http://localhost:3000", "http://localhost:8501"]'
os.environ['ALERT_EMAIL_RECIPIENTS'] = '["admin@example.com"]'
os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
os.environ['HUBSPOT_ACCESS_TOKEN'] = 'demo-token'

app = FastAPI(
    title="Sales Automation API - Demo Mode",
    description="Backend de demostración para el Sales Automation Dashboard",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos de demostración
demo_leads = []
lead_counter = 1000

@app.get("/")
async def root():
    return {
        "message": "Sales Automation API - Demo Mode", 
        "status": "active",
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/docs")
async def get_docs():
    """Redirigir a la documentación interactiva"""
    return {"message": "Visita /docs para la documentación interactiva"}

@app.get("/dashboard/analytics")
async def get_analytics():
    """Endpoint de analytics de demo"""
    return {
        "total_leads": 47,
        "hot_leads": 14,
        "conversion_rate": 16.2,
        "top_sources": [
            {"source": "website", "count": 18},
            {"source": "social_media", "count": 13},
            {"source": "referral", "count": 9},
            {"source": "event", "count": 5},
            {"source": "cold_call", "count": 2}
        ],
        "average_score": 69.5,
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/webhook/lead")
async def capture_lead(lead_data: dict):
    """Endpoint de captura de lead de demo"""
    global lead_counter
    
    lead_id = lead_counter
    lead_counter += 1
    
    # Calcular score demo basado en los datos
    score = random.randint(40, 95)
    
    # Guardar lead en memoria
    demo_lead = {
        "id": lead_id,
        **lead_data,
        "score": score,
        "created_at": datetime.now().isoformat(),
        "status": "new"
    }
    demo_leads.append(demo_lead)
    
    return {
        "success": True,
        "lead_id": lead_id,
        "score": score,
        "message": f"Lead {lead_data.get('name', 'demo')} capturado exitosamente en modo demo",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/chat/message")
async def chat_message(message_data: dict):
    """Endpoint de chat de demo"""
    lead_id = message_data.get("lead_id", 1)
    user_message = message_data.get("message", "")
    
    # Respuestas predefinidas basadas en el mensaje
    responses = {
        "hola": "¡Hola! Soy tu asistente de ventas en modo demostración. ¿En qué puedo ayudarte hoy?",
        "precio": "Nuestros precios varían según el servicio. ¿Podrías contarme más sobre lo que necesitas?",
        "servicio": "Ofrecemos soluciones personalizadas de automatización de ventas. ¿Qué tipo de negocio tienes?",
        "contacto": "Puedes contactarnos en demo@empresa.com o llamarnos al +1234567890",
        "demo": "¡Claro! Podemos agendar una demostración. ¿Qué día y hora te viene bien?"
    }
    
    # Buscar respuesta o usar una genérica
    response_text = "¡Gracias por tu mensaje! En un entorno real, nuestro sistema de IA analizaría tu consulta para darte la mejor respuesta personalizada."
    
    for keyword, response in responses.items():
        if keyword in user_message.lower():
            response_text = response
            break
    
    return {
        "response": response_text,
        "lead_score": random.randint(60, 85),
        "conversation_id": message_data.get("conversation_id", f"demo_{datetime.now().timestamp()}"),
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.get("/leads/{lead_id}")
async def get_lead_details(lead_id: int):
    """Endpoint de detalles de lead de demo"""
    # Buscar lead en datos demo
    lead = next((l for l in demo_leads if l["id"] == lead_id), None)
    
    if not lead:
        # Crear lead demo si no existe
        lead = {
            "id": lead_id,
            "name": f"Lead Demo {lead_id}",
            "email": f"lead{lead_id}@demo.com",
            "phone": f"+123456789{lead_id % 10}",
            "company": f"Empresa Demo {lead_id}",
            "source": "demo",
            "score": random.randint(50, 90),
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
    
    interactions = [
        {
            "message": "Hola, me interesa conocer más sobre sus servicios",
            "response": "¡Claro! ¿Podrías contarme más sobre tu negocio?",
            "timestamp": "2024-01-15T10:00:00"
        },
        {
            "message": "Tengo una empresa de tecnología con 50 empleados",
            "response": "Perfecto, podemos ayudarte con la automatización de ventas.",
            "timestamp": "2024-01-15T10:05:00"
        }
    ]
    
    return {
        "lead": lead,
        "interactions": interactions,
        "score_breakdown": {
            "engagement": random.randint(60, 95),
            "demographics": random.randint(50, 90),
            "behavior": random.randint(55, 85)
        },
        "mode": "demo"
    }

@app.get("/hubspot/sync-status")
async def get_sync_status():
    """Endpoint de estado de HubSpot de demo"""
    return {
        "total_leads": len(demo_leads) + 45,
        "synced_to_hubspot": len(demo_leads) + 32,
        "pending_sync": 13,
        "sync_percentage": round(((len(demo_leads) + 32) / (len(demo_leads) + 45)) * 100, 1),
        "hubspot_configured": True,
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/hubspot/sync-lead/{lead_id}")
async def sync_lead_to_hubspot(lead_id: int):
    """Sincronizar lead con HubSpot - demo"""
    return {
        "success": True,
        "message": f"Lead {lead_id} sincronizado con HubSpot (modo demo)",
        "hubspot_id": f"hubspot_demo_{lead_id}",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/hubspot/bulk-sync")
async def trigger_bulk_sync():
    """Sincronización masiva - demo"""
    return {
        "success": True,
        "message": "Sincronización masiva con HubSpot iniciada (modo demo)",
        "leads_processed": len(demo_leads),
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/leads/{lead_id}/nurture")
async def trigger_nurturing_sequence(lead_id: int, sequence_type: str = "default"):
    """Secuencia de nurturing - demo"""
    sequences = {
        "default": "Secuencia de nurturing estándar iniciada",
        "premium": "Secuencia premium para leads calificados iniciada",
        "reactivation": "Secuencia de reactivación para leads inactivos iniciada"
    }
    
    return {
        "success": True,
        "message": sequences.get(sequence_type, "Secuencia de nurturing iniciada"),
        "sequence_type": sequence_type,
        "lead_id": lead_id,
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/hubspot/create-deal/{lead_id}")
async def create_hubspot_deal(lead_id: int, deal_data: dict):
    """Crear oportunidad en HubSpot - demo"""
    return {
        "success": True,
        "deal_id": f"deal_demo_{int(datetime.now().timestamp())}",
        "deal_name": deal_data.get('deal_name', 'Oportunidad Demo'),
        "amount": deal_data.get('amount', 0),
        "stage": deal_data.get('stage', 'qualifiedtobuy'),
        "message": "Oportunidad creada exitosamente en HubSpot (modo demo)",
        "hubspot_deal_id": f"hubspot_deal_{random.randint(10000, 99999)}",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.get("/leads")
async def get_all_leads():
    """Obtener todos los leads - demo"""
    return {
        "leads": demo_leads[-10:],  # Últimos 10 leads
        "total_count": len(demo_leads),
        "mode": "demo"
    }

if __name__ == "__main__":
    print("🚀 INICIANDO BACKEND DE DEMOSTRACIÓN...")
    print("=" * 50)
    print("📊 API Demo disponible en: http://localhost:8000")
    print("📚 Documentación en: http://localhost:8000/docs")
    print("❤️  Health check en: http://localhost:8000/health")
    print("=" * 50)
    print("🖥️  Frontend disponible en: http://localhost:8501")
    print("⏹️  Presiona Ctrl+C para detener el servidor")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")