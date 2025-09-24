from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, between, case, text
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging

# Importar modelos correctos
from ...models.integration import Lead, LeadStatus, ExternalLead
from ...models.interaction import Interaction, ConversationSummary
from ...models.workflow import WorkflowExecution, EmailSend
from ...models.campaign import Campaign, CampaignLead

logger = logging.getLogger(__name__)

class DataAggregator:
    """Servicio para agregación y transformación de datos analíticos"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.supported_granularities = ['hourly', 'daily', 'weekly', 'monthly']
    
    async def aggregate_lead_metrics_by_time(self, days: int, 
                                           granularity: str = 'daily') -> pd.DataFrame:
        """Agrega métricas de leads por período de tiempo"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Determinar la expresión de tiempo según granularidad
            time_expr = self._get_time_expression(granularity)
            
            stmt = select([
                time_expr.label('period'),
                func.count(Lead.id).label('total_leads'),
                func.avg(Lead.score).label('avg_score'),
                func.sum(case((Lead.is_qualified == True, 1), else_=0)).label('qualified_leads'),
                func.sum(case((Lead.status == LeadStatus.CONVERTED, 1), else_=0)).label('converted_leads'),
                func.count(case((Lead.source.isnot(None), 1))).label('leads_with_source')
            ]).where(
                Lead.created_at >= start_date
            ).group_by('period').order_by('period')
            
            result = await self.db.execute(stmt)
            data = [dict(row) for row in result]
            
            df = pd.DataFrame(data)
            if not df.empty:
                # Calcular métricas derivadas
                df['conversion_rate'] = (df['converted_leads'] / df['total_leads'] * 100).fillna(0)
                df['qualification_rate'] = (df['qualified_leads'] / df['total_leads'] * 100).fillna(0)
                df['avg_score'] = df['avg_score'].fillna(0)
                
                # Redondear valores
                df['conversion_rate'] = df['conversion_rate'].round(2)
                df['qualification_rate'] = df['qualification_rate'].round(2)
                df['avg_score'] = df['avg_score'].round(2)
            
            logger.info(f"Aggregated lead metrics for {days} days with {granularity} granularity")
            return df
            
        except Exception as e:
            logger.error(f"Error aggregating lead metrics: {e}")
            return pd.DataFrame()
    
    async def get_lead_source_attribution(self, days: int) -> Dict[str, Any]:
        """Calcula atribución de leads por fuente"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = select([
                Lead.source,
                func.count(Lead.id).label('lead_count'),
                func.avg(Lead.score).label('avg_score'),
                func.sum(case((Lead.is_qualified == True, 1), else_=0)).label('qualified_count'),
                func.sum(case((Lead.status == LeadStatus.CONVERTED, 1), else_=0)).label('converted_count'),
                func.avg(case((Lead.score.isnot(None), Lead.score), else_=0)).label('avg_quality_score')
            ]).where(
                Lead.created_at >= start_date
            ).group_by(Lead.source)
            
            result = await self.db.execute(stmt)
            
            attribution_data = {}
            total_leads = 0
            total_converted = 0
            
            for source, count, avg_score, qualified, converted, avg_quality in result:
                source_key = source or 'unknown'
                conversion_rate = (converted / count * 100) if count > 0 else 0
                
                attribution_data[source_key] = {
                    'lead_count': count,
                    'avg_score': float(avg_score or 0),
                    'avg_quality_score': float(avg_quality or 0),
                    'qualified_count': qualified,
                    'converted_count': converted,
                    'conversion_rate': round(conversion_rate, 2),
                    'market_share': 0  # Se calculará después
                }
                
                total_leads += count
                total_converted += converted
            
            # Calcular market share para cada fuente
            for source_data in attribution_data.values():
                if total_leads > 0:
                    source_data['market_share'] = round((source_data['lead_count'] / total_leads * 100), 2)
            
            # Ordenar por lead_count descendente
            sorted_attribution = dict(sorted(
                attribution_data.items(), 
                key=lambda x: x[1]['lead_count'], 
                reverse=True
            ))
            
            return {
                'period_days': days,
                'total_leads': total_leads,
                'total_converted': total_converted,
                'overall_conversion_rate': round((total_converted / total_leads * 100), 2) if total_leads > 0 else 0,
                'sources': sorted_attribution,
                'top_source': list(sorted_attribution.keys())[0] if sorted_attribution else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating lead source attribution: {e}")
            return {'error': str(e), 'sources': {}}
    
    async def aggregate_interaction_metrics(self, days: int) -> Dict[str, Any]:
        """Agrega métricas de interacciones y conversaciones"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Métricas básicas de interacciones
            interaction_stats = await self.db.execute(select([
                func.count(Interaction.id).label('total_interactions'),
                func.avg(Interaction.response_time_ms).label('avg_response_time_ms'),
                func.avg(Interaction.sentiment_score).label('avg_sentiment'),
                func.count(func.distinct(Interaction.conversation_id)).label('unique_conversations'),
                func.count(func.distinct(Interaction.lead_id)).label('leads_with_interactions')
            ]).where(Interaction.created_at >= start_date))
            
            total, avg_response, avg_sentiment, unique_conv, leads_with_interactions = interaction_stats.first() or (0, 0, 0, 0, 0)
            
            # Intents más comunes
            top_intents = await self.db.execute(select([
                Interaction.intent_detected,
                func.count(Interaction.id).label('count')
            ]).where(
                Interaction.created_at >= start_date,
                Interaction.intent_detected.isnot(None)
            ).group_by(Interaction.intent_detected).order_by(func.count(Interaction.id).desc()).limit(10))
            
            # Plataformas más utilizadas
            platform_stats = await self.db.execute(select([
                Interaction.platform,
                func.count(Interaction.id).label('count'),
                func.avg(Interaction.response_time_ms).label('avg_response_time')
            ]).where(
                Interaction.created_at >= start_date,
                Interaction.platform.isnot(None)
            ).group_by(Interaction.platform).order_by(func.count(Interaction.id).desc()))
            
            return {
                'period_days': days,
                'summary': {
                    'total_interactions': total or 0,
                    'avg_response_time_minutes': round((avg_response or 0) / 60000, 2),
                    'avg_sentiment': round(float(avg_sentiment or 0), 2),
                    'unique_conversations': unique_conv or 0,
                    'leads_with_interactions': leads_with_interactions or 0,
                    'avg_interactions_per_lead': round((total or 0) / (leads_with_interactions or 1), 2)
                },
                'top_intents': [
                    {'intent': intent, 'count': count} 
                    for intent, count in top_intents
                ],
                'platform_breakdown': [
                    {
                        'platform': platform, 
                        'count': count, 
                        'avg_response_minutes': round((avg_time or 0) / 60000, 2)
                    }
                    for platform, count, avg_time in platform_stats
                ],
                'hourly_distribution': await self._get_hourly_interaction_distribution(days)
            }
            
        except Exception as e:
            logger.error(f"Error aggregating interaction metrics: {e}")
            return {'error': str(e)}
    
    async def aggregate_workflow_metrics(self, days: int) -> Dict[str, Any]:
        """Agrega métricas de workflows y automatizaciones"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Estadísticas de workflows
            workflow_stats = await self.db.execute(select([
                func.count(WorkflowExecution.id).label('total_executions'),
                func.sum(case((WorkflowExecution.status == 'completed', 1), else_=0)).label('completed_executions'),
                func.sum(case((WorkflowExecution.status == 'failed', 1), else_=0)).label('failed_executions'),
                func.avg(WorkflowExecution.total_execution_time_minutes).label('avg_execution_time'),
                func.count(func.distinct(WorkflowExecution.workflow_id)).label('unique_workflows')
            ]).where(WorkflowExecution.started_at >= start_date))
            
            total, completed, failed, avg_time, unique_workflows = workflow_stats.first() or (0, 0, 0, 0, 0)
            
            # Métricas de emails
            email_stats = await self.db.execute(select([
                func.count(EmailSend.id).label('total_emails'),
                func.sum(case((EmailSend.status == 'delivered', 1), else_=0)).label('delivered_emails'),
                func.sum(case((EmailSend.status == 'opened', 1), else_=0)).label('opened_emails'),
                func.sum(case((EmailSend.status == 'clicked', 1), else_=0)).label('clicked_emails'),
                func.avg(EmailSend.open_count).label('avg_open_count')
            ]).where(EmailSend.created_at >= start_date))
            
            total_emails, delivered, opened, clicked, avg_opens = email_stats.first() or (0, 0, 0, 0, 0)
            
            return {
                'period_days': days,
                'workflow_performance': {
                    'total_executions': total,
                    'completed_executions': completed,
                    'failed_executions': failed,
                    'success_rate': round((completed / total * 100), 2) if total > 0 else 0,
                    'avg_execution_time_minutes': round(float(avg_time or 0), 2),
                    'unique_workflows': unique_workflows
                },
                'email_performance': {
                    'total_sent': total_emails,
                    'delivery_rate': round((delivered / total_emails * 100), 2) if total_emails > 0 else 0,
                    'open_rate': round((opened / delivered * 100), 2) if delivered > 0 else 0,
                    'click_rate': round((clicked / opened * 100), 2) if opened > 0 else 0,
                    'avg_opens_per_email': round(float(avg_opens or 0), 2)
                },
                'efficiency_metrics': await self._calculate_efficiency_metrics(days)
            }
            
        except Exception as e:
            logger.error(f"Error aggregating workflow metrics: {e}")
            return {'error': str(e)}
    
    async def aggregate_campaign_metrics(self, days: int) -> Dict[str, Any]:
        """Agrega métricas de campañas de marketing"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Estadísticas de campañas
            campaign_stats = await self.db.execute(select([
                func.count(Campaign.id).label('total_campaigns'),
                func.count(case((Campaign.status == 'active', 1))).label('active_campaigns'),
                func.count(case((Campaign.status == 'completed', 1))).label('completed_campaigns'),
                func.sum(Campaign.impressions).label('total_impressions'),
                func.sum(Campaign.clicks).label('total_clicks'),
                func.sum(Campaign.conversions).label('total_conversions'),
                func.sum(Campaign.revenue_generated).label('total_revenue')
            ]).where(Campaign.created_at >= start_date))
            
            total_campaigns, active, completed, impressions, clicks, conversions, revenue = campaign_stats.first() or (0, 0, 0, 0, 0, 0, 0)
            
            # Performance por tipo de campaña
            campaign_type_stats = await self.db.execute(select([
                Campaign.type,
                func.count(Campaign.id).label('count'),
                func.avg(Campaign.conversion_rate).label('avg_conversion_rate'),
                func.avg(Campaign.roi).label('avg_roi')
            ]).where(
                Campaign.created_at >= start_date,
                Campaign.status.in_(['completed', 'active'])
            ).group_by(Campaign.type))
            
            return {
                'period_days': days,
                'campaign_overview': {
                    'total_campaigns': total_campaigns,
                    'active_campaigns': active,
                    'completed_campaigns': completed,
                    'total_impressions': impressions,
                    'total_clicks': clicks,
                    'total_conversions': conversions,
                    'total_revenue': round(float(revenue or 0), 2),
                    'overall_ctr': round((clicks / impressions * 100), 2) if impressions > 0 else 0,
                    'overall_conversion_rate': round((conversions / clicks * 100), 2) if clicks > 0 else 0
                },
                'performance_by_type': [
                    {
                        'type': camp_type,
                        'count': count,
                        'avg_conversion_rate': round(float(avg_conv or 0), 2),
                        'avg_roi': round(float(avg_roi or 0), 2)
                    }
                    for camp_type, count, avg_conv, avg_roi in campaign_type_stats
                ],
                'top_performing_campaigns': await self._get_top_campaigns(days, limit=5)
            }
            
        except Exception as e:
            logger.error(f"Error aggregating campaign metrics: {e}")
            return {'error': str(e)}
    
    async def calculate_roi_metrics(self, days: int) -> Dict[str, float]:
        """Calcula métricas de ROI (versión mejorada con datos reales)"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Obtener datos reales de ingresos y costos
            revenue_data = await self.db.execute(select([
                func.sum(Campaign.revenue_generated).label('total_revenue')
            ]).where(
                Campaign.created_at >= start_date,
                Campaign.status == 'completed'
            ))
            
            total_revenue = revenue_data.scalar() or 0
            
            # Calcular costos (esto podría venir de integraciones con plataformas de ads)
            # Por ahora usamos un estimado basado en campañas
            cost_data = await self.db.execute(select([
                func.sum(Campaign.budget).label('total_cost')
            ]).where(
                Campaign.created_at >= start_date
            ))
            
            total_cost = cost_data.scalar() or 0
            
            # Métricas de leads para cálculos adicionales
            lead_count = await self.db.execute(select([
                func.count(Lead.id)
            ]).where(Lead.created_at >= start_date))
            
            total_leads = lead_count.scalar() or 0
            
            # Cálculos de ROI
            if total_cost > 0:
                roi = ((total_revenue - total_cost) / total_cost) * 100
                romi = (total_revenue / total_cost) * 100  # Return on Marketing Investment
            else:
                roi = 0
                romi = 0
            
            cost_per_lead = total_cost / total_leads if total_leads > 0 else 0
            revenue_per_lead = total_revenue / total_leads if total_leads > 0 else 0
            
            return {
                "total_revenue": round(float(total_revenue), 2),
                "total_cost": round(float(total_cost), 2),
                "roi_percentage": round(float(roi), 2),
                "romi_percentage": round(float(romi), 2),
                "cost_per_lead": round(float(cost_per_lead), 2),
                "revenue_per_lead": round(float(revenue_per_lead), 2),
                "total_leads": total_leads,
                "net_profit": round(float(total_revenue - total_cost), 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating ROI metrics: {e}")
            return {"error": str(e)}
    
    async def get_trend_analysis(self, metric: str, days: int, granularity: str = 'daily') -> Dict[str, Any]:
        """Analiza tendencias para una métrica específica"""
        
        try:
            # Obtener datos históricos
            if metric == 'leads':
                df = await self.aggregate_lead_metrics_by_time(days * 2, granularity)
                value_col = 'total_leads'
            elif metric == 'conversions':
                df = await self.aggregate_lead_metrics_by_time(days * 2, granularity)
                value_col = 'converted_leads'
            else:
                return {'error': f'Unsupported metric: {metric}'}
            
            if df.empty:
                return {'error': 'No data available for trend analysis'}
            
            # Calcular tendencia usando regresión lineal simple
            recent_data = df.tail(days)
            if len(recent_data) < 2:
                return {'error': 'Insufficient data for trend analysis'}
            
            X = np.array(range(len(recent_data))).reshape(-1, 1)
            y = recent_data[value_col].values
            
            # Modelo de tendencia lineal
            slope = self._calculate_slope(X, y)
            trend_direction = 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
            
            # Calcular cambio porcentual
            first_value = recent_data[value_col].iloc[0]
            last_value = recent_data[value_col].iloc[-1]
            percent_change = ((last_value - first_value) / first_value * 100) if first_value > 0 else 0
            
            return {
                'metric': metric,
                'period_days': days,
                'granularity': granularity,
                'current_value': last_value,
                'trend_direction': trend_direction,
                'trend_strength': abs(slope),
                'percent_change': round(percent_change, 2),
                'data_points': len(recent_data),
                'forecast': await self._generate_forecast(df, value_col, periods=7)
            }
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            return {'error': str(e)}
    
    # Métodos auxiliares privados
    
    def _get_time_expression(self, granularity: str):
        """Obtiene expresión SQL para agregación temporal"""
        from sqlalchemy import date_trunc
        
        if granularity == 'hourly':
            return date_trunc('hour', Lead.created_at)
        elif granularity == 'daily':
            return date_trunc('day', Lead.created_at)
        elif granularity == 'weekly':
            return date_trunc('week', Lead.created_at)
        elif granularity == 'monthly':
            return date_trunc('month', Lead.created_at)
        else:
            return date_trunc('day', Lead.created_at)
    
    async def _get_hourly_interaction_distribution(self, days: int) -> List[Dict]:
        """Obtiene distribución horaria de interacciones"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Usar expresión SQL para extraer la hora
        stmt = text("""
            SELECT EXTRACT(HOUR FROM created_at) as hour, 
                   COUNT(*) as interaction_count
            FROM interactions 
            WHERE created_at >= :start_date
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
        """)
        
        result = await self.db.execute(stmt, {'start_date': start_date})
        
        distribution = []
        for hour, count in result:
            distribution.append({
                'hour': int(hour),
                'interaction_count': count,
                'hour_label': f"{int(hour):02d}:00"
            })
        
        return distribution
    
    async def _calculate_efficiency_metrics(self, days: int) -> Dict[str, float]:
        """Calcula métricas de eficiencia del sistema"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Tiempo promedio desde lead creation hasta primera interacción
        response_time_stmt = text("""
            SELECT AVG(EXTRACT(EPOCH FROM (i.created_at - l.created_at)) / 3600) as avg_hours_to_first_response
            FROM interactions i
            JOIN leads l ON i.lead_id = l.id
            WHERE i.created_at >= :start_date
            AND i.created_at = (
                SELECT MIN(i2.created_at) 
                FROM interactions i2 
                WHERE i2.lead_id = l.id
            )
        """)
        
        result = await self.db.execute(response_time_stmt, {'start_date': start_date})
        avg_hours_to_response = result.scalar() or 0
        
        # Tasa de resolución en primera interacción
        resolution_stmt = select([
            func.count(Interaction.id).label('total_interactions'),
            func.count(case((
                and_(
                    Interaction.conversation_status == 'closed',
                    Interaction.escalated_to_human == False
                ), 1
            ))).label('resolved_first_interaction')
        ]).where(Interaction.created_at >= start_date)
        
        resolution_result = await self.db.execute(resolution_stmt)
        total_interactions, resolved_first = resolution_result.first() or (0, 0)
        
        first_contact_resolution = (resolved_first / total_interactions * 100) if total_interactions > 0 else 0
        
        return {
            'avg_hours_to_first_response': round(float(avg_hours_to_response), 2),
            'first_contact_resolution_rate': round(float(first_contact_resolution), 2),
            'automation_efficiency': await self._calculate_automation_efficiency(days)
        }
    
    async def _calculate_automation_efficiency(self, days: int) -> float:
        """Calcula eficiencia de automatización"""
        # Esta métrica podría basarse en la reducción de tiempo manual
        # vs procesos automatizados. Por ahora retornamos un placeholder.
        return 85.5  # Placeholder - implementar lógica real
    
    async def _get_top_campaigns(self, days: int, limit: int = 5) -> List[Dict]:
        """Obtiene las campañas con mejor performance"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select([
            Campaign.id,
            Campaign.name,
            Campaign.type,
            Campaign.conversion_rate,
            Campaign.roi,
            Campaign.clicks,
            Campaign.conversions
        ]).where(
            Campaign.created_at >= start_date,
            Campaign.status.in_(['completed', 'active'])
        ).order_by(Campaign.roi.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        
        top_campaigns = []
        for campaign_id, name, camp_type, conv_rate, roi, clicks, conversions in result:
            top_campaigns.append({
                'id': campaign_id,
                'name': name,
                'type': camp_type,
                'conversion_rate': round(float(conv_rate or 0), 2),
                'roi': round(float(roi or 0), 2),
                'clicks': clicks,
                'conversions': conversions
            })
        
        return top_campaigns
    
    def _calculate_slope(self, X: np.array, y: np.array) -> float:
        """Calcula la pendiente de una serie de datos usando mínimos cuadrados"""
        if len(X) < 2:
            return 0.0
        
        X_mean = np.mean(X)
        y_mean = np.mean(y)
        
        numerator = np.sum((X - X_mean) * (y - y_mean))
        denominator = np.sum((X - X_mean) ** 2)
        
        return numerator / denominator if denominator != 0 else 0.0
    
    async def _generate_forecast(self, df: pd.DataFrame, value_col: str, periods: int = 7) -> List[float]:
        """Genera forecast simple para una serie temporal"""
        
        if df.empty or len(df) < 2:
            return []
        
        # Usar promedio móvil simple para forecast
        values = df[value_col].values
        if len(values) >= 3:
            # Promedio móvil de 3 períodos
            forecast_values = []
            last_values = values[-3:]
            
            for i in range(periods):
                next_value = np.mean(last_values)
                forecast_values.append(float(next_value))
                last_values = np.append(last_values[1:], next_value)
            
            return forecast_values
        else:
            # Forecast simple basado en el último valor
            last_value = values[-1]
            return [float(last_value)] * periods
    
    async def get_cross_channel_attribution(self, days: int) -> Dict[str, Any]:
        """Calcula atribución multi-canal para conversiones"""
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Obtener leads convertidos y sus fuentes
            stmt = select([
                Lead.source,
                Lead.utm_source,
                Lead.utm_medium,
                Lead.utm_campaign,
                func.count(Lead.id).label('conversion_count'),
                func.avg(Lead.score).label('avg_lead_score'),
                func.avg(case((
                    and_(
                        ExternalLead.external_source.isnot(None),
                        ExternalLead.processed_data.isnot(None)
                    ), 1
                ), else_=0)).label('has_external_data')
            ]).where(
                Lead.created_at >= start_date,
                Lead.status == LeadStatus.CONVERTED
            ).group_by(Lead.source, Lead.utm_source, Lead.utm_medium, Lead.utm_campaign)
            
            result = await self.db.execute(stmt)
            
            attribution_data = []
            total_conversions = 0
            
            for source, utm_source, utm_medium, utm_campaign, count, avg_score, has_external in result:
                attribution_data.append({
                    'channel': source or 'direct',
                    'utm_source': utm_source,
                    'utm_medium': utm_medium,
                    'utm_campaign': utm_campaign,
                    'conversions': count,
                    'avg_lead_score': round(float(avg_score or 0), 2),
                    'has_external_data': bool(has_external),
                    'attribution_weight': 1.0  # Placeholder para modelo de atribución
                })
                
                total_conversions += count
            
            # Calcular shares y aplicar modelo de atribución
            for item in attribution_data:
                item['conversion_share'] = round((item['conversions'] / total_conversions * 100), 2) if total_conversions > 0 else 0
            
            return {
                'period_days': days,
                'total_conversions': total_conversions,
                'attribution_model': 'last_touch',  # Placeholder
                'channel_breakdown': sorted(attribution_data, key=lambda x: x['conversions'], reverse=True),
                'top_performing_channel': attribution_data[0] if attribution_data else None
            }
            
        except Exception as e:
            logger.error(f"Error in cross-channel attribution: {e}")
            return {'error': str(e)}