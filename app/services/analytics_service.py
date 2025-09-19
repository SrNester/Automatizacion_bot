import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ..models.lead import Lead, Interaction
from ..core.database import get_db
from .integrations.hubspot_service import HubSpotService

class HubSpotAnalyticsService:
    def __init__(self):
        self.hubspot = HubSpotService()
    
    async def get_real_time_dashboard_data(self, db: Session, days: int = 30) -> Dict:
        """Obtiene datos del dashboard en tiempo real"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Ejecutar todas las consultas en paralelo
        tasks = [
            self._get_lead_metrics(db, start_date, end_date),
            self._get_conversion_funnel(db, start_date, end_date),
            self._get_source_performance(db, start_date, end_date),
            self._get_score_distribution(db),
            self._get_hubspot_sync_metrics(db),
            self._get_interaction_analytics(db, start_date, end_date),
            self._get_revenue_forecast(db)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            "lead_metrics": results[0],
            "conversion_funnel": results[1], 
            "source_performance": results[2],
            "score_distribution": results[3],
            "sync_metrics": results[4],
            "interaction_analytics": results[5],
            "revenue_forecast": results[6],
            "last_updated": datetime.now().isoformat()
        }
    
    async def _get_lead_metrics(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Métricas básicas de leads"""
        
        total_leads = db.query(Lead).filter(
            and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
        ).count()
        
        qualified_leads = db.query(Lead).filter(
            and_(
                Lead.created_at >= start_date, 
                Lead.created_at <= end_date,
                Lead.is_qualified == True
            )
        ).count()
        
        hot_leads = db.query(Lead).filter(
            and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date, 
                Lead.status == 'hot'
            )
        ).count()
        
        converted_leads = db.query(Lead).filter(
            and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date,
                Lead.status == 'converted'
            )
        ).count()
        
        # Comparación con período anterior
        prev_start = start_date - timedelta(days=(end_date - start_date).days)
        prev_total = db.query(Lead).filter(
            and_(Lead.created_at >= prev_start, Lead.created_at < start_date)
        ).count()
        
        growth_rate = ((total_leads - prev_total) / prev_total * 100) if prev_total > 0 else 0
        
        return {
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "hot_leads": hot_leads,
            "converted_leads": converted_leads,
            "qualification_rate": (qualified_leads / total_leads * 100) if total_leads > 0 else 0,
            "conversion_rate": (converted_leads / total_leads * 100) if total_leads > 0 else 0,
            "growth_rate": round(growth_rate, 2)
        }
    
    async def _get_conversion_funnel(self, db: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Análisis del embudo de conversión"""
        
        funnel_stages = [
            ("Visitantes", "website_visit"),
            ("Leads", "form_submission"), 
            ("Calificados", "qualified"),
            ("Demos", "demo_request"),
            ("Propuestas", "proposal_sent"),
            ("Cerrados", "converted")
        ]
        
        funnel_data = []
        
        for stage_name, stage_filter in funnel_stages:
            if stage_filter in ["qualified", "converted"]:
                count = db.query(Lead).filter(
                    and_(
                        Lead.created_at >= start_date,
                        Lead.created_at <= end_date,
                        getattr(Lead, 'is_qualified' if stage_filter == 'qualified' else 'status') == (True if stage_filter == 'qualified' else 'converted')
                    )
                ).count()
            else:
                count = db.query(Interaction).join(Lead).filter(
                    and_(
                        Interaction.timestamp >= start_date,
                        Interaction.timestamp <= end_date,
                        Interaction.type == stage_filter
                    )
                ).count()
            
            funnel_data.append({
                "stage": stage_name,
                "count": count,
                "percentage": 0  # Se calculará después
            })
        
        # Calcular porcentajes basados en el primer stage
        if funnel_data and funnel_data[0]["count"] > 0:
            base_count = funnel_data[0]["count"]
            for stage in funnel_data:
                stage["percentage"] = (stage["count"] / base_count * 100) if base_count > 0 else 0
        
        return funnel_data
    
    async def _get_source_performance(self, db: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Performance por fuente de lead"""
        
        sources = db.query(
            Lead.source,
            func.count(Lead.id).label('total_leads'),
            func.avg(Lead.score).label('avg_score'),
            func.sum(func.case([(Lead.status == 'converted', 1)], else_=0)).label('conversions')
        ).filter(
            and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
        ).group_by(Lead.source).all()
        
        source_data = []
        for source in sources:
            conversion_rate = (source.conversions / source.total_leads * 100) if source.total_leads > 0 else 0
            
            source_data.append({
                "source": source.source or "Unknown",
                "total_leads": source.total_leads,
                "avg_score": round(source.avg_score or 0, 2),
                "conversions": source.conversions,
                "conversion_rate": round(conversion_rate, 2),
                "quality_score": self._calculate_source_quality(source.avg_score, conversion_rate)
            })
        
        return sorted(source_data, key=lambda x: x["quality_score"], reverse=True)
    
    def _calculate_source_quality(self, avg_score: float, conversion_rate: float) -> float:
        """Calcula un score de calidad para la fuente"""
        return (avg_score * 0.7 + conversion_rate * 0.3) if avg_score else 0
    
    async def _get_score_distribution(self, db: Session) -> Dict:
        """Distribución de scores de leads activos"""
        
        score_ranges = [
            ("0-20", 0, 20),
            ("21-40", 21, 40), 
            ("41-60", 41, 60),
            ("61-80", 61, 80),
            ("81-100", 81, 100)
        ]
        
        distribution = {}
        
        for range_name, min_score, max_score in score_ranges:
            count = db.query(Lead).filter(
                and_(
                    Lead.score >= min_score,
                    Lead.score <= max_score,
                    Lead.is_active == True
                )
            ).count()
            
            distribution[range_name] = count
        
        return distribution
    
    async def _get_hubspot_sync_metrics(self, db: Session) -> Dict:
        """Métricas de sincronización con HubSpot"""
        
        total_leads = db.query(Lead).count()
        synced_leads = db.query(Lead).filter(Lead.hubspot_id.isnot(None)).count()
        
        # Últimas sincronizaciones exitosas
        recent_syncs = db.query(Lead).filter(
            and_(
                Lead.hubspot_id.isnot(None),
                Lead.updated_at >= datetime.now() - timedelta(hours=24)
            )
        ).count()
        
        return {
            "total_leads": total_leads,
            "synced_leads": synced_leads,
            "sync_percentage": (synced_leads / total_leads * 100) if total_leads > 0 else 0,
            "recent_syncs_24h": recent_syncs,
            "sync_health": "Healthy" if (synced_leads / total_leads) > 0.9 else "Needs Attention"
        }
    
    async def _get_interaction_analytics(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Analytics de interacciones del chatbot"""
        
        interactions = db.query(Interaction).filter(
            and_(Interaction.timestamp >= start_date, Interaction.timestamp <= end_date)
        )
        
        total_interactions = interactions.count()
        
        # Por tipo
        by_type = db.query(
            Interaction.type,
            func.count(Interaction.id).label('count')
        ).filter(
            and_(Interaction.timestamp >= start_date, Interaction.timestamp <= end_date)
        ).group_by(Interaction.type).all()
        
        # Sentiment promedio
        avg_sentiment = db.query(
            func.avg(Interaction.sentiment_score)
        ).filter(
            and_(
                Interaction.timestamp >= start_date, 
                Interaction.timestamp <= end_date,
                Interaction.sentiment_score.isnot(None)
            )
        ).scalar()
        
        return {
            "total_interactions": total_interactions,
            "by_type": {interaction.type: interaction.count for interaction in by_type},
            "average_sentiment": round(avg_sentiment or 0, 2),
            "interactions_per_day": total_interactions / ((end_date - start_date).days or 1)
        }
    
    async def _get_revenue_forecast(self, db: Session) -> Dict:
        """Forecast de ingresos basado en pipeline"""
        
        hot_leads = db.query(Lead).filter(Lead.status == 'hot').count()
        warm_leads = db.query(Lead).filter(Lead.status == 'warm').count()
        
        # Valores promedio estimados (estos deberían venir de configuración)
        avg_deal_value = 5000  # USD
        hot_conversion_rate = 0.6
        warm_conversion_rate = 0.3
        
        forecasted_revenue = (
            hot_leads * avg_deal_value * hot_conversion_rate +
            warm_leads * avg_deal_value * warm_conversion_rate
        )
        
        return {
            "hot_leads": hot_leads,
            "warm_leads": warm_leads,
            "avg_deal_value": avg_deal_value,
            "forecasted_revenue": forecasted_revenue,
            "confidence_level": "Medium",
            "time_horizon": "Next 30 days"
        }

# Frontend Component para Dashboard
async def get_dashboard_component() -> str:
    """Retorna HTML para el dashboard de analytics"""
    
    return """
    <div id="hubspot-analytics-dashboard">
        <div class="dashboard-header">
            <h1>HubSpot Analytics Dashboard</h1>
            <div class="last-updated" id="last-updated"></div>
        </div>
        
        <div class="metrics-grid">
            <!-- Lead Metrics -->
            <div class="metric-card">
                <h3>Lead Metrics</h3>
                <div id="lead-metrics"></div>
            </div>
            
            <!-- Conversion Funnel -->
            <div class="metric-card">
                <h3>Conversion Funnel</h3>
                <div id="conversion-funnel"></div>
            </div>
            
            <!-- Source Performance -->
            <div class="metric-card">
                <h3>Source Performance</h3>
                <div id="source-performance"></div>
            </div>
            
            <!-- Score Distribution -->
            <div class="metric-card">
                <h3>Score Distribution</h3>
                <div id="score-distribution"></div>
            </div>
            
            <!-- Sync Metrics -->
            <div class="metric-card">
                <h3>HubSpot Sync Status</h3>
                <div id="sync-metrics"></div>
            </div>
            
            <!-- Revenue Forecast -->
            <div class="metric-card">
                <h3>Revenue Forecast</h3>
                <div id="revenue-forecast"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Auto-refresh dashboard every 5 minutes
        setInterval(refreshDashboard, 300000);
        
        async function refreshDashboard() {
            try {
                const response = await fetch('/api/analytics/dashboard');
                const data = await response.json();
                updateDashboardElements(data);
            } catch (error) {
                console.error('Error refreshing dashboard:', error);
            }
        }
        
        function updateDashboardElements(data) {
            // Update cada sección del dashboard
            document.getElementById('last-updated').textContent = 
                `Last updated: ${new Date(data.last_updated).toLocaleString()}`;
            
            // Actualizar métricas (implementar según necesidad)
        }
        
        // Initial load
        refreshDashboard();
    </script>
    """