from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..core.database import get_db
from ..services.lead_service import (
    get_total_leads, get_hot_leads_count, calculate_conversion_rate,
    get_top_lead_sources, get_leads_by_status, get_leads_by_date_range,
    get_lead_growth_metrics, get_interaction_metrics
)
from ..services.lead_scoring import LeadScoringService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])

class ReportService:
    def __init__(self):
        self.scoring_service = LeadScoringService()
    
    async def generate_lead_report(self, db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Genera reporte completo de leads"""
        try:
            # Parse dates
            if start_date:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_date = datetime.now()
            
            if start_date and end_date and start_date > end_date:
                raise ValueError("La fecha de inicio no puede ser mayor a la fecha fin")
            
            # Get basic metrics
            total_leads = get_total_leads(db)
            hot_leads = get_hot_leads_count(db)
            conversion_rate = calculate_conversion_rate(db)
            top_sources = get_top_lead_sources(db, limit=10)
            
            # Get time-based metrics
            lead_growth = get_lead_growth_metrics(db, start_date, end_date)
            leads_by_status = get_leads_by_status(db)
            leads_by_date = get_leads_by_date_range(db, start_date, end_date)
            
            # Get interaction metrics
            interaction_metrics = get_interaction_metrics(db, start_date, end_date)
            
            # Calculate average score
            avg_score = self.scoring_service.get_average_lead_score(db)
            
            return {
                "report_period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat(),
                    "days_covered": (end_date - start_date).days if start_date else None
                },
                "summary_metrics": {
                    "total_leads": total_leads,
                    "hot_leads": hot_leads,
                    "conversion_rate": conversion_rate,
                    "average_lead_score": avg_score,
                    "hot_lead_percentage": (hot_leads / total_leads * 100) if total_leads > 0 else 0
                },
                "lead_sources": top_sources,
                "lead_growth": lead_growth,
                "leads_by_status": leads_by_status,
                "leads_timeline": leads_by_date,
                "interaction_metrics": interaction_metrics
            }
            
        except Exception as e:
            logger.error(f"Error generando reporte de leads: {str(e)}")
            raise
    
    async def generate_performance_report(self, db: Session, days: int = 30):
        """Genera reporte de performance del sistema"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get lead metrics
            lead_metrics = await self.generate_lead_report(db, start_date.isoformat(), end_date.isoformat())
            
            # Calculate additional performance metrics
            total_interactions = lead_metrics["interaction_metrics"].get("total_interactions", 0)
            avg_interactions_per_lead = total_interactions / lead_metrics["summary_metrics"]["total_leads"] if lead_metrics["summary_metrics"]["total_leads"] > 0 else 0
            
            # Response time metrics (placeholder - implementar según necesidad)
            avg_response_time = self.calculate_avg_response_time(db, start_date, end_date)
            
            return {
                "performance_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                },
                "efficiency_metrics": {
                    "leads_per_day": lead_metrics["summary_metrics"]["total_leads"] / days,
                    "conversion_rate": lead_metrics["summary_metrics"]["conversion_rate"],
                    "average_response_time_minutes": avg_response_time,
                    "interactions_per_lead": avg_interactions_per_lead
                },
                "lead_quality_metrics": {
                    "average_lead_score": lead_metrics["summary_metrics"]["average_lead_score"],
                    "hot_lead_percentage": lead_metrics["summary_metrics"]["hot_lead_percentage"],
                    "lead_score_distribution": self.get_lead_score_distribution(db)
                },
                "source_performance": self.analyze_source_performance(lead_metrics["lead_sources"]),
                "trends": self.calculate_trends(lead_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error generando reporte de performance: {str(e)}")
            raise
    
    def calculate_avg_response_time(self, db: Session, start_date: datetime, end_date: datetime) -> float:
        """Calcula el tiempo promedio de respuesta (placeholder)"""
        # Implementar lógica real según tu base de datos
        try:
            # Ejemplo simplificado - adaptar a tu schema
            return 45.2  # minutos promedio
        except:
            return 0.0
    
    def get_lead_score_distribution(self, db: Session) -> Dict[str, int]:
        """Obtiene distribución de scores de leads"""
        # Implementar según tu base de datos
        return {
            "cold_0_25": 15,
            "warm_26_50": 30,
            "hot_51_75": 40,
            "very_hot_76_100": 15
        }
    
    def analyze_source_performance(self, sources: List[Dict]) -> List[Dict]:
        """Analiza performance por fuente de lead"""
        analyzed_sources = []
        for source in sources:
            conversion_rate = source.get('conversion_rate', 0)
            quality = "high" if conversion_rate > 20 else "medium" if conversion_rate > 10 else "low"
            
            analyzed_sources.append({
                **source,
                "quality_tier": quality,
                "recommendation": self.get_source_recommendation(quality)
            })
        
        return analyzed_sources
    
    def get_source_recommendation(self, quality: str) -> str:
        """Genera recomendaciones basadas en calidad de fuente"""
        recommendations = {
            "high": "Aumentar inversión en esta fuente",
            "medium": "Mantener y optimizar campañas",
            "low": "Reevaluar o reducir inversión"
        }
        return recommendations.get(quality, "Monitorear performance")
    
    def calculate_trends(self, lead_metrics: Dict) -> Dict[str, Any]:
        """Calcula tendencias basadas en métricas históricas"""
        # Placeholder - implementar con datos reales
        return {
            "lead_growth_trend": "up",
            "conversion_trend": "stable",
            "score_trend": "up",
            "predicted_conversions_next_month": 25
        }

# Initialize report service
report_service = ReportService()

@router.get("/leads")
async def get_lead_report(
    start_date: Optional[str] = Query(None, description="Fecha inicio (ISO format)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (ISO format)"),
    db: Session = Depends(get_db)
):
    """
    Genera reporte completo de leads con filtros de fecha opcionales
    """
    try:
        report = await report_service.generate_lead_report(db, start_date, end_date)
        return {
            "success": True,
            "report_type": "lead_analysis",
            "data": report
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generando reporte de leads: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno generando reporte")

@router.get("/performance")
async def get_performance_report(
    days: int = Query(30, description="Número de días para analizar", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Reporte de performance del sistema de automatización
    """
    try:
        report = await report_service.generate_performance_report(db, days)
        return {
            "success": True,
            "report_type": "system_performance",
            "data": report
        }
    except Exception as e:
        logger.error(f"Error generando reporte de performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno generando reporte de performance")

@router.get("/sources")
async def get_source_analysis_report(
    db: Session = Depends(get_db)
):
    """
    Reporte detallado de análisis de fuentes de leads
    """
    try:
        report = await report_service.generate_lead_report(db)
        source_analysis = report_service.analyze_source_performance(report["lead_sources"])
        
        return {
            "success": True,
            "report_type": "source_analysis",
            "data": {
                "sources": source_analysis,
                "top_performing": [s for s in source_analysis if s["quality_tier"] == "high"],
                "needs_attention": [s for s in source_analysis if s["quality_tier"] == "low"]
            }
        }
    except Exception as e:
        logger.error(f"Error generando reporte de fuentes: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno generando reporte de fuentes")

@router.get("/conversions")
async def get_conversion_report(
    start_date: Optional[str] = Query(None, description="Fecha inicio (ISO format)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (ISO format)"),
    db: Session = Depends(get_db)
):
    """
    Reporte especializado en análisis de conversiones
    """
    try:
        lead_report = await report_service.generate_lead_report(db, start_date, end_date)
        
        conversion_data = {
            "overall_conversion_rate": lead_report["summary_metrics"]["conversion_rate"],
            "conversions_by_source": [
                {
                    "source": source["source"],
                    "conversion_rate": source.get("conversion_rate", 0),
                    "total_leads": source["count"]
                }
                for source in lead_report["lead_sources"]
            ],
            "conversion_timeline": lead_report["leads_timeline"],
            "conversion_velocity": report_service.calculate_conversion_velocity(db, start_date, end_date)
        }
        
        return {
            "success": True,
            "report_type": "conversion_analysis",
            "data": conversion_data
        }
    except Exception as e:
        logger.error(f"Error generando reporte de conversiones: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno generando reporte de conversiones")

@router.get("/export")
async def export_reports(
    report_type: str = Query(..., description="Tipo de reporte: leads, performance, sources, conversions"),
    format: str = Query("json", description="Formato: json, csv"),
    db: Session = Depends(get_db)
):
    """
    Exporta reportes en diferentes formatos
    """
    try:
        # Generar reporte base según tipo
        if report_type == "leads":
            data = await report_service.generate_lead_report(db)
        elif report_type == "performance":
            data = await report_service.generate_performance_report(db)
        elif report_type == "sources":
            lead_report = await report_service.generate_lead_report(db)
            data = report_service.analyze_source_performance(lead_report["lead_sources"])
        elif report_type == "conversions":
            lead_report = await report_service.generate_lead_report(db)
            data = {
                "conversion_rate": lead_report["summary_metrics"]["conversion_rate"],
                "sources": lead_report["lead_sources"]
            }
        else:
            raise HTTPException(status_code=400, detail="Tipo de reporte no válido")
        
        # Simular export según formato
        if format == "csv":
            # En una implementación real, generar CSV
            return {
                "success": True,
                "message": "Exportación CSV simulada - implementar generación real",
                "data": data
            }
        else:
            return {
                "success": True,
                "format": "json",
                "data": data
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exportando reporte: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno exportando reporte")

# Endpoints adicionales para métricas específicas
@router.get("/metrics/daily")
async def get_daily_metrics(
    days: int = Query(7, description="Días a retroceder", ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Obtiene métricas diarias para dashboards"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        daily_data = []
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            next_date = current_date + timedelta(days=1)
            
            day_leads = get_leads_by_date_range(
                db, 
                current_date, 
                next_date
            )
            
            daily_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "leads": len(day_leads),
                "conversions": sum(1 for lead in day_leads if lead.get('converted', False))
            })
        
        return {
            "success": True,
            "period": f"last_{days}_days",
            "data": daily_data
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas diarias: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno obteniendo métricas")

# Extender la clase ReportService con métodos adicionales
def calculate_conversion_velocity(self, db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Calcula la velocidad de conversión (placeholder)"""
    # Implementar lógica real de velocidad de conversión
    return {
        "average_days_to_convert": 7.5,
        "fastest_conversion": 1,
        "slowest_conversion": 30
    }

# Añadir el método a la clase
ReportService.calculate_conversion_velocity = calculate_conversion_velocity