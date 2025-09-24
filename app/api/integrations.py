from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import json

from ..core.database import get_db
from ..core.config import settings
from ..services.integrations.meta_ads_service import MetaAdsService
from ..services.integrations.crm_sync_manager import CRMSyncManager, CRMProvider, SyncDirection
from ..services.integrations.pipedrive_service import PipedriveService
from ..services.integrations.hubspot_service import HubSpotService
from ..models.integration import Integration, ExternalLead, SyncLog, CRMSync, WebhookEvent, Lead

router = APIRouter()

# Servicios
meta_ads_service = MetaAdsService()
crm_sync_manager = CRMSyncManager()
pipedrive_service = PipedriveService()
hubspot_service = HubSpotService()

# =============================================================================
# UTILITY FUNCTIONS (MOVIDAS AL INICIO)
# =============================================================================

async def test_integration_connection(provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Testa la conexión con una integración específica"""
    
    try:
        if provider == "meta_ads":
            # Configurar temporalmente el servicio con la config
            service = MetaAdsService()
            service.access_token = config.get("access_token")
            service.app_secret = config.get("app_secret")
            service.ad_account_id = config.get("ad_account_id")
            
            return await service.health_check()
            
        elif provider == "pipedrive":
            service = PipedriveService()
            service.api_token = config.get("api_token")
            
            return await service.health_check()
            
        elif provider == "hubspot":
            service = HubSpotService()
            # Configurar con datos de config
            
            return await service.health_check()
            
        else:
            return {
                "success": False,
                "error": f"Provider {provider} no soportado para health check"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class IntegrationCreateRequest(BaseModel):
    provider: str
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]
    is_active: bool = True

class CRMSyncRequest(BaseModel):
    lead_ids: List[int]
    crm_provider: str
    direction: str = "push"
    batch_size: Optional[int] = 50

class WebhookSetupRequest(BaseModel):
    provider: str
    webhook_url: str
    events: Optional[List[str]] = None

# =============================================================================
# INTEGRATION MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/integrations/", response_model=Dict[str, Any])
async def create_integration(
    integration_data: IntegrationCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea una nueva integración"""
    
    try:
        # Crear integración
        integration = Integration(
            provider=integration_data.provider,
            name=integration_data.name,
            description=integration_data.description,
            config=integration_data.config,
            is_active=integration_data.is_active,
            created_by="api"
        )
        
        db.add(integration)
        db.commit()
        db.refresh(integration)
        
        # Test de conexión inicial
        health_status = await test_integration_connection(integration.provider, integration.config)
        
        integration.health_status = "healthy" if health_status.get("success") else "unhealthy"
        integration.last_health_check = datetime.utcnow()
        
        if not health_status.get("success"):
            integration.last_error = health_status.get("error", "Connection test failed")
        
        db.commit()
        
        return {
            "success": True,
            "integration_id": integration.id,
            "health_status": health_status,
            "message": f"Integración '{integration.name}' creada exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando integración: {str(e)}")

# =============================================================================
# INTEGRATION MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/integrations/", response_model=Dict[str, Any])
async def create_integration(
    integration_data: IntegrationCreateRequest,
    db: Session = Depends(get_db)
):
    """Crea una nueva integración"""
    
    try:
        # Crear integración
        integration = Integration(
            provider=integration_data.provider,
            name=integration_data.name,
            description=integration_data.description,
            config=integration_data.config,
            is_active=integration_data.is_active,
            created_by="api"
        )
        
        db.add(integration)
        db.commit()
        db.refresh(integration)
        
        # Test de conexión inicial
        health_status = await test_integration_connection(integration.provider, integration.config)
        
        integration.health_status = "healthy" if health_status.get("success") else "unhealthy"
        integration.last_health_check = datetime.utcnow()
        
        if not health_status.get("success"):
            integration.last_error = health_status.get("error", "Connection test failed")
        
        db.commit()
        
        return {
            "success": True,
            "integration_id": integration.id,
            "health_status": health_status,
            "message": f"Integración '{integration.name}' creada exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando integración: {str(e)}")

@router.get("/integrations/", response_model=List[Dict[str, Any]])
async def list_integrations(
    provider: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Lista todas las integraciones"""
    
    query = db.query(Integration)
    
    if provider:
        query = query.filter(Integration.provider == provider)
    
    if is_active is not None:
        query = query.filter(Integration.is_active == is_active)
    
    integrations = query.order_by(Integration.created_at.desc()).all()
    
    integration_list = []
    for integration in integrations:
        success_rate = integration.successful_syncs / integration.total_syncs if integration.total_syncs > 0 else 0
        
        integration_list.append({
            "id": integration.id,
            "provider": integration.provider,
            "name": integration.name,
            "description": integration.description,
            "is_active": integration.is_active,
            "health_status": integration.health_status,
            "last_health_check": integration.last_health_check.isoformat() if integration.last_health_check else None,
            "total_syncs": integration.total_syncs,
            "success_rate": success_rate,
            "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
            "is_webhook_configured": integration.is_webhook_configured,
            "created_at": integration.created_at.isoformat()
        })
    
    return integration_list

@router.get("/integrations/{integration_id}/", response_model=Dict[str, Any])
async def get_integration_details(integration_id: int, db: Session = Depends(get_db)):
    """Obtiene detalles completos de una integración"""
    
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    # Obtener logs recientes
    recent_logs = db.query(SyncLog)\
        .filter(SyncLog.integration_id == integration_id)\
        .order_by(SyncLog.started_at.desc())\
        .limit(10)\
        .all()
    
    logs_data = []
    for log in recent_logs:
        logs_data.append({
            "id": log.id,
            "operation": log.operation,
            "status": log.status,
            "duration_ms": log.duration_ms,
            "error_message": log.error_message,
            "started_at": log.started_at.isoformat(),
            "completed_at": log.completed_at.isoformat() if log.completed_at else None
        })
    
    return {
        "id": integration.id,
        "provider": integration.provider,
        "name": integration.name,
        "description": integration.description,
        "config": integration.config,  # Filtrar datos sensibles en producción
        "is_active": integration.is_active,
        "health_status": integration.health_status,
        "last_health_check": integration.last_health_check.isoformat() if integration.last_health_check else None,
        "last_error": integration.last_error,
        "statistics": {
            "total_syncs": integration.total_syncs,
            "successful_syncs": integration.successful_syncs,
            "failed_syncs": integration.failed_syncs,
            "success_rate": integration.successful_syncs / integration.total_syncs if integration.total_syncs > 0 else 0
        },
        "recent_logs": logs_data,
        "created_at": integration.created_at.isoformat(),
        "updated_at": integration.updated_at.isoformat()
    }

@router.post("/integrations/{integration_id}/health-check/", response_model=Dict[str, Any])
async def check_integration_health(
    integration_id: int,
    db: Session = Depends(get_db)
):
    """Ejecuta health check para una integración específica"""
    
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    # Ejecutar health check según el proveedor
    health_result = await test_integration_connection(integration.provider, integration.config)
    
    # Actualizar estado en BD
    integration.health_status = "healthy" if health_result.get("success") else "unhealthy"
    integration.last_health_check = datetime.utcnow()
    
    if not health_result.get("success"):
        integration.last_error = health_result.get("error", "Health check failed")
    else:
        integration.last_error = None
    
    db.commit()
    
    return {
        "integration_id": integration_id,
        "provider": integration.provider,
        "health_result": health_result,
        "updated_at": integration.last_health_check.isoformat()
    }

@router.post("/integrations/health-check-all/", response_model=Dict[str, Any])
async def check_all_integrations_health(db: Session = Depends(get_db)):
    """Ejecuta health check para todas las integraciones activas"""
    
    active_integrations = db.query(Integration)\
        .filter(Integration.is_active == True)\
        .all()
    
    results = []
    
    for integration in active_integrations:
        health_result = await test_integration_connection(integration.provider, integration.config)
        
        # Actualizar estado
        integration.health_status = "healthy" if health_result.get("success") else "unhealthy"
        integration.last_health_check = datetime.utcnow()
        
        if not health_result.get("success"):
            integration.last_error = health_result.get("error")
        else:
            integration.last_error = None
        
        results.append({
            "integration_id": integration.id,
            "provider": integration.provider,
            "name": integration.name,
            "health_status": integration.health_status,
            "health_result": health_result
        })
    
    db.commit()
    
    overall_healthy = all(r["health_result"].get("success", False) for r in results)
    
    return {
        "overall_status": "healthy" if overall_healthy else "degraded",
        "total_integrations": len(results),
        "healthy_count": len([r for r in results if r["health_result"].get("success")]),
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }

# =============================================================================
# META ADS ENDPOINTS
# =============================================================================

@router.post("/integrations/meta-ads/setup-webhook/", response_model=Dict[str, Any])
async def setup_meta_ads_webhook(
    webhook_data: WebhookSetupRequest,
    db: Session = Depends(get_db)
):
    """Configura webhook para Meta Ads"""
    
    try:
        result = await meta_ads_service.setup_webhooks(webhook_data.webhook_url)
        
        if result.get("success"):
            # Actualizar integración con webhook configurado
            integration = db.query(Integration)\
                .filter(Integration.provider == "meta_ads")\
                .first()
            
            if integration:
                integration.is_webhook_configured = True
                integration.webhook_url = webhook_data.webhook_url
                db.commit()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/integrations/crm/retry-failed/", response_model=Dict[str, Any])
async def retry_failed_crm_syncs(
    hours_back: int = 24,
    max_retries: int = 3,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Reintenta sincronizaciones CRM fallidas"""
    
    background_tasks.add_task(
        crm_sync_manager.retry_failed_syncs,
        hours_back,
        max_retries,
        db
    )
    
    return {
        "success": True,
        "message": f"Reintentando syncs fallidos de las últimas {hours_back} horas",
        "status": "processing"
    }

# =============================================================================
# PIPEDRIVE SPECIFIC ENDPOINTS
# =============================================================================

@router.get("/integrations/pipedrive/pipelines/", response_model=List[Dict[str, Any]])
async def get_pipedrive_pipelines():
    """Obtiene pipelines de Pipedrive"""
    
    try:
        pipelines = await pipedrive_service.get_pipelines()
        return pipelines
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/pipedrive/custom-fields/", response_model=Dict[str, Any])
async def get_pipedrive_custom_fields():
    """Obtiene campos personalizados de Pipedrive"""
    
    try:
        custom_fields = await pipedrive_service.get_custom_fields()
        return custom_fields
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/integrations/pipedrive/configure-fields/", response_model=Dict[str, Any])
async def configure_pipedrive_fields():
    """Configura automáticamente campos personalizados de Pipedrive"""
    
    try:
        configured_fields = await pipedrive_service.configure_custom_fields()
        
        return {
            "success": True,
            "configured_fields": configured_fields,
            "message": f"Configurados {len(configured_fields)} campos personalizados"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/integrations/pipedrive/setup-webhook/", response_model=Dict[str, Any])
async def setup_pipedrive_webhook(
    webhook_data: WebhookSetupRequest
):
    """Configura webhook para Pipedrive"""
    
    try:
        result = await pipedrive_service.setup_webhook(
            webhook_data.webhook_url,
            webhook_data.events or ["*"]
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/pipedrive/deals-summary/", response_model=Dict[str, Any])
async def get_pipedrive_deals_summary(days: int = 30):
    """Obtiene resumen de deals de Pipedrive"""
    
    try:
        summary = await pipedrive_service.get_deals_summary(days)
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# WEBHOOK RECEIVERS
# =============================================================================

@router.post("/webhooks/meta-ads/", response_model=Dict[str, Any])
async def receive_meta_ads_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Recibe webhooks de Meta Ads"""
    
    # Verificar si es verificación de webhook
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")
    
    if hub_challenge and hub_verify_token:
        # Validar token
        if hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
            return int(hub_challenge)
        else:
            raise HTTPException(status_code=403, detail="Invalid verify token")
    
    # Procesar webhook normal
    try:
        # Obtener cuerpo del request
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        
        # Verificar firma
        if not await meta_ads_service.verify_webhook_signature(body.decode(), signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parsear datos
        webhook_data = json.loads(body)
        
        # Procesar en background
        background_tasks.add_task(
            meta_ads_service.process_webhook_lead,
            webhook_data,
            db
        )
        
        # Guardar evento de webhook
        webhook_event = WebhookEvent(
            integration_id=None,  # Se podría buscar por provider
            event_id=f"meta_{datetime.utcnow().timestamp()}",
            event_type="leadgen",
            source_system="meta_ads",
            raw_payload=webhook_data,
            headers=dict(request.headers),
            signature=signature
        )
        
        db.add(webhook_event)
        db.commit()
        
        return {"success": True, "message": "Webhook procesado"}
        
    except Exception as e:
        print(f"❌ Error procesando webhook Meta Ads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks/pipedrive/", response_model=Dict[str, Any])
async def receive_pipedrive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Recibe webhooks de Pipedrive"""
    
    try:
        body = await request.body()
        webhook_data = json.loads(body)
        
        # Procesar evento en background
        background_tasks.add_task(
            pipedrive_service.process_webhook_event,
            webhook_data
        )
        
        # Guardar evento
        webhook_event = WebhookEvent(
            integration_id=None,
            event_id=f"pipedrive_{webhook_data.get('id', datetime.utcnow().timestamp())}",
            event_type=f"{webhook_data.get('event', 'unknown')}.{webhook_data.get('object', 'unknown')}",
            source_system="pipedrive",
            raw_payload=webhook_data,
            headers=dict(request.headers)
        )
        
        db.add(webhook_event)
        db.commit()
        
        return {"success": True, "message": "Webhook Pipedrive procesado"}
        
    except Exception as e:
        print(f"❌ Error procesando webhook Pipedrive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks/hubspot/", response_model=Dict[str, Any])
async def receive_hubspot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Recibe webhooks de HubSpot (expandido desde Fase 2)"""
    
    try:
        body = await request.body()
        signature = request.headers.get("X-HubSpot-Signature-v3", "")
        
        # Verificar firma (implementación del webhook existente)
        # ... código de verificación ...
        
        webhook_data = json.loads(body)
        
        # Procesar en background usando el servicio existente
        background_tasks.add_task(
            hubspot_service.process_webhook_event,
            webhook_data,
            db
        )
        
        return {"success": True, "message": "Webhook HubSpot procesado"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ANALYTICS Y REPORTING
# =============================================================================

@router.get("/integrations/analytics/dashboard/", response_model=Dict[str, Any])
async def get_integrations_dashboard(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Obtiene dashboard completo de integraciones"""
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Estadísticas generales
        total_integrations = db.query(Integration).count()
        active_integrations = db.query(Integration).filter(Integration.is_active == True).count()
        healthy_integrations = db.query(Integration)\
            .filter(Integration.health_status == "healthy")\
            .count()
        
        # Leads capturados por fuente externa
        external_leads_stats = db.query(ExternalLead.external_source, 
                                      db.func.count(ExternalLead.id).label('count'))\
            .filter(ExternalLead.processed_at > since_date)\
            .group_by(ExternalLead.external_source)\
            .all()
        
        leads_by_source = {source: count for source, count in external_leads_stats}
        
        # Sync performance
        sync_stats = db.query(SyncLog.integration_type,
                            db.func.count(SyncLog.id).label('total'),
                            db.func.sum(db.case([(SyncLog.status == 'completed', 1)], else_=0)).label('successful'))\
            .filter(SyncLog.started_at > since_date)\
            .group_by(SyncLog.integration_type)\
            .all()
        
        sync_performance = []
        for integration_type, total, successful in sync_stats:
            success_rate = successful / total if total > 0 else 0
            sync_performance.append({
                "integration": integration_type,
                "total_syncs": total,
                "successful_syncs": successful or 0,
                "success_rate": success_rate
            })
        
        # Top error messages
        error_stats = db.query(SyncLog.error_message,
                             db.func.count(SyncLog.id).label('count'))\
            .filter(SyncLog.status == 'failed')\
            .filter(SyncLog.started_at > since_date)\
            .filter(SyncLog.error_message.isnot(None))\
            .group_by(SyncLog.error_message)\
            .order_by(db.func.count(SyncLog.id).desc())\
            .limit(5)\
            .all()
        
        top_errors = [{"error": error[:100], "count": count} for error, count in error_stats]
        
        # Webhook events
        webhook_stats = db.query(WebhookEvent.source_system,
                               db.func.count(WebhookEvent.id).label('total'),
                               db.func.sum(db.case([(WebhookEvent.is_processed == True, 1)], else_=0)).label('processed'))\
            .filter(WebhookEvent.received_at > since_date)\
            .group_by(WebhookEvent.source_system)\
            .all()
        
        webhook_performance = []
        for source, total, processed in webhook_stats:
            processing_rate = processed / total if total > 0 else 0
            webhook_performance.append({
                "source": source,
                "total_events": total,
                "processed_events": processed or 0,
                "processing_rate": processing_rate
            })
        
        return {
            "period_days": days,
            "summary": {
                "total_integrations": total_integrations,
                "active_integrations": active_integrations,
                "healthy_integrations": healthy_integrations,
                "health_rate": healthy_integrations / active_integrations if active_integrations > 0 else 0
            },
            "lead_capture": {
                "total_external_leads": sum(leads_by_source.values()),
                "leads_by_source": leads_by_source
            },
            "sync_performance": sync_performance,
            "webhook_performance": webhook_performance,
            "top_errors": top_errors,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/analytics/attribution/", response_model=Dict[str, Any])
async def get_attribution_report(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Genera reporte de atribución de leads por fuente"""
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Leads por fuente externa
        external_attribution = db.query(
            ExternalLead.external_source,
            ExternalLead.utm_source,
            ExternalLead.utm_campaign,
            db.func.count(ExternalLead.id).label('leads_count'),
            db.func.avg(Lead.score).label('avg_score')
        ).join(Lead)\
         .filter(ExternalLead.processed_at > since_date)\
         .group_by(ExternalLead.external_source, ExternalLead.utm_source, ExternalLead.utm_campaign)\
         .all()
        
        attribution_data = []
        for source, utm_source, utm_campaign, leads_count, avg_score in external_attribution:
            attribution_data.append({
                "external_source": source,
                "utm_source": utm_source,
                "utm_campaign": utm_campaign,
                "leads_count": leads_count,
                "avg_score": float(avg_score) if avg_score else 0,
                "quality_tier": "high" if avg_score and avg_score >= 70 else "medium" if avg_score and avg_score >= 40 else "low"
            })
        
        # Leads internos (sin fuente externa)
        internal_leads = db.query(Lead)\
            .filter(Lead.created_at > since_date)\
            .filter(~Lead.external_leads.any())\
            .count()
        
        total_leads = db.query(Lead).filter(Lead.created_at > since_date).count()
        external_leads_total = sum(item["leads_count"] for item in attribution_data)
        
        return {
            "period_days": days,
            "summary": {
                "total_leads": total_leads,
                "external_leads": external_leads_total,
                "internal_leads": internal_leads,
                "external_attribution_rate": external_leads_total / total_leads if total_leads > 0 else 0
            },
            "attribution_breakdown": attribution_data,
            "top_sources": sorted(attribution_data, key=lambda x: x["leads_count"], reverse=True)[:5],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def test_integration_connection(provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Testa la conexión con una integración específica"""
    
    try:
        if provider == "meta_ads":
            # Configurar temporalmente el servicio con la config
            service = MetaAdsService()
            service.access_token = config.get("access_token")
            service.app_secret = config.get("app_secret")
            service.ad_account_id = config.get("ad_account_id")
            
            return await service.health_check()
            
        elif provider == "pipedrive":
            service = PipedriveService()
            service.api_token = config.get("api_token")
            
            return await service.health_check()
            
        elif provider == "hubspot":
            service = HubSpotService()
            # Configurar con datos de config
            
            return await service.health_check()
            
        else:
            return {
                "success": False,
                "error": f"Provider {provider} no soportado para health check"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/integrations/meta-ads/sync-historical/", response_model=Dict[str, Any])
async def sync_meta_ads_historical(
    days_back: int = 7,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Sincroniza leads históricos de Meta Ads"""
    
    background_tasks.add_task(
        meta_ads_service.sync_historical_leads,
        days_back,
        50,  # batch_size
        db
    )
    
    return {
        "success": True,
        "message": f"Sincronización histórica iniciada para últimos {days_back} días",
        "status": "processing"
    }

@router.get("/integrations/meta-ads/campaigns/", response_model=List[Dict[str, Any]])
async def get_meta_ads_campaigns():
    """Obtiene campañas de Meta Ads"""
    
    try:
        campaigns = await meta_ads_service.get_campaigns()
        return campaigns
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/meta-ads/metrics/", response_model=Dict[str, Any])
async def get_meta_ads_metrics(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Obtiene métricas de atribución de Meta Ads"""
    
    try:
        metrics = await meta_ads_service.get_attribution_report(days, db)
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# CRM SYNC ENDPOINTS
# =============================================================================

@router.post("/integrations/crm/sync/", response_model=Dict[str, Any])
async def sync_leads_to_crm(
    sync_data: CRMSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Sincroniza leads con CRM especificado"""
    
    try:
        # Validar CRM provider
        crm_provider = CRMProvider(sync_data.crm_provider)
        sync_direction = SyncDirection(sync_data.direction)
        
        # Ejecutar sync en background
        background_tasks.add_task(
            crm_sync_manager.bulk_sync_leads,
            sync_data.lead_ids,
            crm_provider,
            sync_direction,
            sync_data.batch_size or 50,
            db
        )
        
        return {
            "success": True,
            "message": f"Iniciando sync de {len(sync_data.lead_ids)} leads a {crm_provider}",
            "sync_direction": sync_direction,
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/integrations/crm/sync-all/", response_model=Dict[str, Any])
async def sync_all_leads_to_crm(
    crm_provider: str,
    days_back: Optional[int] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Sincroniza todos los leads (o desde una fecha) con un CRM"""
    
    try:
        provider = CRMProvider(crm_provider)
        since_date = datetime.utcnow() - timedelta(days=days_back) if days_back else None
        
        background_tasks.add_task(
            crm_sync_manager.sync_all_leads_to_crm,
            provider,
            since_date,
            db
        )
        
        return {
            "success": True,
            "message": f"Sync masivo iniciado para {crm_provider}",
            "since_date": since_date.isoformat() if since_date else None,
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/crm/metrics/", response_model=Dict[str, Any])
async def get_crm_sync_metrics(
    days: int = 30,
    crm_provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtiene métricas de sincronización CRM"""
    
    try:
        provider = CRMProvider(crm_provider) if crm_provider else None
        metrics = await crm_sync_manager.get_sync_metrics(days, provider, db)
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))