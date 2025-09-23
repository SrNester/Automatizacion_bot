from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, WebSocket
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import json

from ..core.database import get_db
from ..services.analytics.analytics_engine import AnalyticsEngine
from ..services.analytics.report_generator import ReportGenerator
from ..services.notifications.notification_service import NotificationService
from ..models.lead import Lead 

router = APIRouter()

# Servicios
analytics_engine = AnalyticsEngine()
report_generator = ReportGenerator()
notification_service = NotificationService()

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DashboardRequest(BaseModel):
    days: int = 30
    granularity: str = "daily"  # daily, weekly, monthly
    filters: Optional[Dict[str, Any]] = None

class ReportRequest(BaseModel):
    report_type: str  # executive, detailed, custom
    period: str = "monthly"  # weekly, monthly, quarterly
    format: str = "json"  # json, pdf, excel
    email_recipients: Optional[List[str]] = None
    custom_filters: Optional[Dict[str, Any]] = None

class AlertRequest(BaseModel):
    metric: str
    condition: str  # gt, lt, eq, change_gt, change_lt
    threshold: float
    notification_channels: List[str] = ["email"]
    is_active: bool = True

# =============================================================================
# EXECUTIVE DASHBOARD ENDPOINTS
# =============================================================================

@router.get("/dashboard/executive/", response_model=Dict[str, Any])
async def get_executive_dashboard(
    days: int = Query(30, ge=1, le=365),
    refresh_cache: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Obtiene dashboard ejecutivo completo"""
    
    try:
        if refresh_cache:
            analytics_engine.clear_cache("executive_dashboard:*")
        
        dashboard_data = await analytics_engine.get_executive_dashboard(days, db)
        
        return {
            "success": True,
            "data": dashboard_data,
            "meta": {
                "generated_at": datetime.utcnow().isoformat(),
                "period_days": days,
                "cache_refreshed": refresh_cache
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo dashboard: {str(e)}")

@router.get("/dashboard/kpis/", response_model=Dict[str, Any])
async def get_kpi_summary(
    days: int = Query(30, ge=1, le=365),
    kpis: Optional[str] = Query(None, description="Comma-separated list of specific KPIs"),
    db: Session = Depends(get_db)
):
    """Obtiene resumen de KPIs específicos"""
    
    try:
        dashboard_data = await analytics_engine.get_executive_dashboard(days, db)
        kpi_data = dashboard_data.get("kpi_summary", {})
        
        # Filtrar KPIs específicos si se solicitan
        if kpis:
            requested_kpis = [kpi.strip() for kpi in kpis.split(",")]
            kpi_data = {k: v for k, v in kpi_data.items() if k in requested_kpis}
        
        return {
            "success": True,
            "kpis": kpi_data,
            "definitions": {k: v for k, v in analytics_engine.kpi_definitions.items() 
                          if not kpis or k in requested_kpis.split(",")},
            "period_days": days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo KPIs: {str(e)}")

@router.get("/dashboard/real-time/", response_model=Dict[str, Any])
async def get_real_time_metrics(db: Session = Depends(get_db)):
    """Obtiene métricas en tiempo real"""
    
    try:
        real_time_data = await analytics_engine.get_real_time_metrics(db)
        
        return {
            "success": True,
            "data": real_time_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas en tiempo real: {str(e)}")

# =============================================================================
# ANALYTICS DETALLADOS
# =============================================================================

@router.get("/dashboard/analytics/{metric}/", response_model=Dict[str, Any])
async def get_detailed_analytics(
    metric: str,
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$"),
    source: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db)
):
    """Obtiene analytics detallados para una métrica específica"""
    
    try:
        filters = {}
        if source:
            filters["source"] = source
        if min_score is not None:
            filters["min_score"] = min_score
        
        detailed_data = await analytics_engine.get_detailed_analytics(
            metric=metric,
            days=days,
            granularity=granularity,
            filters=filters,
            db=db
        )
        
        if "error" in detailed_data:
            raise HTTPException(status_code=400, detail=detailed_data["error"])
        
        return {
            "success": True,
            "metric": metric,
            "data": detailed_data,
            "filters_applied": filters,
            "granularity": granularity,
            "period_days": days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo analytics: {str(e)}")

@router.get("/dashboard/funnel/", response_model=Dict[str, Any])
async def get_conversion_funnel(
    days: int = Query(30, ge=1, le=365),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Obtiene análisis detallado del funnel de conversión"""
    
    try:
        filters = {"source": source} if source else None
        
        funnel_data = await analytics_engine.get_detailed_analytics(
            metric="conversion_funnel",
            days=days,
            filters=filters,
            db=db
        )
        
        return {
            "success": True,
            "funnel_data": funnel_data,
            "source_filter": source,
            "period_days": days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo funnel: {str(e)}")

@router.get("/dashboard/channels/", response_model=Dict[str, Any])
async def get_channel_performance(
    days: int = Query(30, ge=1, le=365),
    sort_by: str = Query("leads_count", regex="^(leads_count|conversion_rate|roi|cost_per_lead)$"),
    db: Session = Depends(get_db)
):
    """Obtiene performance detallado por canal"""
    
    try:
        dashboard_data = await analytics_engine.get_executive_dashboard(days, db)
        channel_data = dashboard_data.get("channel_performance", [])
        
        # Ordenar por métrica solicitada
        if sort_by == "conversion_rate":
            channel_data = sorted(channel_data, key=lambda x: x["conversion_rate"], reverse=True)
        elif sort_by == "roi":
            channel_data = sorted(channel_data, key=lambda x: x["roi"], reverse=True)
        elif sort_by == "cost_per_lead":
            channel_data = sorted(channel_data, key=lambda x: x["cost_per_lead"])
        # Por defecto ya está ordenado por leads_count
        
        return {
            "success": True,
            "channels": channel_data,
            "sorted_by": sort_by,
            "period_days": days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo canales: {str(e)}")

# =============================================================================
# REPORTING ENDPOINTS
# =============================================================================

@router.post("/dashboard/reports/generate/", response_model=Dict[str, Any])
async def generate_report(
    report_request: ReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Genera un reporte personalizado"""
    
    try:
        if report_request.format == "json":
            # Generar reporte inmediatamente
            if report_request.report_type == "executive":
                report_data = await analytics_engine.generate_executive_report(
                    report_request.period, db
                )
            else:
                # Otros tipos de reporte
                report_data = await report_generator.generate_custom_report(
                    report_request.report_type,
                    report_request.period,
                    report_request.custom_filters,
                    db
                )
            
            return {
                "success": True,
                "report": report_data,
                "format": "json"
            }
        
        else:
            # Generar reporte en background (PDF/Excel)
            background_tasks.add_task(
                report_generator.generate_and_send_report,
                report_request.report_type,
                report_request.period,
                report_request.format,
                report_request.email_recipients,
                report_request.custom_filters,
                db
            )
            
            return {
                "success": True,
                "message": f"Reporte {report_request.format.upper()} será generado y enviado",
                "status": "processing"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando reporte: {str(e)}")

@router.get("/dashboard/reports/templates/", response_model=List[Dict[str, Any]])
async def get_report_templates():
    """Obtiene plantillas de reportes disponibles"""
    
    templates = [
        {
            "id": "executive",
            "name": "Reporte Ejecutivo",
            "description": "Resumen ejecutivo con KPIs principales y insights",
            "sections": ["kpis", "trends", "insights", "recommendations"],
            "formats": ["json", "pdf", "excel"]
        },
        {
            "id": "detailed_analytics",
            "name": "Analytics Detallado",
            "description": "Análisis profundo de métricas y performance",
            "sections": ["funnel", "channels", "conversions", "quality"],
            "formats": ["json", "pdf", "excel"]
        },
        {
            "id": "channel_performance",
            "name": "Performance por Canal",
            "description": "Análisis detallado de ROI y performance por canal",
            "sections": ["channel_metrics", "attribution", "costs", "trends"],
            "formats": ["json", "pdf", "excel"]
        },
        {
            "id": "lead_quality",
            "name": "Calidad de Leads",
            "description": "Análisis de scoring, segmentación y calidad",
            "sections": ["score_distribution", "sources", "quality_trends"],
            "formats": ["json", "pdf"]
        }
    ]
    
    return templates

@router.get("/dashboard/exports/{export_id}/", response_model=Dict[str, Any])
async def get_export_status(export_id: str):
    """Obtiene el estado de un export en proceso"""
    
    try:
        # En producción, esto consultaría el estado de una tarea de Celery
        # Por ahora, mock response
        
        status_data = {
            "export_id": export_id,
            "status": "completed",  # pending, processing, completed, failed
            "progress": 100,
            "download_url": f"/api/v1/dashboard/downloads/{export_id}",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        
        return {
            "success": True,
            "export": status_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado del export: {str(e)}")

# =============================================================================
# CONFIGURACIÓN Y PERSONALIZACIÓN
# =============================================================================

@router.get("/dashboard/config/", response_model=Dict[str, Any])
async def get_dashboard_config(db: Session = Depends(get_db)):
    """Obtiene configuración actual del dashboard"""
    
    # Mock configuration - en producción vendría de BD
    config = {
        "default_period": 30,
        "refresh_interval": 60,  # seconds
        "widgets": [
            {
                "id": "kpi_cards",
                "name": "KPI Cards",
                "type": "kpi_grid",
                "position": {"row": 0, "col": 0, "width": 12, "height": 2},
                "config": {
                    "metrics": ["total_leads", "conversion_rate", "avg_lead_score", "roi"]
                }
            },
            {
                "id": "conversion_trends",
                "name": "Tendencias de Conversión",
                "type": "line_chart",
                "position": {"row": 2, "col": 0, "width": 8, "height": 4},
                "config": {
                    "metric": "conversion_trends",
                    "show_forecast": True
                }
            },
            {
                "id": "channel_performance",
                "name": "Performance por Canal",
                "type": "bar_chart",
                "position": {"row": 2, "col": 8, "width": 4, "height": 4},
                "config": {
                    "metric": "channel_performance",
                    "sort_by": "roi"
                }
            },
            {
                "id": "lead_funnel",
                "name": "Funnel de Leads",
                "type": "funnel_chart",
                "position": {"row": 6, "col": 0, "width": 6, "height": 3},
                "config": {
                    "metric": "lead_funnel"
                }
            },
            {
                "id": "system_health",
                "name": "Salud del Sistema",
                "type": "health_gauge",
                "position": {"row": 6, "col": 6, "width": 6, "height": 3},
                "config": {
                    "metric": "system_health"
                }
            }
        ],
        "alerts": [
            {
                "metric": "conversion_rate",
                "condition": "lt",
                "threshold": 0.15,
                "active": True
            },
            {
                "metric": "response_time",
                "condition": "gt", 
                "threshold": 5,
                "active": True
            }
        ],
        "theme": {
            "primary_color": "#3B82F6",
            "secondary_color": "#10B981",
            "accent_color": "#F59E0B",
            "danger_color": "#EF4444"
        }
    }
    
    return {
        "success": True,
        "config": config
    }

@router.post("/dashboard/config/", response_model=Dict[str, Any])
async def update_dashboard_config(
    config: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Actualiza configuración del dashboard"""
    
    try:
        # En producción, guardar en BD
        # Para demo, solo validar estructura
        
        required_fields = ["widgets", "default_period"]
        for field in required_fields:
            if field not in config:
                raise HTTPException(status_code=400, detail=f"Campo requerido: {field}")
        
        return {
            "success": True,
            "message": "Configuración actualizada exitosamente",
            "config": config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando configuración: {str(e)}")

# =============================================================================
# ALERTAS Y NOTIFICACIONES
# =============================================================================

@router.post("/dashboard/alerts/", response_model=Dict[str, Any])
async def create_alert(
    alert_request: AlertRequest,
    db: Session = Depends(get_db)
):
    """Crea una nueva alerta"""
    
    try:
        alert_config = {
            "id": f"alert_{datetime.utcnow().timestamp()}",
            "metric": alert_request.metric,
            "condition": alert_request.condition,
            "threshold": alert_request.threshold,
            "notification_channels": alert_request.notification_channels,
            "is_active": alert_request.is_active,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # En producción, guardar en BD
        
        return {
            "success": True,
            "alert": alert_config,
            "message": "Alerta creada exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando alerta: {str(e)}")

@router.get("/dashboard/alerts/", response_model=List[Dict[str, Any]])
async def get_alerts(db: Session = Depends(get_db)):
    """Obtiene todas las alertas configuradas"""
    
    # Mock alerts - en producción vendría de BD
    alerts = [
        {
            "id": "alert_1",
            "metric": "conversion_rate",
            "condition": "lt",
            "threshold": 0.15,
            "notification_channels": ["email", "slack"],
            "is_active": True,
            "last_triggered": None,
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": "alert_2",
            "metric": "response_time",
            "condition": "gt",
            "threshold": 5.0,
            "notification_channels": ["email"],
            "is_active": True,
            "last_triggered": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
    ]
    
    return alerts

@router.delete("/dashboard/alerts/{alert_id}/", response_model=Dict[str, Any])
async def delete_alert(alert_id: str, db: Session = Depends(get_db)):
    """Elimina una alerta"""
    
    try:
        # En producción, eliminar de BD
        
        return {
            "success": True,
            "message": f"Alerta {alert_id} eliminada exitosamente"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando alerta: {str(e)}")

# =============================================================================
# WEBSOCKET PARA DATOS EN TIEMPO REAL
# =============================================================================

@router.websocket("/dashboard/live")
async def websocket_live_data(websocket: WebSocket, db: Session = Depends(get_db)):
    """WebSocket para datos en tiempo real"""
    
    await websocket.accept()
    
    try:
        while True:
            # Obtener datos en tiempo real
            real_time_data = await analytics_engine.get_real_time_metrics(db)
            
            # Enviar datos al cliente
            await websocket.send_json({
                "type": "real_time_update",
                "data": real_time_data
            })
            
            # Esperar 30 segundos antes de la próxima actualización
            await asyncio.sleep(30)
            
    except Exception as e:
        print(f"Error en WebSocket: {e}")
    finally:
        await websocket.close()

@router.websocket("/dashboard/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket para notificaciones en tiempo real"""
    
    await websocket.accept()
    
    try:
        while True:
            # Verificar si hay nuevas notificaciones
            notifications = await notification_service.get_pending_notifications()
            
            if notifications:
                await websocket.send_json({
                    "type": "notifications",
                    "data": notifications
                })
            
            # Verificar cada 10 segundos
            await asyncio.sleep(10)
            
    except Exception as e:
        print(f"Error en WebSocket notifications: {e}")
    finally:
        await websocket.close()

# =============================================================================
# UTILIDADES Y HEALTH CHECKS
# =============================================================================

@router.get("/dashboard/health/", response_model=Dict[str, Any])
async def dashboard_health_check(db: Session = Depends(get_db)):
    """Health check del sistema de dashboard"""
    
    try:
        # Test básico de BD
        db.execute("SELECT 1")
        
        # Test de cache Redis
        cache_status = "healthy"
        if analytics_engine.redis_client:
            try:
                analytics_engine.redis_client.ping()
            except:
                cache_status = "unhealthy"
        else:
            cache_status = "not_configured"
        
        # Test de datos básicos
        lead_count = db.query(Lead).count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy",
                "cache": cache_status,
                "analytics_engine": "healthy",
                "data_availability": "healthy" if lead_count > 0 else "no_data"
            },
            "version": "1.0.0"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/dashboard/cache/clear/", response_model=Dict[str, Any])
async def clear_dashboard_cache(
    pattern: str = Query("*", description="Cache pattern to clear")
):
    """Limpia el cache del dashboard"""
    
    try:
        cleared_keys = analytics_engine.clear_cache(pattern)
        
        return {
            "success": True,
            "cleared_keys": cleared_keys,
            "pattern": pattern,
            "message": f"Cache limpiado: {cleared_keys} keys eliminadas"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error limpiando cache: {str(e)}")

@router.get("/dashboard/meta/", response_model=Dict[str, Any])
async def get_dashboard_meta():
    """Obtiene metadatos del dashboard"""
    
    return {
        "version": "1.0.0",
        "last_updated": datetime.utcnow().isoformat(),
        "supported_metrics": list(analytics_engine.kpi_definitions.keys()),
        "supported_periods": [7, 14, 30, 60, 90, 180, 365],
        "supported_formats": ["json", "pdf", "excel"],
        "real_time_interval": 30,  # seconds
        "cache_ttl": analytics_engine.cache_ttl,
        "features": {
            "real_time_updates": True,
            "custom_reports": True,
            "predictive_analytics": True,
            "alerts": True,
            "webhooks": True,
            "mobile_responsive": True
        }
    }