from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import asyncio

# Celery
from celery import Celery

# Base de datos
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

# Nuestros servicios
from ..services.integrations.hubspot_service import HubSpotService
from ..core.database import get_db
from ..core.config import settings
from ..models.integration import Lead, IntegrationLog, SyncStatus
from ..models.workflow import LeadActivity

# Logger
logger = logging.getLogger("hubspot_sync")

@dataclass
class SyncResult:
    success: bool
    message: str
    processed_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    error_count: int = 0
    details: Optional[Dict] = None

class HubSpotSyncService:
    """
    Servicio completo de sincronización con HubSpot
    Maneja sincronización bidireccional con tracking y recovery
    """
    
    def __init__(self):
        self.hubspot_service = HubSpotService()
        self.celery_app = Celery("sales_automation")
        self._setup_celery()
        
        # Configuración de sync
        self.sync_config = {
            'batch_size': 50,
            'max_retries': 3,
            'retry_delay_minutes': 5,
            'incremental_sync_hours': 24
        }
        
        logger.info("HubSpotSyncService inicializado")
    
    def _setup_celery(self):
        """Configura Celery para tareas de sincronización"""
        
        self.celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_routes={
                'services.tasks.hubspot_sync.sync_lead_to_hubspot_task': {'queue': 'hubspot'},
                'services.tasks.hubspot_sync.bulk_sync_to_hubspot_task': {'queue': 'hubspot'},
                'services.tasks.hubspot_sync.sync_from_hubspot_task': {'queue': 'hubspot'},
                'services.tasks.hubspot_sync.incremental_sync_task': {'queue': 'hubspot'},
            }
        )
    
    async def full_sync(self, db: Session) -> SyncResult:
        """
        Sincronización completa bidireccional
        """
        
        logger.info("Iniciando sincronización completa con HubSpot")
        
        try:
            # 1. Sincronizar desde HubSpot (traer datos nuevos/actualizados)
            from_result = await self._sync_from_hubspot(db)
            
            # 2. Sincronizar hacia HubSpot (enviar datos locales)
            to_result = await self._sync_to_hubspot(db, sync_all=True)
            
            # 3. Actualizar estadísticas
            await self._update_sync_metrics(db)
            
            return SyncResult(
                success=from_result.success and to_result.success,
                message=f"Sincronización completa: {from_result.message} | {to_result.message}",
                processed_count=from_result.processed_count + to_result.processed_count,
                created_count=from_result.created_count + to_result.created_count,
                updated_count=from_result.updated_count + to_result.updated_count,
                error_count=from_result.error_count + to_result.error_count,
                details={
                    'from_hubspot': from_result.details,
                    'to_hubspot': to_result.details
                }
            )
            
        except Exception as e:
            logger.error(f"Error en sincronización completa: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sincronización completa: {str(e)}",
                error_count=1
            )
    
    async def incremental_sync(self, db: Session) -> SyncResult:
        """
        Sincronización incremental - solo datos recientes
        """
        
        logger.info("Iniciando sincronización incremental con HubSpot")
        
        try:
            # 1. Sincronizar cambios desde HubSpot (últimas 24 horas)
            from_result = await self._sync_recent_from_hubspot(db)
            
            # 2. Sincronizar cambios locales hacia HubSpot
            to_result = await self._sync_recent_to_hubspot(db)
            
            return SyncResult(
                success=from_result.success and to_result.success,
                message=f"Sincronización incremental: {from_result.message} | {to_result.message}",
                processed_count=from_result.processed_count + to_result.processed_count,
                created_count=from_result.created_count + to_result.created_count,
                updated_count=from_result.updated_count + to_result.updated_count,
                error_count=from_result.error_count + to_result.error_count
            )
            
        except Exception as e:
            logger.error(f"Error en sincronización incremental: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sincronización incremental: {str(e)}",
                error_count=1
            )
    
    async def sync_specific_leads(self, lead_ids: List[int], db: Session) -> SyncResult:
        """
        Sincroniza leads específicos hacia HubSpot
        """
        
        logger.info(f"Sincronizando {len(lead_ids)} leads específicos a HubSpot")
        
        try:
            leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
            
            if not leads:
                return SyncResult(
                    success=True,
                    message="No se encontraron leads para sincronizar",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "errors": 0,
                "error_details": []
            }
            
            for lead in leads:
                try:
                    # Determinar si es creación o actualización
                    if lead.hubspot_id:
                        result = await self.hubspot_service.update_contact(lead)
                        action = "updated"
                    else:
                        result = await self.hubspot_service.create_contact(lead)
                        action = "created"
                    
                    if result['success']:
                        # Actualizar hubspot_id si es creación
                        if action == "created" and result.get('hubspot_id'):
                            lead.hubspot_id = result['hubspot_id']
                        
                        # Actualizar timestamp de sync
                        lead.last_sync_at = datetime.utcnow()
                        lead.sync_status = SyncStatus.SYNCED
                        
                        results[action] += 1
                        logger.debug(f"Lead {lead.id} {action} en HubSpot")
                    else:
                        results["errors"] += 1
                        results["error_details"].append({
                            'lead_id': lead.id,
                            'error': result.get('error', 'Unknown error')
                        })
                        lead.sync_status = SyncStatus.FAILED
                        logger.warning(f"Error sincronizando lead {lead.id}: {result.get('error')}")
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    results["error_details"].append({
                        'lead_id': lead.id,
                        'error': str(e)
                    })
                    lead.sync_status = SyncStatus.FAILED
                    logger.error(f"Excepción sincronizando lead {lead.id}: {str(e)}")
            
            db.commit()
            
            # Log de la operación
            await self._log_sync_operation(
                db, "specific_leads", results["processed"], results["errors"], lead_ids
            )
            
            return SyncResult(
                success=results["errors"] == 0,
                message=f"Sincronización específica completada: {results['processed']} procesados, {results['errors']} errores",
                processed_count=results["processed"],
                created_count=results["created"],
                updated_count=results["updated"],
                error_count=results["errors"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en sync específico: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sync específico: {str(e)}",
                error_count=len(lead_ids)
            )
    
    async def _sync_to_hubspot(self, db: Session, sync_all: bool = False) -> SyncResult:
        """
        Sincroniza datos locales hacia HubSpot
        """
        
        try:
            # Construir query basada en el tipo de sync
            query = db.query(Lead)
            
            if not sync_all:
                # Solo leads que necesitan sync (nuevos o modificados)
                query = query.filter(
                    or_(
                        Lead.hubspot_id.is_(None),  # Nuevos leads
                        Lead.updated_at > Lead.last_sync_at,  # Leads modificados
                        Lead.sync_status == SyncStatus.FAILED  # Reintentar fallidos
                    )
                )
            
            leads = query.limit(self.sync_config['batch_size']).all()
            
            if not leads:
                return SyncResult(
                    success=True,
                    message="No hay leads pendientes para sincronizar",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "errors": 0
            }
            
            for lead in leads:
                try:
                    if lead.hubspot_id:
                        # Actualizar contacto existente
                        result = await self.hubspot_service.update_contact(lead)
                        action = "updated"
                    else:
                        # Crear nuevo contacto
                        result = await self.hubspot_service.create_contact(lead)
                        action = "created"
                    
                    if result['success']:
                        # Actualizar datos locales
                        if action == "created" and result.get('hubspot_id'):
                            lead.hubspot_id = result['hubspot_id']
                        
                        lead.last_sync_at = datetime.utcnow()
                        lead.sync_status = SyncStatus.SYNCED
                        
                        results[action] += 1
                    else:
                        results["errors"] += 1
                        lead.sync_status = SyncStatus.FAILED
                        lead.sync_retry_count = (lead.sync_retry_count or 0) + 1
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    lead.sync_status = SyncStatus.FAILED
                    lead.sync_retry_count = (lead.sync_retry_count or 0) + 1
                    logger.error(f"Error procesando lead {lead.id}: {str(e)}")
            
            db.commit()
            
            # Log de la operación
            await self._log_sync_operation(
                db, "to_hubspot", results["processed"], results["errors"]
            )
            
            return SyncResult(
                success=results["errors"] == 0,
                message=f"Sincronización a HubSpot: {results['processed']} procesados, {results['created']} creados, {results['updated']} actualizados, {results['errors']} errores",
                processed_count=results["processed"],
                created_count=results["created"],
                updated_count=results["updated"],
                error_count=results["errors"]
            )
            
        except Exception as e:
            logger.error(f"Error en sync to HubSpot: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sync to HubSpot: {str(e)}",
                error_count=0
            )
    
    async def _sync_from_hubspot(self, db: Session) -> SyncResult:
        """
        Sincroniza datos desde HubSpot hacia el sistema local
        """
        
        try:
            # Obtener contactos de HubSpot
            contacts_result = await self.hubspot_service.get_all_contacts(limit=100)
            
            if not contacts_result['success']:
                return SyncResult(
                    success=False,
                    message=f"Error obteniendo contactos de HubSpot: {contacts_result.get('error')}",
                    error_count=1
                )
            
            contacts = contacts_result.get('contacts', [])
            results = {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "errors": 0
            }
            
            for contact in contacts:
                try:
                    hubspot_id = contact.get('id')
                    email = contact.get('properties', {}).get('email')
                    
                    if not email:
                        continue
                    
                    # Buscar lead existente por hubspot_id o email
                    existing_lead = db.query(Lead).filter(
                        or_(
                            Lead.hubspot_id == hubspot_id,
                            Lead.email == email
                        )
                    ).first()
                    
                    if existing_lead:
                        # Actualizar lead existente
                        await self._update_lead_from_hubspot(existing_lead, contact)
                        results["updated"] += 1
                    else:
                        # Crear nuevo lead
                        await self._create_lead_from_hubspot(contact, db)
                        results["created"] += 1
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Error procesando contacto HubSpot {contact.get('id')}: {str(e)}")
            
            db.commit()
            
            # Log de la operación
            await self._log_sync_operation(
                db, "from_hubspot", results["processed"], results["errors"]
            )
            
            return SyncResult(
                success=results["errors"] == 0,
                message=f"Sincronización desde HubSpot: {results['processed']} procesados, {results['created']} creados, {results['updated']} actualizados, {results['errors']} errores",
                processed_count=results["processed"],
                created_count=results["created"],
                updated_count=results["updated"],
                error_count=results["errors"]
            )
            
        except Exception as e:
            logger.error(f"Error en sync from HubSpot: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sync from HubSpot: {str(e)}",
                error_count=0
            )
    
    async def _sync_recent_from_hubspot(self, db: Session) -> SyncResult:
        """
        Sincroniza solo contactos recientemente modificados desde HubSpot
        """
        
        try:
            # Obtener contactos modificados en las últimas 24 horas
            since_date = datetime.utcnow() - timedelta(hours=self.sync_config['incremental_sync_hours'])
            
            contacts_result = await self.hubspot_service.get_recently_modified_contacts(since_date)
            
            if not contacts_result['success']:
                return SyncResult(
                    success=False,
                    message=f"Error obteniendo contactos recientes: {contacts_result.get('error')}",
                    error_count=1
                )
            
            contacts = contacts_result.get('contacts', [])
            results = {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "errors": 0
            }
            
            for contact in contacts:
                try:
                    hubspot_id = contact.get('id')
                    email = contact.get('properties', {}).get('email')
                    
                    if not email:
                        continue
                    
                    # Buscar lead existente
                    existing_lead = db.query(Lead).filter(
                        or_(
                            Lead.hubspot_id == hubspot_id,
                            Lead.email == email
                        )
                    ).first()
                    
                    if existing_lead:
                        await self._update_lead_from_hubspot(existing_lead, contact)
                        results["updated"] += 1
                    else:
                        await self._create_lead_from_hubspot(contact, db)
                        results["created"] += 1
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Error procesando contacto reciente {contact.get('id')}: {str(e)}")
            
            db.commit()
            
            return SyncResult(
                success=results["errors"] == 0,
                message=f"Sync incremental desde HubSpot: {results['processed']} contactos procesados",
                processed_count=results["processed"],
                created_count=results["created"],
                updated_count=results["updated"],
                error_count=results["errors"]
            )
            
        except Exception as e:
            logger.error(f"Error en sync incremental desde HubSpot: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sync incremental: {str(e)}",
                error_count=0
            )
    
    async def _sync_recent_to_hubspot(self, db: Session) -> SyncResult:
        """
        Sincroniza solo leads modificados recientemente hacia HubSpot
        """
        
        try:
            # Leads modificados en las últimas 24 horas que necesitan sync
            since_date = datetime.utcnow() - timedelta(hours=self.sync_config['incremental_sync_hours'])
            
            leads = db.query(Lead).filter(
                and_(
                    Lead.updated_at > since_date,
                    or_(
                        Lead.hubspot_id.is_(None),
                        Lead.updated_at > Lead.last_sync_at,
                        Lead.sync_status == SyncStatus.FAILED
                    )
                )
            ).limit(self.sync_config['batch_size']).all()
            
            if not leads:
                return SyncResult(
                    success=True,
                    message="No hay leads recientes para sincronizar",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "created": 0,
                "updated": 0,
                "errors": 0
            }
            
            for lead in leads:
                try:
                    if lead.hubspot_id:
                        result = await self.hubspot_service.update_contact(lead)
                        action = "updated"
                    else:
                        result = await self.hubspot_service.create_contact(lead)
                        action = "created"
                    
                    if result['success']:
                        if action == "created" and result.get('hubspot_id'):
                            lead.hubspot_id = result['hubspot_id']
                        
                        lead.last_sync_at = datetime.utcnow()
                        lead.sync_status = SyncStatus.SYNCED
                        
                        results[action] += 1
                    else:
                        results["errors"] += 1
                        lead.sync_status = SyncStatus.FAILED
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    lead.sync_status = SyncStatus.FAILED
                    logger.error(f"Error sync reciente lead {lead.id}: {str(e)}")
            
            db.commit()
            
            return SyncResult(
                success=results["errors"] == 0,
                message=f"Sync incremental a HubSpot: {results['processed']} leads procesados",
                processed_count=results["processed"],
                created_count=results["created"],
                updated_count=results["updated"],
                error_count=results["errors"]
            )
            
        except Exception as e:
            logger.error(f"Error en sync incremental a HubSpot: {str(e)}")
            return SyncResult(
                success=False,
                message=f"Error en sync incremental: {str(e)}",
                error_count=0
            )
    
    async def _update_lead_from_hubspot(self, lead: Lead, hubspot_contact: Dict):
        """Actualiza un lead local con datos de HubSpot"""
        
        properties = hubspot_contact.get('properties', {})
        
        # Mapear propiedades de HubSpot a campos locales
        field_mapping = {
            'firstname': 'name',
            'lastname': 'last_name', 
            'company': 'company',
            'phone': 'phone',
            'website': 'website',
            'country': 'country',
            'city': 'city',
            'jobtitle': 'job_title',
            'lifecyclestage': 'lifecycle_stage',
            'hubspot_owner_id': 'owner_id'
        }
        
        for hubspot_field, local_field in field_mapping.items():
            if hubspot_field in properties and properties[hubspot_field]:
                setattr(lead, local_field, properties[hubspot_field])
        
        # Asegurar hubspot_id
        if not lead.hubspot_id:
            lead.hubspot_id = hubspot_contact.get('id')
        
        lead.last_sync_at = datetime.utcnow()
        lead.sync_status = SyncStatus.SYNCED
    
    async def _create_lead_from_hubspot(self, hubspot_contact: Dict, db: Session) -> Lead:
        """Crea un nuevo lead desde un contacto de HubSpot"""
        
        properties = hubspot_contact.get('properties', {})
        
        lead = Lead(
            hubspot_id=hubspot_contact.get('id'),
            email=properties.get('email'),
            name=properties.get('firstname'),
            last_name=properties.get('lastname'),
            company=properties.get('company'),
            phone=properties.get('phone'),
            website=properties.get('website'),
            country=properties.get('country'),
            city=properties.get('city'),
            job_title=properties.get('jobtitle'),
            lifecycle_stage=properties.get('lifecyclestage'),
            source='hubspot',
            sync_status=SyncStatus.SYNCED,
            last_sync_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        db.add(lead)
        return lead
    
    async def _log_sync_operation(self, db: Session, operation: str, processed: int, errors: int, lead_ids: List[int] = None):
        """Registra una operación de sync en el log"""
        
        log_entry = IntegrationLog(
            integration_name='hubspot',
            operation=operation,
            records_processed=processed,
            records_failed=errors,
            details={
                'lead_ids': lead_ids,
                'timestamp': datetime.utcnow().isoformat()
            },
            created_at=datetime.utcnow()
        )
        
        db.add(log_entry)
        db.commit()
    
    async def _update_sync_metrics(self, db: Session):
        """Actualiza métricas de sincronización"""
        
        # Contar leads por estado de sync
        sync_stats = db.query(
            Lead.sync_status,
            func.count(Lead.id).label('count')
        ).group_by(Lead.sync_status).all()
        
        total_leads = db.query(Lead).count()
        synced_leads = db.query(Lead).filter(Lead.sync_status == SyncStatus.SYNCED).count()
        
        sync_percentage = (synced_leads / total_leads * 100) if total_leads > 0 else 0
        
        logger.info(f"Métricas de sync: {synced_leads}/{total_leads} ({sync_percentage:.1f}%) sincronizados")
    
    async def get_sync_status(self, db: Session) -> Dict[str, Any]:
        """Obtiene el estado actual de la sincronización"""
        
        # Estadísticas básicas
        total_leads = db.query(Lead).count()
        synced_leads = db.query(Lead).filter(Lead.sync_status == SyncStatus.SYNCED).count()
        failed_leads = db.query(Lead).filter(Lead.sync_status == SyncStatus.FAILED).count()
        pending_leads = db.query(Lead).filter(Lead.sync_status.in_([SyncStatus.PENDING, None])).count()
        
        # Últimas operaciones de sync
        recent_operations = db.query(IntegrationLog)\
            .filter(IntegrationLog.integration_name == 'hubspot')\
            .order_by(IntegrationLog.created_at.desc())\
            .limit(10)\
            .all()
        
        return {
            'summary': {
                'total_leads': total_leads,
                'synced_leads': synced_leads,
                'failed_leads': failed_leads,
                'pending_leads': pending_leads,
                'sync_percentage': (synced_leads / total_leads * 100) if total_leads > 0 else 0
            },
            'recent_operations': [
                {
                    'operation': op.operation,
                    'processed': op.records_processed,
                    'failed': op.records_failed,
                    'timestamp': op.created_at.isoformat()
                }
                for op in recent_operations
            ],
            'last_updated': datetime.utcnow().isoformat()
        }

# ===========================================
# TAREAS CELERY
# ===========================================

celery_app = Celery("sales_automation")

# Configuración de Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'services.tasks.hubspot_sync.sync_lead_to_hubspot_task': {'queue': 'hubspot'},
        'services.tasks.hubspot_sync.bulk_sync_to_hubspot_task': {'queue': 'hubspot'},
        'services.tasks.hubspot_sync.sync_from_hubspot_task': {'queue': 'hubspot'},
        'services.tasks.hubspot_sync.incremental_sync_task': {'queue': 'hubspot'},
    }
)

@celery_app.task(name="sync_lead_to_hubspot_task")
def sync_lead_to_hubspot_task(lead_id: int):
    """Tarea Celery para sincronizar un lead específico"""
    
    async def _sync_lead():
        db = next(get_db())
        try:
            sync_service = HubSpotSyncService()
            result = await sync_service.sync_specific_leads([lead_id], db)
            logger.info(f"Sync individual completado: {result.message}")
            return result.__dict__  # Convertir dataclass a dict para Celery
        finally:
            db.close()
    
    return asyncio.run(_sync_lead())

@celery_app.task(name="bulk_sync_to_hubspot_task") 
def bulk_sync_to_hubspot_task(sync_type: str = "incremental"):
    """Tarea Celery para sincronización masiva"""
    
    async def _bulk_sync():
        db = next(get_db())
        try:
            sync_service = HubSpotSyncService()
            
            if sync_type == "full":
                result = await sync_service.full_sync(db)
            else:
                result = await sync_service.incremental_sync(db)
            
            logger.info(f"Sync masivo completado: {result.message}")
            return result.__dict__  # Convertir dataclass a dict para Celery
        finally:
            db.close()
    
    return asyncio.run(_bulk_sync())

@celery_app.task(name="sync_from_hubspot_task")
def sync_from_hubspot_task():
    """Tarea Celery para sincronizar desde HubSpot"""
    
    async def _sync_from():
        db = next(get_db())
        try:
            sync_service = HubSpotSyncService()
            result = await sync_service._sync_from_hubspot(db)
            logger.info(f"Sync desde HubSpot completado: {result.message}")
            return result.__dict__  # Convertir dataclass a dict para Celery
        finally:
            db.close()
    
    return asyncio.run(_sync_from())

@celery_app.task(name="incremental_sync_task")
def incremental_sync_task():
    """Tarea Celery para sync incremental"""
    return bulk_sync_to_hubspot_task("incremental")

# Configuración de tareas periódicas
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'hubspot-incremental-sync': {
        'task': 'services.tasks.hubspot_sync.incremental_sync_task',
        'schedule': crontab(minute='*/30'),  # Cada 30 minutos
    },
    'hubspot-full-sync-daily': {
        'task': 'services.tasks.hubspot_sync.bulk_sync_to_hubspot_task',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'kwargs': {'sync_type': 'full'}
    },
    'hubspot-sync-from-daily': {
        'task': 'services.tasks.hubspot_sync.sync_from_hubspot_task', 
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
}

# Instancia global del servicio
hubspot_sync_service = HubSpotSyncService()