import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from jinja2 import Template
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
import logging
from enum import Enum
from pathlib import Path

# FastAPI
from fastapi import BackgroundTasks, Depends
from fastapi_cache.decorator import cache

# Base de datos
from sqlalchemy.orm import Session

# Nuestros servicios
from ..core.database import get_db
from ..core.config import settings
from .analytics_service import HubSpotAnalyticsService
from ..services.email_automation import EmailService
from ..services.report_generator import ReportGenerator, ReportFormat, ReportType

# Logger
logger = logging.getLogger("automated_reporting")

class ReportFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class ReportDeliveryMethod(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    STORAGE = "storage"

class AutomatedReportingService:
    """
    Servicio de automatización de reportes con generación programada,
    múltiples formatos y canales de entrega.
    """
    
    def __init__(self):
        self.analytics = HubSpotAnalyticsService()
        self.email_service = EmailService()
        self.report_generator = ReportGenerator()
        
        # Configuración
        self.company_config = {
            'name': settings.COMPANY_NAME,
            'logo_url': settings.COMPANY_LOGO_URL,
            'primary_color': '#3B82F6',
            'secondary_color': '#10B981'
        }
        
        # Templates cargados
        self.report_templates = self._load_report_templates()
        self.scheduled_reports = self._load_scheduled_reports()
        
        # Cache de reportes generados
        self.report_cache = {}
    
    def _load_report_templates(self) -> Dict:
        """Carga y configura todos los templates de reportes"""
        
        return {
            "weekly_sales": {
                "name": "Weekly Sales Performance",
                "frequency": ReportFrequency.WEEKLY,
                "template": self._get_weekly_sales_template(),
                "default_recipients": ["sales-team@company.com", "management@company.com"],
                "subject_template": "📊 Weekly Sales Performance Report - Week of {date}",
                "enabled": True,
                "data_sources": ["leads", "conversions", "hubspot_sync", "revenue_forecast"],
                "charts": ["funnel", "source_performance", "trends"]
            },
            "monthly_executive": {
                "name": "Monthly Executive Summary", 
                "frequency": ReportFrequency.MONTHLY,
                "template": self._get_monthly_executive_template(),
                "default_recipients": ["executives@company.com", "ceo@company.com"],
                "subject_template": "📈 Monthly Executive Report - {month} {year}",
                "enabled": True,
                "data_sources": ["kpis", "revenue", "team_performance", "market_analysis"],
                "charts": ["kpi_trends", "revenue_breakdown", "market_share"]
            },
            "daily_health": {
                "name": "Daily System Health",
                "frequency": ReportFrequency.DAILY,
                "template": self._get_daily_health_template(),
                "default_recipients": ["tech-team@company.com", "operations@company.com"],
                "subject_template": "🔧 Daily System Health Report - {date}",
                "enabled": True,
                "data_sources": ["system_metrics", "integration_health", "error_logs"],
                "charts": ["system_health", "error_trends"]
            },
            "quarterly_business": {
                "name": "Quarterly Business Review",
                "frequency": ReportFrequency.QUARTERLY,
                "template": self._get_quarterly_business_template(),
                "default_recipients": ["board@company.com", "investors@company.com"],
                "subject_template": "🎯 Q{quarter} Business Review - {year}",
                "enabled": True,
                "data_sources": ["financials", "growth_metrics", "market_position", "strategic_goals"],
                "charts": ["financial_trends", "growth_metrics", "competitive_analysis"]
            }
        }
    
    def _load_scheduled_reports(self) -> Dict:
        """Carga la configuración de reportes programados"""
        
        return {
            "monday_morning_weekly": {
                "template": "weekly_sales",
                "schedule": "0 8 * * 1",  # Lunes 8:00 AM
                "recipients": ["sales-team@company.com", "sales-director@company.com"],
                "delivery_methods": [ReportDeliveryMethod.EMAIL, ReportDeliveryMethod.SLACK],
                "format": ReportFormat.HTML,
                "timezone": "America/New_York",
                "enabled": True
            },
            "monthly_executive_review": {
                "template": "monthly_executive", 
                "schedule": "0 9 1 * *",  # Primer día del mes 9:00 AM
                "recipients": ["executive-team@company.com"],
                "delivery_methods": [ReportDeliveryMethod.EMAIL],
                "format": ReportFormat.PDF,
                "timezone": "America/New_York",
                "enabled": True
            },
            "daily_health_check": {
                "template": "daily_health",
                "schedule": "0 7 * * *",  # Diario 7:00 AM
                "recipients": ["devops@company.com"],
                "delivery_methods": [ReportDeliveryMethod.EMAIL, ReportDeliveryMethod.SLACK],
                "format": ReportFormat.HTML,
                "timezone": "UTC",
                "enabled": True
            }
        }
    
    def _get_weekly_sales_template(self) -> str:
        """Template para reporte semanal de ventas"""
        
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Weekly Sales Performance Report</title>
            <style>
                :root {
                    --primary-color: {{ primary_color }};
                    --secondary-color: {{ secondary_color }};
                    --text-color: #333;
                    --bg-color: #f8f9fa;
                    --border-color: #dee2e6;
                }
                
                body { 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background-color: var(--bg-color);
                    color: var(--text-color);
                }
                
                .container { 
                    max-width: 1200px; 
                    margin: 0 auto; 
                    background: white; 
                    border-radius: 12px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
                    overflow: hidden;
                }
                
                .header { 
                    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
                    color: white; 
                    padding: 30px; 
                    text-align: center;
                }
                
                .header h1 { 
                    margin: 0; 
                    font-size: 2.5em; 
                    font-weight: 300;
                }
                
                .header .subtitle { 
                    font-size: 1.2em; 
                    opacity: 0.9; 
                    margin-top: 10px;
                }
                
                .metric-grid { 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                    gap: 20px; 
                    padding: 30px; 
                }
                
                .metric-card { 
                    background: white; 
                    border: 1px solid var(--border-color); 
                    border-radius: 8px; 
                    padding: 20px; 
                    text-align: center;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                
                .metric-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }
                
                .metric-value { 
                    font-size: 2.5em; 
                    font-weight: bold; 
                    color: var(--primary-color); 
                    margin: 10px 0;
                }
                
                .metric-label { 
                    font-size: 0.9em; 
                    color: #666; 
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                
                .trend-up { color: #10B981; }
                .trend-down { color: #EF4444; }
                .trend-neutral { color: #6B7280; }
                
                .section { 
                    padding: 0 30px 30px; 
                    border-bottom: 1px solid var(--border-color);
                }
                
                .section:last-child { border-bottom: none; }
                
                .section-title { 
                    font-size: 1.5em; 
                    color: var(--primary-color); 
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                
                .chart-container { 
                    background: white; 
                    border-radius: 8px; 
                    padding: 20px; 
                    margin: 20px 0;
                    border: 1px solid var(--border-color);
                }
                
                .chart { text-align: center; }
                
                table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }
                
                th, td { 
                    border: 1px solid var(--border-color); 
                    padding: 15px; 
                    text-align: left; 
                }
                
                th { 
                    background-color: var(--primary-color); 
                    color: white; 
                    font-weight: 600;
                    text-transform: uppercase;
                    font-size: 0.9em;
                    letter-spacing: 0.5px;
                }
                
                tr:nth-child(even) { background-color: #f8f9fa; }
                
                .insights-grid { 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                    gap: 20px; 
                }
                
                .insight-card { 
                    background: white; 
                    border-left: 4px solid var(--primary-color); 
                    padding: 20px; 
                    border-radius: 4px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                
                .insight-card.positive { border-left-color: #10B981; }
                .insight-card.warning { border-left-color: #F59E0B; }
                .insight-card.critical { border-left-color: #EF4444; }
                
                .footer { 
                    text-align: center; 
                    padding: 30px; 
                    background: var(--bg-color); 
                    color: #666;
                    font-size: 0.9em;
                }
                
                .badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                
                .badge.success { background: #D1FAE5; color: #065F46; }
                .badge.warning { background: #FEF3C7; color: #92400E; }
                .badge.error { background: #FEE2E2; color: #991B1B; }
                
                @media (max-width: 768px) {
                    .metric-grid { grid-template-columns: 1fr; }
                    .insights-grid { grid-template-columns: 1fr; }
                    .header h1 { font-size: 2em; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Header -->
                <div class="header">
                    <h1>📊 Weekly Sales Performance Report</h1>
                    <div class="subtitle">
                        Period: {{ period.start_date }} to {{ period.end_date }} | Generated: {{ generated_at }}
                    </div>
                </div>
                
                <!-- Key Metrics -->
                <div class="section">
                    <h2 class="section-title">📈 Key Performance Indicators</h2>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Total Leads</div>
                            <div class="metric-value">{{ metrics.total_leads|default(0)|number_format }}</div>
                            <div class="trend-{{ metrics.leads_trend|default('neutral') }}">
                                {{ metrics.leads_change|default(0)|abs }}% 
                                {{ "↗" if metrics.leads_trend == 'up' else "↘" if metrics.leads_trend == 'down' else "➡" }}
                                vs previous week
                            </div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Conversion Rate</div>
                            <div class="metric-value">{{ "%.1f"|format(metrics.conversion_rate|default(0)) }}%</div>
                            <div>{{ metrics.converted_leads|default(0) }} / {{ metrics.total_leads|default(0) }} converted</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Hot Leads</div>
                            <div class="metric-value">{{ metrics.hot_leads|default(0)|number_format }}</div>
                            <div>Ready for sales contact</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Avg Lead Score</div>
                            <div class="metric-value">{{ "%.1f"|format(metrics.avg_lead_score|default(0)) }}</div>
                            <div>Overall lead quality</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Response Time</div>
                            <div class="metric-value">{{ "%.1f"|format(metrics.avg_response_time|default(0)) }}h</div>
                            <div>Average first response</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Pipeline Value</div>
                            <div class="metric-value">${{ metrics.pipeline_value|default(0)|number_format }}</div>
                            <div>Total opportunity value</div>
                        </div>
                    </div>
                </div>
                
                <!-- Conversion Funnel -->
                <div class="section">
                    <h2 class="section-title">🔄 Conversion Funnel</h2>
                    <div class="chart-container">
                        <div class="chart">
                            <img src="data:image/png;base64,{{ charts.funnel }}" alt="Conversion Funnel" style="max-width: 100%;">
                        </div>
                    </div>
                </div>
                
                <!-- Source Performance -->
                <div class="section">
                    <h2 class="section-title">🎯 Source Performance</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Source</th>
                                <th>Leads</th>
                                <th>Avg Score</th>
                                <th>Conversions</th>
                                <th>Conversion Rate</th>
                                <th>Quality Score</th>
                                <th>Trend</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for source in source_performance %}
                            <tr>
                                <td><strong>{{ source.source|title }}</strong></td>
                                <td>{{ source.total_leads|number_format }}</td>
                                <td>{{ "%.1f"|format(source.avg_score|default(0)) }}</td>
                                <td>{{ source.conversions|number_format }}</td>
                                <td>{{ "%.1f"|format(source.conversion_rate|default(0)) }}%</td>
                                <td>
                                    <span class="badge {{ 'success' if source.quality_score >= 8 else 'warning' if source.quality_score >= 5 else 'error' }}">
                                        {{ "%.1f"|format(source.quality_score|default(0)) }}/10
                                    </span>
                                </td>
                                <td class="trend-{{ source.trend|default('neutral') }}">
                                    {{ "↗" if source.trend == 'up' else "↘" if source.trend == 'down' else "➡" }}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                <!-- HubSpot Integration -->
                <div class="section">
                    <h2 class="section-title">🔄 HubSpot Integration Status</h2>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Sync Status</div>
                            <div class="metric-value">{{ "%.1f"|format(sync_metrics.sync_percentage|default(0)) }}%</div>
                            <div>{{ sync_metrics.synced_leads|default(0) }} / {{ sync_metrics.total_leads|default(0) }} synced</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Recent Activity</div>
                            <div class="metric-value">{{ sync_metrics.recent_syncs_24h|default(0)|number_format }}</div>
                            <div>Syncs in last 24h</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Health Status</div>
                            <div class="metric-value">
                                <span class="badge {{ 'success' if sync_metrics.sync_health == 'Healthy' else 'warning' if sync_metrics.sync_health == 'Degraded' else 'error' }}">
                                    {{ sync_metrics.sync_health|default('Unknown') }}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Revenue Forecast -->
                <div class="section">
                    <h2 class="section-title">💰 Revenue Forecast</h2>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Forecasted Revenue</div>
                            <div class="metric-value">${{ revenue_forecast.forecasted_revenue|default(0)|number_format }}</div>
                            <div>Next 30 days projection</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Pipeline Value</div>
                            <div class="metric-value">{{ (revenue_forecast.hot_leads|default(0) + revenue_forecast.warm_leads|default(0))|number_format }}</div>
                            <div>{{ revenue_forecast.hot_leads|default(0) }} hot + {{ revenue_forecast.warm_leads|default(0) }} warm</div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-label">Win Probability</div>
                            <div class="metric-value">{{ "%.1f"|format(revenue_forecast.win_probability|default(0)) }}%</div>
                            <div>Weighted probability</div>
                        </div>
                    </div>
                </div>
                
                <!-- Insights & Recommendations -->
                <div class="section">
                    <h2 class="section-title">🎯 Key Insights & Recommendations</h2>
                    <div class="insights-grid">
                        {% for insight in insights %}
                        <div class="insight-card {{ insight.type|default('') }}">
                            <h4>{{ insight.title }}</h4>
                            <p>{{ insight.description }}</p>
                            {% if insight.recommendation %}
                            <p><strong>Recommendation:</strong> {{ insight.recommendation }}</p>
                            {% endif %}
                            {% if insight.impact %}
                            <p><em>Impact: {{ insight.impact }}</em></p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Footer -->
                <div class="footer">
                    <p>This report was automatically generated by your Sales Automation System.</p>
                    <p>For questions or custom reports, contact your system administrator.</p>
                    <p><small>Report ID: {{ report_id }} | Generated at: {{ generated_at }}</small></p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_monthly_executive_template(self) -> str:
        """Template para reporte ejecutivo mensual"""
        # Similar structure to weekly but with executive focus
        return "<!-- Monthly Executive Template -->"
    
    def _get_daily_health_template(self) -> str:
        """Template para reporte diario de salud del sistema"""
        return "<!-- Daily Health Template -->"
    
    def _get_quarterly_business_template(self) -> str:
        """Template para revisión trimestral de negocio"""
        return "<!-- Quarterly Business Template -->"
    
    async def generate_report(self, 
                            report_type: str,
                            frequency: ReportFrequency,
                            custom_data: Optional[Dict] = None,
                            db: Session = None) -> Dict[str, Any]:
        """Genera un reporte completo con datos y visualizaciones"""
        
        try:
            start_time = datetime.utcnow()
            logger.info(f"Generating {frequency.value} {report_type} report")
            
            # Obtener template
            template_config = self.report_templates.get(report_type)
            if not template_config:
                raise ValueError(f"Report type '{report_type}' not found")
            
            # Obtener período
            period = self._get_report_period(frequency)
            
            # Recopilar datos
            report_data = await self._collect_report_data(report_type, period, db, custom_data)
            
            # Generar visualizaciones
            charts = await self._generate_charts(report_data, template_config['charts'])
            
            # Renderizar template
            html_content = self._render_template(template_config['template'], {
                **report_data,
                'charts': charts,
                'period': period,
                'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'report_id': f"{report_type}_{frequency.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                'primary_color': self.company_config['primary_color'],
                'secondary_color': self.company_config['secondary_color']
            })
            
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"Report generated successfully in {generation_time:.2f}s")
            
            return {
                "success": True,
                "report_type": report_type,
                "frequency": frequency,
                "content": html_content,
                "data": report_data,
                "charts": charts,
                "metadata": {
                    "generation_time": generation_time,
                    "period": period,
                    "data_sources": template_config['data_sources'],
                    "size_bytes": len(html_content.encode('utf-8'))
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "report_type": report_type,
                "frequency": frequency
            }
    
    def _get_report_period(self, frequency: ReportFrequency) -> Dict[str, str]:
        """Calcula el período del reporte basado en la frecuencia"""
        
        now = datetime.utcnow()
        
        if frequency == ReportFrequency.DAILY:
            start_date = now - timedelta(days=1)
            end_date = now
        elif frequency == ReportFrequency.WEEKLY:
            start_date = now - timedelta(days=7)
            end_date = now
        elif frequency == ReportFrequency.MONTHLY:
            start_date = now - timedelta(days=30)
            end_date = now
        elif frequency == ReportFrequency.QUARTERLY:
            start_date = now - timedelta(days=90)
            end_date = now
        elif frequency == ReportFrequency.YEARLY:
            start_date = now - timedelta(days=365)
            end_date = now
        else:
            start_date = now - timedelta(days=7)
            end_date = now
        
        return {
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "start_datetime": start_date.isoformat(),
            "end_datetime": end_date.isoformat()
        }
    
    async def _collect_report_data(self, 
                                 report_type: str, 
                                 period: Dict[str, str],
                                 db: Session,
                                 custom_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Recopila datos de múltiples fuentes para el reporte"""
        
        data = {
            "period": period,
            "custom_data": custom_data or {}
        }
        
        template_config = self.report_templates[report_type]
        
        # Recopilar datos de cada fuente
        for source in template_config['data_sources']:
            try:
                if source == "leads":
                    data["metrics"] = await self._get_lead_metrics(period, db)
                elif source == "conversions":
                    data["metrics"].update(await self._get_conversion_metrics(period, db))
                elif source == "hubspot_sync":
                    data["sync_metrics"] = await self._get_sync_metrics(period, db)
                elif source == "revenue_forecast":
                    data["revenue_forecast"] = await self._get_revenue_forecast(period, db)
                elif source == "source_performance":
                    data["source_performance"] = await self._get_source_performance(period, db)
                elif source == "insights":
                    data["insights"] = await self._generate_insights(data, db)
                
            except Exception as e:
                logger.error(f"Error collecting data from {source}: {str(e)}")
                # Continuar con otras fuentes de datos
        
        return data
    
    async def _get_lead_metrics(self, period: Dict[str, str], db: Session) -> Dict[str, Any]:
        """Obtiene métricas de leads"""
        
        # En producción, implementar consultas reales a la base de datos
        return {
            "total_leads": 1247,
            "leads_trend": "up",
            "leads_change": 12.5,
            "converted_leads": 89,
            "conversion_rate": 7.1,
            "hot_leads": 156,
            "avg_lead_score": 72.4,
            "avg_response_time": 2.3,
            "pipeline_value": 2450000
        }
    
    async def _get_conversion_metrics(self, period: Dict[str, str], db: Session) -> Dict[str, Any]:
        """Obtiene métricas de conversión"""
        
        return {
            "conversion_funnel": {
                "awareness": 1247,
                "consideration": 567,
                "conversion": 89,
                "retention": 45
            },
            "conversion_trend": "up",
            "conversion_change": 5.2
        }
    
    async def _get_sync_metrics(self, period: Dict[str, str], db: Session) -> Dict[str, Any]:
        """Obtiene métricas de sincronización con HubSpot"""
        
        return {
            "sync_percentage": 98.7,
            "synced_leads": 1230,
            "total_leads": 1247,
            "recent_syncs_24h": 45,
            "sync_health": "Healthy",
            "last_sync": datetime.utcnow().isoformat()
        }
    
    async def _get_revenue_forecast(self, period: Dict[str, str], db: Session) -> Dict[str, Any]:
        """Genera forecast de revenue"""
        
        return {
            "forecasted_revenue": 1850000,
            "hot_leads": 156,
            "warm_leads": 289,
            "win_probability": 68.5,
            "confidence_interval": "high"
        }
    
    async def _get_source_performance(self, period: Dict[str, str], db: Session) -> List[Dict[str, Any]]:
        """Obtiene performance por fuente de leads"""
        
        return [
            {
                "source": "website",
                "total_leads": 567,
                "avg_score": 78.2,
                "conversions": 45,
                "conversion_rate": 7.9,
                "quality_score": 8.5,
                "trend": "up"
            },
            {
                "source": "linkedin",
                "total_leads": 234,
                "avg_score": 82.1,
                "conversions": 22,
                "conversion_rate": 9.4,
                "quality_score": 8.8,
                "trend": "up"
            },
            {
                "source": "referral",
                "total_leads": 189,
                "avg_score": 85.6,
                "conversions": 18,
                "conversion_rate": 9.5,
                "quality_score": 9.2,
                "trend": "stable"
            }
        ]
    
    async def _generate_insights(self, data: Dict, db: Session) -> List[Dict[str, Any]]:
        """Genera insights automáticos basados en los datos"""
        
        insights = []
        
        # Insight 1: Performance de fuentes
        if data.get('source_performance'):
            best_source = max(data['source_performance'], key=lambda x: x['conversion_rate'])
            insights.append({
                "type": "positive",
                "title": f"High Performing Source: {best_source['source'].title()}",
                "description": f"{best_source['source'].title()} shows the highest conversion rate at {best_source['conversion_rate']}%",
                "recommendation": f"Consider increasing investment in {best_source['source']} campaigns",
                "impact": "High"
            })
        
        # Insight 2: Tendencias de leads
        metrics = data.get('metrics', {})
        if metrics.get('leads_trend') == 'up':
            insights.append({
                "type": "positive", 
                "title": "Positive Lead Growth Trend",
                "description": f"Leads increased by {metrics.get('leads_change', 0)}% compared to previous period",
                "impact": "Medium"
            })
        
        # Insight 3: Calidad de leads
        if metrics.get('avg_lead_score', 0) > 70:
            insights.append({
                "type": "positive",
                "title": "Strong Lead Quality",
                "description": f"Average lead score of {metrics.get('avg_lead_score', 0)} indicates high-quality leads",
                "impact": "High"
            })
        
        return insights
    
    async def _generate_charts(self, data: Dict, chart_types: List[str]) -> Dict[str, str]:
        """Genera gráficos y los convierte a base64"""
        
        charts = {}
        
        for chart_type in chart_types:
            try:
                if chart_type == "funnel":
                    charts["funnel"] = await self._create_funnel_chart(data)
                elif chart_type == "source_performance":
                    charts["source_performance"] = await self._create_source_performance_chart(data)
                # Agregar más tipos de gráficos según sea necesario
                    
            except Exception as e:
                logger.error(f"Error generating {chart_type} chart: {str(e)}")
                charts[chart_type] = self._create_placeholder_chart(f"Error generating {chart_type}")
        
        return charts
    
    async def _create_funnel_chart(self, data: Dict) -> str:
        """Crea gráfico de funnel de conversión"""
        
        try:
            plt.figure(figsize=(10, 6))
            
            funnel_data = data.get('metrics', {}).get('conversion_funnel', {})
            if not funnel_data:
                funnel_data = {
                    'awareness': 1000,
                    'consideration': 600, 
                    'conversion': 300,
                    'retention': 150
                }
            
            stages = list(funnel_data.keys())
            values = list(funnel_data.values())
            
            # Crear funnel chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Calcular posiciones para el funnel
            y_pos = range(len(stages))
            widths = [v / max(values) * 0.8 for v in values]  # Normalizar anchos
            
            bars = ax.barh(y_pos, widths, height=0.6, color=self.company_config['primary_color'])
            
            # Etiquetas
            ax.set_yticks(y_pos)
            ax.set_yticklabels([s.title() for s in stages])
            ax.set_xlabel('Normalized Count')
            ax.set_title('Conversion Funnel')
            
            # Agregar valores en las barras
            for i, (bar, value) in enumerate(zip(bars, values)):
                width = bar.get_width()
                ax.text(width + 0.01, bar.get_y() + bar.get_height()/2, 
                       f'{value:,}', ha='left', va='center')
            
            plt.tight_layout()
            
            # Convertir a base64
            return self._fig_to_base64(plt)
            
        except Exception as e:
            logger.error(f"Error creating funnel chart: {str(e)}")
            return self._create_placeholder_chart("Funnel Chart")
    
    async def _create_source_performance_chart(self, data: Dict) -> str:
        """Crea gráfico de performance por fuente"""
        
        try:
            sources = data.get('source_performance', [])
            if not sources:
                return self._create_placeholder_chart("Source Performance")
            
            source_names = [s['source'] for s in sources]
            conversion_rates = [s['conversion_rate'] for s in sources]
            
            plt.figure(figsize=(12, 6))
            bars = plt.bar(source_names, conversion_rates, color=self.company_config['secondary_color'])
            
            plt.title('Conversion Rate by Source')
            plt.ylabel('Conversion Rate (%)')
            plt.xticks(rotation=45)
            
            # Agregar valores en las barras
            for bar, rate in zip(bars, conversion_rates):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        f'{rate:.1f}%', ha='center', va='bottom')
            
            plt.tight_layout()
            
            return self._fig_to_base64(plt)
            
        except Exception as e:
            logger.error(f"Error creating source performance chart: {str(e)}")
            return self._create_placeholder_chart("Source Performance")
    
    def _fig_to_base64(self, plt) -> str:
        """Convierte figura de matplotlib a base64"""
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        buffer.close()
        plt.close()
        
        return image_base64
    
    def _create_placeholder_chart(self, title: str) -> str:
        """Crea un gráfico placeholder cuando hay errores"""
        
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, f'Chart: {title}\nData Not Available', 
                ha='center', va='center', transform=plt.gca().transAxes)
        plt.axis('off')
        
        return self._fig_to_base64(plt)
    
    def _render_template(self, template_str: str, data: Dict) -> str:
        """Renderiza el template Jinja2 con los datos"""
        
        # Agregar filtros personalizados
        def number_format(value):
            return f"{value:,}"
        
        template = Template(template_str)
        template.environment.filters['number_format'] = number_format
        
        return template.render(**data)
    
    async def send_report(self,
                         report_type: str,
                         frequency: ReportFrequency,
                         recipients: List[str],
                         delivery_methods: List[ReportDeliveryMethod],
                         custom_data: Optional[Dict] = None,
                         db: Session = None) -> Dict[str, Any]:
        """Genera y envía un reporte a través de múltiples canales"""
        
        try:
            # Generar reporte
            report_result = await self.generate_report(report_type, frequency, custom_data, db)
            
            if not report_result['success']:
                return report_result
            
            # Enviar por cada método de entrega
            delivery_results = {}
            
            for method in delivery_methods:
                try:
                    if method == ReportDeliveryMethod.EMAIL:
                        result = await self._send_via_email(
                            report_result, recipients, report_type, frequency
                        )
                    elif method == ReportDeliveryMethod.SLACK:
                        result = await self._send_via_slack(
                            report_result, recipients, report_type, frequency
                        )
                    elif method == ReportDeliveryMethod.WEBHOOK:
                        result = await self._send_via_webhook(
                            report_result, recipients, report_type, frequency
                        )
                    elif method == ReportDeliveryMethod.STORAGE:
                        result = await self._save_to_storage(
                            report_result, report_type, frequency
                        )
                    
                    delivery_results[method.value] = result
                    
                except Exception as e:
                    logger.error(f"Error sending via {method}: {str(e)}")
                    delivery_results[method.value] = {"success": False, "error": str(e)}
            
            return {
                "success": True,
                "report_generation": report_result,
                "delivery_results": delivery_results,
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in send_report: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_via_email(self, 
                            report_result: Dict, 
                            recipients: List[str],
                            report_type: str,
                            frequency: ReportFrequency) -> Dict[str, Any]:
        """Envía reporte por email"""
        
        template_config = self.report_templates[report_type]
        subject = template_config['subject_template'].format(
            date=datetime.now().strftime('%Y-%m-%d'),
            month=datetime.now().strftime('%B'),
            year=datetime.now().strftime('%Y'),
            quarter=(datetime.now().month - 1) // 3 + 1
        )
        
        return await self.email_service.send_html_email(
            recipients=recipients,
            subject=subject,
            html_content=report_result['content'],
            attachments=[],  # Podemos agregar PDF/Excel aquí
            category=f"automated_report_{report_type}"
        )
    
    async def _send_via_slack(self, report_result: Dict, recipients: List[str], report_type: str, frequency: ReportFrequency) -> Dict:
        """Envía resumen del reporte por Slack"""
        # Implementar integración con Slack
        return {"success": True, "message": "Slack integration not implemented"}
    
    async def _send_via_webhook(self, report_result: Dict, recipients: List[str], report_type: str, frequency: ReportFrequency) -> Dict:
        """Envía datos del reporte via webhook"""
        # Implementar webhooks
        return {"success": True, "message": "Webhook integration not implemented"}
    
    async def _save_to_storage(self, report_result: Dict, report_type: str, frequency: ReportFrequency) -> Dict:
        """Guarda reporte en almacenamiento"""
        # Implementar guardado en S3/Google Drive/etc.
        return {"success": True, "message": "Storage integration not implemented"}
    
    async def schedule_automated_reports(self, background_tasks: BackgroundTasks, db: Session = None):
        """Programa todos los reportes automáticos basados en la configuración"""
        
        logger.info("Scheduling automated reports...")
        
        for report_id, schedule_config in self.scheduled_reports.items():
            if schedule_config['enabled']:
                background_tasks.add_task(
                    self._execute_scheduled_report,
                    report_id,
                    schedule_config,
                    db
                )
        
        return {"scheduled": len(self.scheduled_reports), "message": "Reports scheduled successfully"}
    
    async def _execute_scheduled_report(self, report_id: str, config: Dict, db: Session):
        """Ejecuta un reporte programado"""
        
        try:
            logger.info(f"Executing scheduled report: {report_id}")
            
            template_name = config['template']
            frequency = ReportFrequency(self.report_templates[template_name]['frequency'])
            
            await self.send_report(
                report_type=template_name,
                frequency=frequency,
                recipients=config['recipients'],
                delivery_methods=config['delivery_methods'],
                db=db
            )
            
            logger.info(f"Successfully executed scheduled report: {report_id}")
            
        except Exception as e:
            logger.error(f"Error executing scheduled report {report_id}: {str(e)}")
    
    def get_available_reports(self) -> List[Dict[str, Any]]:
        """Retorna lista de reportes disponibles"""
        
        reports = []
        for report_id, config in self.report_templates.items():
            if config['enabled']:
                reports.append({
                    'id': report_id,
                    'name': config['name'],
                    'frequency': config['frequency'].value,
                    'description': f"Automated {config['frequency']} {config['name'].lower()} report",
                    'data_sources': config['data_sources'],
                    'default_recipients': config['default_recipients'],
                    'charts': config['charts']
                })
        
        return reports
    
    def get_scheduled_reports(self) -> List[Dict[str, Any]]:
        """Retorna lista de reportes programados"""
        
        scheduled = []
        for report_id, config in self.scheduled_reports.items():
            if config['enabled']:
                scheduled.append({
                    'id': report_id,
                    'template': config['template'],
                    'schedule': config['schedule'],
                    'recipients': config['recipients'],
                    'delivery_methods': [m.value for m in config['delivery_methods']],
                    'format': config['format'].value,
                    'timezone': config['timezone']
                })
        
        return scheduled

# FastAPI Router
from fastapi import APIRouter

router = APIRouter()
reporting_service = AutomatedReportingService()

@router.get("/reports/available")
async def get_available_reports():
    """Obtiene reportes disponibles"""
    return reporting_service.get_available_reports()

@router.get("/reports/scheduled")
async def get_scheduled_reports():
    """Obtiene reportes programados"""
    return reporting_service.get_scheduled_reports()

@router.post("/reports/generate")
async def generate_automated_report(
    report_type: str,
    frequency: ReportFrequency,
    recipients: List[str],
    delivery_methods: List[ReportDeliveryMethod],
    custom_data: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    """Genera y envía un reporte automático"""
    return await reporting_service.send_report(
        report_type, frequency, recipients, delivery_methods, custom_data, db
    )

@router.post("/reports/schedule/start")
async def start_scheduled_reports(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Inicia el scheduling de reportes automáticos"""
    return await reporting_service.schedule_automated_reports(background_tasks, db)