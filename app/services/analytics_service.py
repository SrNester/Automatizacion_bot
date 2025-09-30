import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, text
import logging
from ..models.integration import Lead, LeadStatus
from ..models.interaction import Interaction, ConversationSummary, MessageType, Platform
from ..core.database import get_db
from .integrations.hubspot_service import HubSpotService

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self):
        self.hubspot = HubSpotService()
        self.cache = {}
        self.cache_ttl = 300  # 5 minutos
    
    async def get_real_time_dashboard_data(self, db: Session, days: int = 30) -> Dict:
        """Obtiene datos del dashboard en tiempo real con cache"""
        
        cache_key = f"dashboard_{days}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                logger.info("Returning cached dashboard data")
                return cached_data
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            # Ejecutar todas las consultas en paralelo
            tasks = [
                self._get_lead_metrics(db, start_date, end_date),
                self._get_conversion_funnel(db, start_date, end_date),
                self._get_source_performance(db, start_date, end_date),
                self._get_score_distribution(db),
                self._get_hubspot_sync_metrics(db),
                self._get_interaction_analytics(db, start_date, end_date),
                self._get_revenue_forecast(db),
                self._get_engagement_metrics(db, start_date, end_date),
                self._get_performance_trends(db, start_date, end_date)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verificar errores en los resultados
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in task {i}: {result}")
                    processed_results.append({})  # Datos vacíos en caso de error
                else:
                    processed_results.append(result)
            
            dashboard_data = {
                "lead_metrics": processed_results[0],
                "conversion_funnel": processed_results[1], 
                "source_performance": processed_results[2],
                "score_distribution": processed_results[3],
                "sync_metrics": processed_results[4],
                "interaction_analytics": processed_results[5],
                "revenue_forecast": processed_results[6],
                "engagement_metrics": processed_results[7],
                "performance_trends": processed_results[8],
                "last_updated": datetime.now().isoformat(),
                "time_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                }
            }
            
            # Actualizar cache
            self.cache[cache_key] = (dashboard_data, datetime.now())
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error generating dashboard data: {e}")
            return self._get_error_dashboard()
    
    async def _get_lead_metrics(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Métricas básicas de leads con comparativas"""
        
        try:
            # Métricas del período actual
            current_leads = db.query(Lead).filter(
                and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
            )
            
            total_leads = current_leads.count()
            
            qualified_leads = current_leads.filter(Lead.is_qualified == True).count()
            
            hot_leads = current_leads.filter(Lead.status == LeadStatus.HOT.value).count()
            
            converted_leads = current_leads.filter(Lead.status == LeadStatus.CONVERTED.value).count()
            
            # Leads por status
            status_counts = db.query(
                Lead.status,
                func.count(Lead.id).label('count')
            ).filter(
                and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
            ).group_by(Lead.status).all()
            
            status_distribution = {status: count for status, count in status_counts}
            
            # Comparación con período anterior
            prev_start = start_date - timedelta(days=(end_date - start_date).days)
            prev_end = start_date
            
            prev_total = db.query(Lead).filter(
                and_(Lead.created_at >= prev_start, Lead.created_at < prev_end)
            ).count()
            
            growth_rate = ((total_leads - prev_total) / prev_total * 100) if prev_total > 0 else 0
            
            # Tendencias semanales
            weekly_trend = await self._get_weekly_trend(db, start_date, end_date)
            
            return {
                "total_leads": total_leads,
                "qualified_leads": qualified_leads,
                "hot_leads": hot_leads,
                "converted_leads": converted_leads,
                "status_distribution": status_distribution,
                "qualification_rate": (qualified_leads / total_leads * 100) if total_leads > 0 else 0,
                "conversion_rate": (converted_leads / total_leads * 100) if total_leads > 0 else 0,
                "growth_rate": round(growth_rate, 2),
                "weekly_trend": weekly_trend,
                "avg_lead_score": db.query(func.avg(Lead.score)).filter(
                    and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
                ).scalar() or 0
            }
            
        except Exception as e:
            logger.error(f"Error in lead metrics: {e}")
            return {}
    
    async def _get_conversion_funnel(self, db: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Análisis del embudo de conversación mejorado"""
        
        try:
            funnel_stages = [
                {"name": "Visitantes", "filter": "website_visit", "description": "Interacciones iniciales"},
                {"name": "Leads Capturados", "filter": "lead_captured", "description": "Formularios completados"},
                {"name": "Leads Calificados", "filter": "qualified", "description": "Leads cualificados"},
                {"name": "Demos Solicitadas", "filter": "demo_requested", "description": "Solicitudes de demo"},
                {"name": "Propuestas Enviadas", "filter": "proposal_sent", "description": "Propuestas enviadas"},
                {"name": "Clientes Convertidos", "filter": "converted", "description": "Conversiones finales"}
            ]
            
            funnel_data = []
            previous_count = 0
            
            for i, stage in enumerate(funnel_stages):
                if stage["filter"] in ["qualified", "converted"]:
                    # Para stages basados en Lead status
                    count = db.query(Lead).filter(
                        and_(
                            Lead.created_at >= start_date,
                            Lead.created_at <= end_date,
                            Lead.status == stage["filter"].upper()
                        )
                    ).count()
                else:
                    # Para stages basados en Interaction type
                    count = db.query(Interaction).filter(
                        and_(
                            Interaction.created_at >= start_date,
                            Interaction.created_at <= end_date,
                            Interaction.intent_detected == stage["filter"]
                        )
                    ).count()
                
                dropoff = 0
                if i > 0 and previous_count > 0:
                    dropoff = ((previous_count - count) / previous_count * 100)
                
                funnel_data.append({
                    "stage": stage["name"],
                    "stage_key": stage["filter"],
                    "description": stage["description"],
                    "count": count,
                    "dropoff_rate": round(dropoff, 2),
                    "conversion_rate": 0  # Se calculará después
                })
                
                previous_count = count
            
            # Calcular tasas de conversión desde el inicio
            if funnel_data and funnel_data[0]["count"] > 0:
                base_count = funnel_data[0]["count"]
                for stage in funnel_data:
                    stage["conversion_rate"] = round((stage["count"] / base_count * 100), 2)
            
            return funnel_data
            
        except Exception as e:
            logger.error(f"Error in conversion funnel: {e}")
            return []
    
    async def _get_source_performance(self, db: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Performance por fuente de lead con análisis avanzado"""
        
        try:
            sources = db.query(
                Lead.source,
                func.count(Lead.id).label('total_leads'),
                func.avg(Lead.score).label('avg_score'),
                func.sum(case([(Lead.status == LeadStatus.CONVERTED.value, 1)], else_=0)).label('conversions'),
                func.avg(case([(Lead.is_qualified == True, 1)], else_=0)).label('qualification_rate')
            ).filter(
                and_(Lead.created_at >= start_date, Lead.created_at <= end_date),
                Lead.source.isnot(None)
            ).group_by(Lead.source).all()
            
            source_data = []
            for source in sources:
                conversion_rate = (source.conversions / source.total_leads * 100) if source.total_leads > 0 else 0
                qualification_rate = (source.qualification_rate * 100) if source.total_leads > 0 else 0
                
                source_data.append({
                    "source": source.source or "Unknown",
                    "total_leads": source.total_leads,
                    "avg_score": round(float(source.avg_score or 0), 2),
                    "conversions": source.conversions,
                    "conversion_rate": round(conversion_rate, 2),
                    "qualification_rate": round(qualification_rate, 2),
                    "quality_score": self._calculate_source_quality(
                        float(source.avg_score or 0), 
                        conversion_rate,
                        qualification_rate
                    ),
                    "cost_per_lead": self._estimate_cost_per_lead(source.source)
                })
            
            return sorted(source_data, key=lambda x: x["quality_score"], reverse=True)
            
        except Exception as e:
            logger.error(f"Error in source performance: {e}")
            return []
    
    def _calculate_source_quality(self, avg_score: float, conversion_rate: float, qualification_rate: float) -> float:
        """Calcula un score de calidad compuesto para la fuente"""
        score_components = [
            (avg_score / 100 * 0.4),           # Peso 40% al score promedio
            (conversion_rate / 100 * 0.3),     # Peso 30% a tasa de conversión
            (qualification_rate / 100 * 0.3)   # Peso 30% a tasa de calificación
        ]
        
        return round(sum(score_components) * 100, 2)
    
    def _estimate_cost_per_lead(self, source: str) -> float:
        """Estima costo por lead basado en la fuente"""
        cost_estimates = {
            "organic": 0,
            "referral": 50,
            "social_media": 75,
            "paid_ads": 150,
            "events": 200,
            "cold_outreach": 100
        }
        
        return cost_estimates.get(source, 100)
    
    async def _get_score_distribution(self, db: Session) -> Dict:
        """Distribución de scores de leads activos con análisis"""
        
        try:
            score_ranges = [
                ("0-20", 0, 20, "Muy Bajo"),
                ("21-40", 21, 40, "Bajo"), 
                ("41-60", 41, 60, "Medio"),
                ("61-80", 61, 80, "Alto"),
                ("81-100", 81, 100, "Muy Alto")
            ]
            
            distribution = {}
            total_active_leads = db.query(Lead).filter(Lead.is_active == True).count()
            
            for range_name, min_score, max_score, label in score_ranges:
                count = db.query(Lead).filter(
                    and_(
                        Lead.score >= min_score,
                        Lead.score <= max_score,
                        Lead.is_active == True
                    )
                ).count()
                
                percentage = (count / total_active_leads * 100) if total_active_leads > 0 else 0
                
                distribution[range_name] = {
                    "count": count,
                    "percentage": round(percentage, 2),
                    "label": label
                }
            
            # Score promedio y mediano
            avg_score = db.query(func.avg(Lead.score)).filter(Lead.is_active == True).scalar() or 0
            median_score = self._calculate_median_score(db)
            
            return {
                "distribution": distribution,
                "total_active_leads": total_active_leads,
                "average_score": round(float(avg_score), 2),
                "median_score": median_score,
                "score_health": self._assess_score_health(distribution)
            }
            
        except Exception as e:
            logger.error(f"Error in score distribution: {e}")
            return {}
    
    def _calculate_median_score(self, db: Session) -> float:
        """Calcula el score mediano de los leads activos"""
        try:
            # Consulta para obtener scores ordenados
            scores = db.query(Lead.score).filter(
                Lead.is_active == True,
                Lead.score.isnot(None)
            ).order_by(Lead.score).all()
            
            scores = [score[0] for score in scores]
            
            if not scores:
                return 0.0
            
            n = len(scores)
            mid = n // 2
            
            if n % 2 == 0:
                return (scores[mid - 1] + scores[mid]) / 2
            else:
                return float(scores[mid])
                
        except Exception as e:
            logger.error(f"Error calculating median score: {e}")
            return 0.0
    
    def _assess_score_health(self, distribution: Dict) -> str:
        """Evalúa la salud general de los scores"""
        high_quality = distribution.get("81-100", {}).get("percentage", 0)
        low_quality = distribution.get("0-20", {}).get("percentage", 0)
        
        if high_quality > 30:
            return "Excelente"
        elif high_quality > 20:
            return "Buena"
        elif low_quality > 40:
            return "Necesita Mejora"
        else:
            return "Normal"
    
    async def _get_hubspot_sync_metrics(self, db: Session) -> Dict:
        """Métricas de sincronización con HubSpot mejoradas"""
        
        try:
            total_leads = db.query(Lead).count()
            synced_leads = db.query(Lead).filter(Lead.hubspot_id.isnot(None)).count()
            
            # Últimas sincronizaciones (24 horas)
            recent_syncs = db.query(Lead).filter(
                and_(
                    Lead.hubspot_id.isnot(None),
                    Lead.updated_at >= datetime.now() - timedelta(hours=24)
                )
            ).count()
            
            # Leads que necesitan sync
            needs_sync = db.query(Lead).filter(
                and_(
                    Lead.hubspot_id.is_(None),
                    Lead.updated_at >= datetime.now() - timedelta(hours=24)
                )
            ).count()
            
            sync_percentage = (synced_leads / total_leads * 100) if total_leads > 0 else 0
            
            return {
                "total_leads": total_leads,
                "synced_leads": synced_leads,
                "sync_percentage": round(sync_percentage, 2),
                "recent_syncs_24h": recent_syncs,
                "needs_sync": needs_sync,
                "sync_health": "Healthy" if sync_percentage > 90 else "Needs Attention",
                "last_sync_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in HubSpot sync metrics: {e}")
            return {}
    
    async def _get_interaction_analytics(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Analytics de interacciones del chatbot mejorado"""
        
        try:
            # Métricas básicas
            total_interactions = db.query(Interaction).filter(
                and_(Interaction.created_at >= start_date, Interaction.created_at <= end_date)
            ).count()
            
            # Por tipo de mensaje
            by_type = db.query(
                Interaction.user_message_type,
                func.count(Interaction.id).label('count')
            ).filter(
                and_(Interaction.created_at >= start_date, Interaction.created_at <= end_date)
            ).group_by(Interaction.user_message_type).all()
            
            # Por plataforma
            by_platform = db.query(
                Interaction.platform,
                func.count(Interaction.id).label('count')
            ).filter(
                and_(Interaction.created_at >= start_date, Interaction.created_at <= end_date)
            ).group_by(Interaction.platform).all()
            
            # Sentiment analysis
            sentiment_stats = db.query(
                func.avg(Interaction.sentiment_score).label('avg_sentiment'),
                func.count(Interaction.id).label('total_with_sentiment')
            ).filter(
                and_(
                    Interaction.created_at >= start_date, 
                    Interaction.created_at <= end_date,
                    Interaction.sentiment_score.isnot(None)
                )
            ).first()
            
            # Intención más común
            top_intent = db.query(
                Interaction.intent_detected,
                func.count(Interaction.id).label('count')
            ).filter(
                and_(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date,
                    Interaction.intent_detected.isnot(None)
                )
            ).group_by(Interaction.intent_detected).order_by(func.count(Interaction.id).desc()).first()
            
            return {
                "total_interactions": total_interactions,
                "interactions_per_day": round(total_interactions / max((end_date - start_date).days, 1), 2),
                "by_message_type": {msg_type: count for msg_type, count in by_type},
                "by_platform": {platform: count for platform, count in by_platform},
                "sentiment_analysis": {
                    "average_sentiment": round(float(sentiment_stats.avg_sentiment or 0), 2),
                    "total_analyzed": sentiment_stats.total_with_sentiment,
                    "positive_rate": self._calculate_positive_sentiment_rate(db, start_date, end_date)
                },
                "top_intent": top_intent[0] if top_intent else "N/A",
                "top_intent_count": top_intent[1] if top_intent else 0,
                "escalation_rate": self._calculate_escalation_rate(db, start_date, end_date)
            }
            
        except Exception as e:
            logger.error(f"Error in interaction analytics: {e}")
            return {}
    
    def _calculate_positive_sentiment_rate(self, db: Session, start_date: datetime, end_date: datetime) -> float:
        """Calcula el porcentaje de interacciones con sentiment positivo"""
        try:
            positive_count = db.query(Interaction).filter(
                and_(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date,
                    Interaction.sentiment_score > 0.3
                )
            ).count()
            
            total_with_sentiment = db.query(Interaction).filter(
                and_(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date,
                    Interaction.sentiment_score.isnot(None)
                )
            ).count()
            
            return round((positive_count / total_with_sentiment * 100) if total_with_sentiment > 0 else 0, 2)
        except Exception as e:
            logger.error(f"Error calculating positive sentiment rate: {e}")
            return 0.0
    
    def _calculate_escalation_rate(self, db: Session, start_date: datetime, end_date: datetime) -> float:
        """Calcula la tasa de escalación a humanos"""
        try:
            escalated_count = db.query(Interaction).filter(
                and_(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date,
                    Interaction.escalated_to_human == True
                )
            ).count()
            
            total_interactions = db.query(Interaction).filter(
                and_(Interaction.created_at >= start_date, Interaction.created_at <= end_date)
            ).count()
            
            return round((escalated_count / total_interactions * 100) if total_interactions > 0 else 0, 2)
        except Exception as e:
            logger.error(f"Error calculating escalation rate: {e}")
            return 0.0
    
    async def _get_revenue_forecast(self, db: Session) -> Dict:
        """Forecast de ingresos basado en pipeline mejorado"""
        
        try:
            # Configuración de valores por defecto (debería venir de DB)
            deal_config = {
                "hot_lead_value": 5000,
                "warm_lead_value": 2500,
                "hot_conversion_rate": 0.4,
                "warm_conversion_rate": 0.15,
                "sales_cycle_days": 30
            }
            
            # Contar leads por status
            hot_leads = db.query(Lead).filter(
                Lead.status == LeadStatus.HOT.value,
                Lead.is_active == True
            ).count()
            
            warm_leads = db.query(Lead).filter(
                Lead.status == LeadStatus.WARM.value,
                Lead.is_active == True
            ).count()
            
            # Calcular forecast
            hot_revenue = hot_leads * deal_config["hot_lead_value"] * deal_config["hot_conversion_rate"]
            warm_revenue = warm_leads * deal_config["warm_lead_value"] * deal_config["warm_conversion_rate"]
            total_forecast = hot_revenue + warm_revenue
            
            # Calcular confianza basada en datos históricos
            confidence_level = self._calculate_forecast_confidence(db, hot_leads + warm_leads)
            
            return {
                "hot_leads": hot_leads,
                "warm_leads": warm_leads,
                "deal_values": deal_config,
                "forecasted_revenue": round(total_forecast, 2),
                "confidence_level": confidence_level,
                "time_horizon": f"Next {deal_config['sales_cycle_days']} days",
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in revenue forecast: {e}")
            return {}
    
    def _calculate_forecast_confidence(self, db: Session, current_pipeline: int) -> str:
        """Calcula el nivel de confianza del forecast"""
        try:
            # Análisis histórico de accuracy
            historical_accuracy = 0.7  # Placeholder - debería venir de análisis real
            
            if current_pipeline > 50:
                base_confidence = "High"
            elif current_pipeline > 20:
                base_confidence = "Medium"
            else:
                base_confidence = "Low"
            
            # Ajustar por accuracy histórica
            if historical_accuracy > 0.8:
                return f"{base_confidence} (High Accuracy)"
            elif historical_accuracy > 0.6:
                return f"{base_confidence} (Medium Accuracy)"
            else:
                return f"{base_confidence} (Low Accuracy)"
                
        except Exception as e:
            logger.error(f"Error calculating forecast confidence: {e}")
            return "Unknown"
    
    async def _get_engagement_metrics(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Métricas de engagement de leads"""
        
        try:
            # Tiempo promedio de respuesta
            avg_response_time = db.query(
                func.avg(Interaction.response_time_ms)
            ).filter(
                and_(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date,
                    Interaction.response_time_ms.isnot(None),
                    Interaction.response_time_ms > 0
                )
            ).scalar() or 0
            
            # Engagement por lead
            engagement_by_lead = db.query(
                Interaction.lead_id,
                func.count(Interaction.id).label('interaction_count'),
                func.avg(Interaction.sentiment_score).label('avg_sentiment')
            ).filter(
                and_(Interaction.created_at >= start_date, Interaction.created_at <= end_date)
            ).group_by(Interaction.lead_id).all()
            
            avg_interactions_per_lead = (
                sum(lead.interaction_count for lead in engagement_by_lead) / len(engagement_by_lead)
                if engagement_by_lead else 0
            )
            
            return {
                "average_response_time_ms": round(float(avg_response_time), 2),
                "average_interactions_per_lead": round(avg_interactions_per_lead, 2),
                "highly_engaged_leads": len([l for l in engagement_by_lead if l.interaction_count > 5]),
                "total_leads_engaged": len(engagement_by_lead),
                "average_engagement_sentiment": round(
                    sum(lead.avg_sentiment or 0 for lead in engagement_by_lead) / len(engagement_by_lead), 2
                ) if engagement_by_lead else 0
            }
            
        except Exception as e:
            logger.error(f"Error in engagement metrics: {e}")
            return {}
    
    async def _get_performance_trends(self, db: Session, start_date: datetime, end_date: datetime) -> Dict:
        """Tendencias de performance over time"""
        
        try:
            # Leads por día
            daily_leads = db.query(
                func.date(Lead.created_at).label('date'),
                func.count(Lead.id).label('count')
            ).filter(
                and_(Lead.created_at >= start_date, Lead.created_at <= end_date)
            ).group_by(func.date(Lead.created_at)).order_by('date').all()
            
            # Conversiones por día
            daily_conversions = db.query(
                func.date(Lead.updated_at).label('date'),
                func.count(Lead.id).label('count')
            ).filter(
                and_(
                    Lead.updated_at >= start_date,
                    Lead.updated_at <= end_date,
                    Lead.status == LeadStatus.CONVERTED.value
                )
            ).group_by(func.date(Lead.updated_at)).order_by('date').all()
            
            return {
                "daily_leads": [{"date": lead.date.isoformat(), "count": lead.count} for lead in daily_leads],
                "daily_conversions": [{"date": conv.date.isoformat(), "count": conv.count} for conv in daily_conversions],
                "trend_period": f"{start_date.date()} to {end_date.date()}"
            }
            
        except Exception as e:
            logger.error(f"Error in performance trends: {e}")
            return {}
    
    async def _get_weekly_trend(self, db: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Tendencia semanal de leads"""
        try:
            weekly_data = db.query(
                func.year(Lead.created_at).label('year'),
                func.week(Lead.created_at).label('week'),
                func.count(Lead.id).label('lead_count')
            ).filter(
                and_(Lead.created_at >= start_date - timedelta(days=90), Lead.created_at <= end_date)
            ).group_by('year', 'week').order_by('year', 'week').all()
            
            return [
                {
                    "year": data.year,
                    "week": data.week,
                    "lead_count": data.lead_count,
                    "period": f"W{data.week}-{data.year}"
                }
                for data in weekly_data[-8:]  # Últimas 8 semanas
            ]
        except Exception as e:
            logger.error(f"Error in weekly trend: {e}")
            return []
    
    def _get_error_dashboard(self) -> Dict:
        """Dashboard de error cuando hay problemas"""
        return {
            "error": True,
            "message": "Error generating dashboard data",
            "last_updated": datetime.now().isoformat(),
            "lead_metrics": {},
            "conversion_funnel": [],
            "source_performance": [],
            "score_distribution": {},
            "sync_metrics": {},
            "interaction_analytics": {},
            "revenue_forecast": {},
            "engagement_metrics": {},
            "performance_trends": {}
        }
    
    def clear_cache(self):
        """Limpia la cache del servicio"""
        self.cache.clear()
        logger.info("Analytics cache cleared")

# Función de utilidad para crear instancia
def create_analytics_service() -> AnalyticsService:
    return AnalyticsService()