from celery import Celery
from ..services.integrations.hubspot_service import HubSpotService
from ..core.database import get_db
from ..models.lead import Lead
from sqlalchemy.orm import Session

celery_app = Celery("sales_automation")
hubspot_service = HubSpotService()

@celery_app.task(name="sync_lead_to_hubspot")
async def sync_lead_to_hubspot(lead_id: int):
    """Tarea para sincronizar un lead a HubSpot"""
    
    db = next(get_db())
    
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        
        if lead:
            result = await hubspot_service.create_or_update_contact(lead)
            
            if result['success']:
                print(f"Lead {lead_id} sincronizado exitosamente a HubSpot")
            else:
                print(f"Error sincronizando lead {lead_id} a HubSpot")
        
    except Exception as e:
        print(f"Error en tarea de sincronización: {e}")
    
    finally:
        db.close()

@celery_app.task(name="bulk_sync_to_hubspot")
async def bulk_sync_to_hubspot():
    """Tarea para sincronizar todos los leads pendientes"""
    
    db = next(get_db())
    
    try:
        # Obtener leads que necesitan sincronización
        leads = db.query(Lead).filter(Lead.hubspot_id.is_(None)).limit(50).all()
        
        sync_results = {
            "processed": 0,
            "success": 0,
            "errors": 0
        }
        
        for lead in leads:
            try:
                result = await hubspot_service.create_or_update_contact(lead)
                
                if result['success']:
                    # Actualizar hubspot_id en la BD local
                    lead.hubspot_id = result['hubspot_id']
                    db.commit()
                    sync_results["success"] += 1
                else:
                    sync_results["errors"] += 1
                
                sync_results["processed"] += 1
                
            except Exception as e:
                print(f"Error sincronizando lead {lead.id}: {e}")
                sync_results["errors"] += 1
        
        print(f"Sincronización completada: {sync_results}")
        
    except Exception as e:
        print(f"Error en sincronización masiva: {e}")
    
    finally:
        db.close()

@celery_app.task(name="sync_from_hubspot")
async def sync_from_hubspot():
    """Tarea para sincronizar datos desde HubSpot hacia nuestro sistema"""
    
    try:
        result = await hubspot_service.sync_all_contacts(limit=100)
        print(f"Sincronización desde HubSpot completada: {result}")
    
    except Exception as e:
        print(f"Error sincronizando desde HubSpot: {e}")

# Programar tareas periódicas
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'sync-to-hubspot-every-hour': {
        'task': 'bulk_sync_to_hubspot',
        'schedule': crontab(minute=0),  # Cada hora
    },
    'sync-from-hubspot-daily': {
        'task': 'sync_from_hubspot', 
        'schedule': crontab(hour=2, minute=0),  # Diario a las 2 AM
    },
}