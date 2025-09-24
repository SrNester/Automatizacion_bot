from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from enum import Enum
import asyncio
import json
import logging

# Importaciones corregidas según tu estructura real
from ...models.integration import (
    Lead, Integration, SyncLog, CRMSync, 
    IntegrationProvider, SyncStatus, SyncDirection, LeadStatus
)
from .hubspot_service import HubSpotService
from .pipedrive_service import PipedriveService
from .salesforce_service import SalesforceService

logger = logging.getLogger(__name__)

class CRMProvider(str, Enum):
    HUBSPOT = "hubspot"
    PIPEDRIVE = "pipedrive"
    SALESFORCE = "salesforce"
    ZOHO = "zoho"
    MS_DYNAMICS = "ms_dynamics"

class CRMSyncManager:
    """Orchestrador para sincronización con múltiples CRMs"""
    
    def __init__(self):
        # Inicializar servicios CRM
        self.crm_services = {
            CRMProvider.HUBSPOT: HubSpotService(),
            CRMProvider.PIPEDRIVE: PipedriveService(),
            CRMProvider.SALESFORCE: SalesforceService()
        }
        
        # Configuraciones de mapeo por CRM
        self.field_mappings = self._load_field_mappings()
        
        # Configuraciones de conflictos
        self.conflict_resolution = {
            "default_strategy": "last_modified_wins",
            "field_priority": {
                "email": "crm_wins",
                "score": "internal_wins",
                "phone": "most_complete_wins"
            }
        }
    
    def _load_field_mappings(self) -> Dict[str, Dict[str, str]]:
        """Carga mapeos de campos para cada CRM"""
        
        return {
            CRMProvider.HUBSPOT: {
                "name": "firstname",
                "email": "email",
                "phone": "phone",
                "company": "company",
                "job_title": "jobtitle",
                "source": "hs_lead_source",
                "score": "hs_score",
                "status": "lifecyclestage"
            },
            CRMProvider.PIPEDRIVE: {
                "name": "name",
                "email": "email",
                "phone": "phone",
                "company": "org_name",
                "job_title": "job_title",
                "source": "lead_source",
                "score": "lead_score",
                "status": "status"
            },
            CRMProvider.SALESFORCE: {
                "name": "Name",
                "email": "Email",
                "phone": "Phone",
                "company": "Company",
                "job_title": "Title",
                "source": "LeadSource",
                "score": "Lead_Score__c",
                "status": "Status"
            }
        }
    
    async def sync_lead_to_crm(self, 
                             lead: Lead, 
                             crm_provider: Union[str, CRMProvider],
                             direction: SyncDirection = SyncDirection.PUSH,
                             db: Session = None) -> Dict[str, Any]:
        """Sincroniza un lead específico con un CRM"""
        
        if isinstance(crm_provider, str):
            crm_provider = CRMProvider(crm_provider)
        
        # Log inicio de sync
        sync_log = SyncLog(
            integration_type=crm_provider.value,
            operation=f"sync_lead_{direction.value}",
            internal_id=lead.id,
            status=SyncStatus.IN_PROGRESS,
            details={"direction": direction.value, "crm_provider": crm_provider.value},
            started_at=datetime.utcnow()
        )
        
        db.add(sync_log)
        db.commit()
        db.refresh(sync_log)
        
        try:
            # Verificar si el CRM está disponible
            crm_service = self.crm_services.get(crm_provider)
            if not crm_service:
                raise ValueError(f"CRM provider {crm_provider} no soportado")
            
            # Ejecutar sincronización según dirección
            if direction == SyncDirection.PUSH:
                result = await self._push_lead_to_crm(lead, crm_provider, crm_service, db)
            elif direction == SyncDirection.PULL:
                result = await self._pull_lead_from_crm(lead, crm_provider, crm_service, db)
            else:  # BIDIRECTIONAL
                result = await self._bidirectional_sync(lead, crm_provider, crm_service, db)
            
            # Actualizar log con resultado
            sync_log.status = SyncStatus.COMPLETED if result["success"] else SyncStatus.FAILED
            sync_log.external_id = result.get("crm_id")
            sync_log.details.update(result)
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_ms = int((datetime.utcnow() - sync_log.started_at).total_seconds() * 1000)
            
            db.commit()
            
            return result
            
        except Exception as e:
            # Log error
            sync_log.status = SyncStatus.FAILED
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_ms = int((datetime.utcnow() - sync_log.started_at).total_seconds() * 1000)
            db.commit()
            
            logger.error(f"Error sincronizando lead {lead.id} con {crm_provider}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "operation": "sync"
            }
    
    def _map_internal_to_crm(self, lead: Lead, crm_provider: CRMProvider) -> Dict[str, Any]:
        """Mapea campos internos a campos del CRM"""
        
        mapping = self.field_mappings.get(crm_provider, {})
        crm_data = {}
        
        for internal_field, crm_field in mapping.items():
            value = getattr(lead, internal_field, None)
            
            if value is not None:
                # Transformaciones especiales por campo
                if internal_field == "name" and crm_provider in [CRMProvider.HUBSPOT, CRMProvider.SALESFORCE]:
                    # Dividir nombre completo en firstname/lastname
                    name_parts = str(value).split(" ", 1)
                    if crm_provider == CRMProvider.HUBSPOT:
                        crm_data["firstname"] = name_parts[0]
                        crm_data["lastname"] = name_parts[1] if len(name_parts) > 1 else ""
                    else:  # Salesforce
                        crm_data["FirstName"] = name_parts[0]
                        crm_data["LastName"] = name_parts[1] if len(name_parts) > 1 else ""
                
                elif internal_field == "status":
                    # Mapear status internos a status CRM
                    crm_data[crm_field] = self._map_status_to_crm(value, crm_provider)
                
                else:
                    crm_data[crm_field] = value
        
        # Agregar campos específicos por CRM
        if crm_provider == CRMProvider.HUBSPOT:
            crm_data["hs_lead_source"] = lead.source or "api"
            if lead.score is not None:
                crm_data["hs_score"] = lead.score
            
        elif crm_provider == CRMProvider.PIPEDRIVE:
            crm_data["lead_source"] = lead.source or "api"
            if lead.score is not None:
                crm_data["lead_score"] = lead.score
            
        elif crm_provider == CRMProvider.SALESFORCE:
            crm_data["LeadSource"] = lead.source or "API"
            if lead.score is not None:
                crm_data["Lead_Score__c"] = lead.score
        
        return crm_data
    
    def _map_crm_to_internal(self, crm_data: Dict, crm_provider: CRMProvider) -> Dict[str, Any]:
        """Mapea campos del CRM a campos internos"""
        
        mapping = self.field_mappings.get(crm_provider, {})
        internal_data = {}
        
        # Mapeo inverso
        inverse_mapping = {v: k for k, v in mapping.items()}
        
        for crm_field, value in crm_data.items():
            if crm_field in inverse_mapping:
                internal_field = inverse_mapping[crm_field]
                
                # Transformaciones especiales
                if internal_field == "name" and crm_provider in [CRMProvider.HUBSPOT, CRMProvider.SALESFORCE]:
                    # Combinar firstname/lastname
                    if crm_provider == CRMProvider.HUBSPOT:
                        firstname = crm_data.get("firstname", "")
                        lastname = crm_data.get("lastname", "")
                    else:  # Salesforce
                        firstname = crm_data.get("FirstName", "")
                        lastname = crm_data.get("LastName", "")
                    
                    full_name = f"{firstname} {lastname}".strip()
                    if full_name:
                        internal_data["name"] = full_name
                
                elif internal_field == "status":
                    internal_data["status"] = self._map_status_from_crm(value, crm_provider)
                
                elif value is not None:
                    internal_data[internal_field] = value
        
        return internal_data
    
    def _map_status_to_crm(self, internal_status: str, crm_provider: CRMProvider) -> str:
        """Mapea status interno a status CRM"""
        
        status_mappings = {
            CRMProvider.HUBSPOT: {
                "cold": "lead",
                "warm": "marketingqualifiedlead", 
                "hot": "salesqualifiedlead",
                "converted": "customer",
                "lost": "other"
            },
            CRMProvider.PIPEDRIVE: {
                "cold": "Open",
                "warm": "Qualified", 
                "hot": "Contacted",
                "converted": "Won",
                "lost": "Lost"
            },
            CRMProvider.SALESFORCE: {
                "cold": "New",
                "warm": "Qualified",
                "hot": "Working - Contacted", 
                "converted": "Closed - Converted",
                "lost": "Closed - Not Converted"
            }
        }
        
        mapping = status_mappings.get(crm_provider, {})
        return mapping.get(internal_status, internal_status)
    
    def _map_status_from_crm(self, crm_status: str, crm_provider: CRMProvider) -> str:
        """Mapea status CRM a status interno"""
        
        status_mappings = {
            CRMProvider.HUBSPOT: {
                "lead": "cold",
                "marketingqualifiedlead": "warm",
                "salesqualifiedlead": "hot", 
                "customer": "converted",
                "other": "lost"
            },
            CRMProvider.PIPEDRIVE: {
                "Open": "cold",
                "Qualified": "warm",
                "Contacted": "hot",
                "Won": "converted", 
                "Lost": "lost"
            },
            CRMProvider.SALESFORCE: {
                "New": "cold",
                "Qualified": "warm",
                "Working - Contacted": "hot",
                "Closed - Converted": "converted",
                "Closed - Not Converted": "lost"
            }
        }
        
        mapping = status_mappings.get(crm_provider, {})
        return mapping.get(crm_status, "cold")
    
    async def _find_existing_crm_record(self, 
                                      lead: Lead,
                                      crm_provider: CRMProvider,
                                      crm_service) -> Optional[Dict[str, Any]]:
        """Busca si el lead ya existe en el CRM"""
        
        # Buscar por email primero
        if lead.email:
            result = await crm_service.find_contact_by_email(lead.email)
            if result and result.get("success") and result.get("contact"):
                return result["contact"]
        
        # Buscar por teléfono si no se encontró por email
        if lead.phone:
            result = await crm_service.find_contact_by_phone(lead.phone)
            if result and result.get("success") and result.get("contact"):
                return result["contact"]
        
        return None
    
    async def _resolve_update_conflicts(self, 
                                      new_data: Dict[str, Any],
                                      existing_data: Dict[str, Any],
                                      crm_provider: CRMProvider) -> Dict[str, Any]:
        """Resuelve conflictos al actualizar datos en CRM"""
        
        resolved_data = {}
        
        for field, new_value in new_data.items():
            existing_value = existing_data.get(field)
            
            # Si no hay conflicto, usar valor nuevo
            if existing_value is None or existing_value == new_value:
                resolved_data[field] = new_value
                continue
            
            # Aplicar estrategia de resolución de conflictos
            strategy = self.conflict_resolution["field_priority"].get(
                field, 
                self.conflict_resolution["default_strategy"]
            )
            
            if strategy == "crm_wins":
                continue
            elif strategy == "internal_wins":
                resolved_data[field] = new_value
            elif strategy == "most_complete_wins":
                if len(str(new_value)) > len(str(existing_value)):
                    resolved_data[field] = new_value
            elif strategy == "last_modified_wins":
                resolved_data[field] = new_value
        
        return resolved_data
    
    async def _resolve_pull_conflicts(self, 
                                    crm_data: Dict[str, Any],
                                    lead: Lead,
                                    crm_provider: CRMProvider) -> Dict[str, Any]:
        """Resuelve conflictos al traer datos desde CRM"""
        
        resolved_data = {}
        
        for field, crm_value in crm_data.items():
            internal_value = getattr(lead, field, None)
            
            # Si no hay conflicto, usar valor CRM
            if internal_value is None or internal_value == crm_value:
                resolved_data[field] = crm_value
                continue
            
            strategy = self.conflict_resolution["field_priority"].get(
                field,
                self.conflict_resolution["default_strategy"]
            )
            
            if strategy == "crm_wins":
                resolved_data[field] = crm_value
            elif strategy == "internal_wins":
                continue
            elif strategy == "most_complete_wins":
                if len(str(crm_value)) > len(str(internal_value)):
                    resolved_data[field] = crm_value
            elif strategy == "last_modified_wins":
                resolved_data[field] = crm_value
        
        return resolved_data
    
    async def _update_lead_crm_reference(self, 
                                       lead: Lead,
                                       crm_provider: CRMProvider,
                                       crm_id: str,
                                       db: Session):
        """Actualiza la referencia CRM en el lead interno"""
        
        # Actualizar campo específico del CRM
        if crm_provider == CRMProvider.HUBSPOT:
            lead.hubspot_id = crm_id
        elif crm_provider == CRMProvider.PIPEDRIVE:
            lead.pipedrive_id = crm_id
        elif crm_provider == CRMProvider.SALESFORCE:
            lead.salesforce_id = crm_id
        
        lead.updated_at = datetime.utcnow()
        db.commit()
    
    async def bulk_sync_leads(self, 
                            lead_ids: List[int],
                            crm_provider: Union[str, CRMProvider],
                            direction: SyncDirection = SyncDirection.PUSH,
                            batch_size: int = 50,
                            db: Session = None) -> Dict[str, Any]:
        """Sincroniza múltiples leads en lotes"""
        
        if isinstance(crm_provider, str):
            crm_provider = CRMProvider(crm_provider)
        
        results = {
            "total_leads": len(lead_ids),
            "successful": 0,
            "failed": 0,
            "processed": 0,
            "errors": []
        }
        
        # Procesar en lotes
        for i in range(0, len(lead_ids), batch_size):
            batch_ids = lead_ids[i:i + batch_size]
            
            # Obtener leads del lote
            leads = db.query(Lead).filter(Lead.id.in_(batch_ids)).all()
            
            # Procesar cada lead del lote
            for lead in leads:
                try:
                    sync_result = await self.sync_lead_to_crm(
                        lead, crm_provider, direction, db
                    )
                    
                    if sync_result["success"]:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append({
                            "lead_id": lead.id,
                            "error": sync_result.get("error", "Unknown error")
                        })
                    
                    results["processed"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "lead_id": lead.id,
                        "error": str(e)
                    })
            
            # Pausa entre lotes para no saturar APIs
            await asyncio.sleep(2)
            
            logger.info(f"Procesado lote {i//batch_size + 1}: {len(leads)} leads")
        
        return results
    
    async def sync_all_leads_to_crm(self, 
                                  crm_provider: Union[str, CRMProvider],
                                  since_date: Optional[datetime] = None,
                                  db: Session = None) -> Dict[str, Any]:
        """Sincroniza todos los leads (o desde una fecha) a un CRM"""
        
        # Query base
        query = db.query(Lead)
        
        if since_date:
            query = query.filter(Lead.updated_at > since_date)
        
        # Solo leads con email (requerido para CRMs)
        query = query.filter(Lead.email.isnot(None))
        
        all_leads = query.all()
        lead_ids = [lead.id for lead in all_leads]
        
        logger.info(f"Iniciando sync masivo de {len(lead_ids)} leads a {crm_provider}")
        
        return await self.bulk_sync_leads(
            lead_ids, crm_provider, SyncDirection.PUSH, db=db
        )
    
    async def health_check_all_crms(self) -> Dict[str, Any]:
        """Verifica el estado de conexión con todos los CRMs"""
        
        health_results = {}
        
        for crm_provider, crm_service in self.crm_services.items():
            try:
                health_result = await crm_service.health_check()
                health_results[crm_provider] = health_result
            except Exception as e:
                health_results[crm_provider] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        all_healthy = all(
            result.get("status") == "healthy" 
            for result in health_results.values()
        )
        
        return {
            "overall_status": "healthy" if all_healthy else "partial",
            "crm_status": health_results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_sync_metrics(self, 
                             days: int = 30,
                             crm_provider: Optional[CRMProvider] = None,
                             db: Session = None) -> Dict[str, Any]:
        """Obtiene métricas de sincronización"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Query base
        query = db.query(SyncLog).filter(SyncLog.started_at > since_date)
        
        if crm_provider:
            query = query.filter(SyncLog.integration_type == crm_provider.value)
        
        sync_logs = query.all()
        
        # Calcular métricas
        total_syncs = len(sync_logs)
        successful_syncs = len([log for log in sync_logs if log.status == SyncStatus.COMPLETED])
        failed_syncs = len([log for log in sync_logs if log.status == SyncStatus.FAILED])
        
        success_rate = successful_syncs / total_syncs if total_syncs > 0 else 0
        
        # Métricas por CRM
        crm_metrics = {}
        for log in sync_logs:
            crm = log.integration_type
            if crm not in crm_metrics:
                crm_metrics[crm] = {"total": 0, "successful": 0, "failed": 0}
            
            crm_metrics[crm]["total"] += 1
            if log.status == SyncStatus.COMPLETED:
                crm_metrics[crm]["successful"] += 1
            elif log.status == SyncStatus.FAILED:
                crm_metrics[crm]["failed"] += 1
        
        # Calcular rates por CRM
        for crm, metrics in crm_metrics.items():
            metrics["success_rate"] = metrics["successful"] / metrics["total"] if metrics["total"] > 0 else 0
        
        # Errores más comunes
        error_logs = [log for log in sync_logs if log.error_message]
        error_counts = {}
        
        for log in error_logs:
            error = log.error_message[:100]
            error_counts[error] = error_counts.get(error, 0) + 1
        
        top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "period_days": days,
            "summary": {
                "total_syncs": total_syncs,
                "successful_syncs": successful_syncs,
                "failed_syncs": failed_syncs,
                "success_rate": success_rate
            },
            "crm_breakdown": crm_metrics,
            "top_errors": [{"error": error, "count": count} for error, count in top_errors],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def retry_failed_syncs(self, 
                               hours_back: int = 24,
                               max_retries: int = 3,
                               db: Session = None) -> Dict[str, Any]:
        """Reintenta sincronizaciones fallidas"""
        
        since_date = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Buscar syncs fallidos
        failed_syncs = db.query(SyncLog)\
            .filter(SyncLog.status == SyncStatus.FAILED)\
            .filter(SyncLog.started_at > since_date)\
            .filter(SyncLog.retry_count < max_retries)\
            .all()
        
        results = {
            "total_retries": len(failed_syncs),
            "successful_retries": 0,
            "failed_retries": 0
        }
        
        for sync_log in failed_syncs:
            try:
                # Obtener lead
                lead = db.query(Lead).filter(Lead.id == sync_log.internal_id).first()
                
                if not lead:
                    continue
                
                # Extraer parámetros del sync original
                crm_provider = CRMProvider(sync_log.integration_type)
                direction = SyncDirection(sync_log.sync_direction or SyncDirection.PUSH)
                
                # Reintentar sync
                retry_result = await self.sync_lead_to_crm(lead, crm_provider, direction, db)
                
                # Actualizar contador de reintentos
                sync_log.retry_count += 1
                
                if retry_result["success"]:
                    results["successful_retries"] += 1
                    logger.info(f"Retry exitoso para lead {lead.id}")
                else:
                    results["failed_retries"] += 1
                    logger.error(f"Retry fallido para lead {lead.id}: {retry_result.get('error')}")
                
                db.commit()
                
            except Exception as e:
                results["failed_retries"] += 1
                sync_log.retry_count += 1
                db.commit()
                logger.error(f"Error en retry: {e}")
            
            # Pausa entre reintentos
            await asyncio.sleep(1)
        
        return results
    
    async def configure_crm_integration(self, 
                                      crm_provider: CRMProvider,
                                      config: Dict[str, Any],
                                      db: Session = None) -> Dict[str, Any]:
        """Configura una integración CRM"""
        
        try:
            # Crear o actualizar configuración
            integration = db.query(Integration)\
                .filter(Integration.provider == crm_provider.value)\
                .first()
            
            if integration:
                # Actualizar existente
                integration.config = config
                integration.is_active = config.get("is_active", True)
                integration.updated_at = datetime.utcnow()
            else:
                # Crear nueva
                integration = Integration(
                    provider=crm_provider.value,
                    name=f"CRM {crm_provider.value.title()}",
                    config=config,
                    is_active=config.get("is_active", True),
                    created_at=datetime.utcnow()
                )
                db.add(integration)
            
            db.commit()
            
            # Test de conexión
            crm_service = self.crm_services.get(crm_provider)
            if crm_service:
                health_check = await crm_service.health_check()
                
                if health_check.get("status") == "healthy":
                    integration.last_health_check = datetime.utcnow()
                    integration.health_status = "healthy"
                    db.commit()
                    
                    return {
                        "success": True,
                        "message": f"Integración {crm_provider} configurada exitosamente",
                        "health_check": health_check
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Configuración guardada pero conexión falló",
                        "health_check": health_check
                    }
            else:
                return {
                    "success": False,
                    "error": f"CRM provider {crm_provider} no soportado"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _push_lead_to_crm(self, 
                              lead: Lead, 
                              crm_provider: CRMProvider,
                              crm_service,
                              db: Session) -> Dict[str, Any]:
        """Empuja un lead interno hacia el CRM"""
        
        try:
            # Mapear campos internos a campos CRM
            crm_data = self._map_internal_to_crm(lead, crm_provider)
            
            # Verificar si el lead ya existe en el CRM
            existing_crm_record = await self._find_existing_crm_record(
                lead, crm_provider, crm_service
            )
            
            if existing_crm_record:
                # Actualizar registro existente
                crm_id = existing_crm_record["id"]
                
                # Resolver conflictos si es necesario
                resolved_data = await self._resolve_update_conflicts(
                    crm_data, existing_crm_record, crm_provider
                )
                
                # Actualizar en CRM
                update_result = await crm_service.update_contact(crm_id, resolved_data)
                
                if update_result.get("success"):
                    # Actualizar referencia en lead interno
                    await self._update_lead_crm_reference(lead, crm_provider, crm_id, db)
                    
                    return {
                        "success": True,
                        "operation": "update",
                        "crm_id": crm_id,
                        "updated_fields": list(resolved_data.keys()),
                        "conflicts_resolved": len(resolved_data) != len(crm_data)
                    }
                else:
                    return {
                        "success": False,
                        "error": update_result.get("error", "Update failed"),
                        "operation": "update"
                    }
            else:
                # Crear nuevo registro
                create_result = await crm_service.create_contact(crm_data)
                
                if create_result.get("success"):
                    crm_id = create_result["contact_id"]
                    
                    # Guardar referencia en lead interno
                    await self._update_lead_crm_reference(lead, crm_provider, crm_id, db)
                    
                    # Crear registro en CRMSync
                    crm_sync = CRMSync(
                        lead_id=lead.id,
                        crm_provider=crm_provider.value,
                        crm_id=crm_id,
                        last_synced_at=datetime.utcnow(),
                        sync_direction=SyncDirection.PUSH,
                        is_active=True
                    )
                    
                    db.add(crm_sync)
                    db.commit()
                    
                    return {
                        "success": True,
                        "operation": "create",
                        "crm_id": crm_id,
                        "created_fields": list(crm_data.keys())
                    }
                else:
                    return {
                        "success": False,
                        "error": create_result.get("error", "Create failed"),
                        "operation": "create"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "operation": "push"
            }
    
    async def _pull_lead_from_crm(self, 
                                lead: Lead,
                                crm_provider: CRMProvider,
                                crm_service,
                                db: Session) -> Dict[str, Any]:
        """Trae datos de un lead desde el CRM"""
        
        try:
            # Buscar el lead en el CRM
            crm_record = await self._find_existing_crm_record(
                lead, crm_provider, crm_service
            )
            
            if not crm_record:
                return {
                    "success": False,
                    "error": "Lead not found in CRM",
                    "operation": "pull"
                }
            
            # Mapear campos CRM a campos internos
            internal_data = self._map_crm_to_internal(crm_record, crm_provider)
            
            # Resolver conflictos entre datos CRM y datos internos
            resolved_data = await self._resolve_pull_conflicts(
                internal_data, lead, crm_provider
            )
            
            # Actualizar lead interno
            updated_fields = []
            for field, value in resolved_data.items():
                if hasattr(lead, field) and value is not None:
                    old_value = getattr(lead, field)
                    if old_value != value:
                        setattr(lead, field, value)
                        updated_fields.append(field)
            
            if updated_fields:
                lead.updated_at = datetime.utcnow()
                db.commit()
            
            return {
                "success": True,
                "operation": "pull",
                "crm_id": crm_record["id"],
                "updated_fields": updated_fields,
                "no_changes": len(updated_fields) == 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "operation": "pull"
            }
    
    async def _bidirectional_sync(self, 
                                lead: Lead,
                                crm_provider: CRMProvider,
                                crm_service,
                                db: Session) -> Dict[str, Any]:
        """Sincronización bidireccional entre interno y CRM"""
        
        try:
            # Primero hacer pull para obtener cambios del CRM
            pull_result = await self._pull_lead_from_crm(lead, crm_provider, crm_service, db)
            
            # Luego hacer push para enviar cambios internos
            push_result = await self._push_lead_to_crm(lead, crm_provider, crm_service, db)
            
            return {
                "success": pull_result.get("success", False) and push_result.get("success", False),
                "operation": "bidirectional",
                "pull_result": pull_result,
                "push_result": push_result,
                "total_changes": len(pull_result.get("updated_fields", [])) + len(push_result.get("updated_fields", []))
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "operation": "bidirectional"
            }

# Instancia global del manager
crm_sync_manager = CRMSyncManager()

# Función helper para uso rápido
async def sync_lead_to_crm(lead: Lead, 
                          crm_provider: Union[str, CRMProvider],
                          direction: SyncDirection = SyncDirection.PUSH,
                          db: Session = None) -> Dict[str, Any]:
    """Función helper para sincronización rápida"""
    return await crm_sync_manager.sync_lead_to_crm(lead, crm_provider, direction, db)