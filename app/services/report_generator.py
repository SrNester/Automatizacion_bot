import asyncio
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import io
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import matplotlib.pyplot as plt
import seaborn as sns
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import LineChart, BarChart, Reference

from ..core.config import settings
from ..services.analytics.analytics_engine import AnalyticsEngine

class ReportGenerator:
    """Generador de reportes en múltiples formatos (PDF, Excel, HTML)"""
    
    def __init__(self):
        self.analytics_engine = AnalyticsEngine()
        
        # Configuración de estilos
        self.styles = getSampleStyleSheet()
        self.company_colors = {
            'primary': '#3B82F6',
            'secondary': '#10B981', 
            'accent': '#F59E0B',
            'dark': '#1F2937',
            'light': '#F9FAFB'
        }
        
        # Templates de reportes
        self.report_templates = {
            'executive': self._executive_template,
            'detailed_analytics': self._detailed_analytics_template,
            'channel_performance': self._channel_performance_template,
            'lead_quality': self._lead_quality_template
        }
    
    async def generate_custom_report(self, 
                                   report_type: str,
                                   period: str,
                                   custom_filters: Optional[Dict] = None,
                                   db: Session = None) -> Dict[str, Any]:
        """Genera un reporte personalizado en formato JSON"""
        
        # Determinar días según período
        period_days = {
            'weekly': 7,
            'monthly': 30,
            'quarterly': 90,
            'yearly': 365
        }.get(period, 30)
        
        # Obtener datos base
        if report_type == 'executive':
            data = await self.analytics_engine.generate_executive_report(period, db)
        else:
            # Usar template específico
            template_func = self.report_templates.get(report_type)
            if not template_func:
                raise ValueError(f"Report type '{report_type}' no soportado")
            
            data = await template_func(period_days, custom_filters, db)
        
        return {
            "report_type": report_type,
            "period": period,
            "generated_at": datetime.utcnow().isoformat(),
            "data": data,
            "filters": custom_filters or {},
            "metadata": {
                "total_pages": 1,
                "format": "json",
                "version": "1.0"
            }
        }
    
    async def generate_pdf_report(self,
                                report_type: str,
                                period: str, 
                                custom_filters: Optional[Dict] = None,
                                db: Session = None) -> bytes:
        """Genera reporte en formato PDF"""
        
        # Obtener datos del reporte
        report_data = await self.generate_custom_report(report_type, period, custom_filters, db)
        
        # Crear PDF en memoria
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Título del reporte
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor(self.company_colors['primary']),
            spaceAfter=30
        )
        
        story.append(Paragraph(f"Reporte {report_type.title()}", title_style))
        story.append(Paragraph(f"Período: {period} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                              self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Contenido según tipo de reporte
        if report_type == 'executive':
            story.extend(self._build_executive_pdf_content(report_data))
        elif report_type == 'detailed_analytics':
            story.extend(self._build_detailed_pdf_content(report_data))
        elif report_type == 'channel_performance':
            story.extend(self._build_channel_pdf_content(report_data))
        
        # Generar PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _build_executive_pdf_content(self, report_data: Dict) -> List:
        """Construye contenido PDF para reporte ejecutivo"""
        
        content = []
        
        # Resumen ejecutivo
        content.append(Paragraph("Resumen Ejecutivo", self.styles['Heading2']))
        content.append(Spacer(1, 12))
        
        # KPIs principales
        kpis = report_data['data'].get('summary', {}).get('kpi_summary', {})
        
        # Crear tabla de KPIs
        kpi_data = [['Métrica', 'Valor', 'Cambio']]
        
        for kpi_name, kpi_data_item in kpis.items():
            value = kpi_data_item.get('value', 0)
            change = kpi_data_item.get('change', 0)
            
            # Formatear valores según el tipo
            if kpi_name in ['conversion_rate', 'roi']:
                formatted_value = f"{value:.1%}"
                formatted_change = f"{change:+.1f}%"
            elif kpi_name in ['revenue_attributed', 'cost_per_lead']:
                formatted_value = f"${value:,.0f}"
                formatted_change = f"{change:+.1f}%"
            elif kpi_name == 'response_time':
                formatted_value = f"{value:.1f}s"
                formatted_change = f"{change:+.1f}%"
            else:
                formatted_value = f"{value:,.0f}"
                formatted_change = f"{change:+.1f}%"
            
            kpi_data.append([
                kpi_name.replace('_', ' ').title(),
                formatted_value,
                formatted_change
            ])
        
        kpi_table = Table(kpi_data)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.company_colors['primary'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        content.append(kpi_table)
        content.append(Spacer(1, 20))
        
        # Insights
        insights = report_data['data'].get('insights', [])
        if insights:
            content.append(Paragraph("Insights Principales", self.styles['Heading2']))
            content.append(Spacer(1, 12))
            
            for insight in insights[:3]:  # Top 3 insights
                bullet_text = f"• <b>{insight['title']}:</b> {insight['description']}"
                content.append(Paragraph(bullet_text, self.styles['Normal']))
                content.append(Spacer(1, 6))
        
        # Recomendaciones
        recommendations = report_data['data'].get('recommendations', [])
        if recommendations:
            content.append(Spacer(1, 20))
            content.append(Paragraph("Recomendaciones", self.styles['Heading2']))
            content.append(Spacer(1, 12))
            
            for rec in recommendations[:3]:
                bullet_text = f"• <b>{rec['title']}:</b> {rec['description']}"
                content.append(Paragraph(bullet_text, self.styles['Normal']))
                content.append(Spacer(1, 6))
        
        return content
    
    def _build_detailed_pdf_content(self, report_data: Dict) -> List:
        """Construye contenido PDF para reporte detallado"""
        
        content = []
        
        # Análisis detallado
        content.append(Paragraph("Análisis Detallado", self.styles['Heading2']))
        content.append(Spacer(1, 12))
        
        # Funnel de conversión
        funnel_data = report_data['data'].get('lead_funnel', {})
        if funnel_data:
            content.append(Paragraph("Funnel de Conversión", self.styles['Heading3']))
            
            stages = funnel_data.get('stages', {})
            funnel_table_data = [['Etapa', 'Cantidad', 'Tasa de Conversión']]
            
            stage_names = {
                'captured': 'Capturados',
                'engaged': 'Comprometidos', 
                'qualified': 'Calificados',
                'converted': 'Convertidos'
            }
            
            for stage, count in stages.items():
                stage_name = stage_names.get(stage, stage.title())
                # Calcular conversion rate (mock)
                conversion_rate = count / stages.get('captured', 1) if stages.get('captured') else 0
                
                funnel_table_data.append([
                    stage_name,
                    f"{count:,}",
                    f"{conversion_rate:.1%}"
                ])
            
            funnel_table = Table(funnel_table_data)
            funnel_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.company_colors['secondary'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            content.append(funnel_table)
            content.append(Spacer(1, 20))
        
        return content
    
    def _build_channel_pdf_content(self, report_data: Dict) -> List:
        """Construye contenido PDF para reporte de canales"""
        
        content = []
        
        # Performance por canal
        content.append(Paragraph("Performance por Canal", self.styles['Heading2']))
        content.append(Spacer(1, 12))
        
        channels = report_data['data'].get('channel_performance', [])
        if channels:
            channel_table_data = [['Canal', 'Leads', 'Conversiones', 'ROI', 'Costo por Lead']]
            
            for channel in channels[:5]:  # Top 5 channels
                channel_table_data.append([
                    channel.get('channel', 'Unknown'),
                    f"{channel.get('leads_count', 0):,}",
                    f"{channel.get('conversions', 0):,}",
                    f"{channel.get('roi', 0):.0f}%",
                    f"${channel.get('cost_per_lead', 0):.2f}"
                ])
            
            channel_table = Table(channel_table_data)
            channel_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.company_colors['accent'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            content.append(channel_table)
        
        return content
    
    async def generate_excel_report(self,
                                  report_type: str,
                                  period: str,
                                  custom_filters: Optional[Dict] = None,
                                  db: Session = None) -> bytes:
        """Genera reporte en formato Excel"""
        
        # Obtener datos del reporte
        report_data = await self.generate_custom_report(report_type, period, custom_filters, db)
        
        # Crear workbook en memoria
        buffer = io.BytesIO()
        workbook = Workbook()
        
        # Hoja principal - Resumen
        ws_summary = workbook.active
        ws_summary.title = "Resumen"
        
        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
        
        # Título
        ws_summary['A1'] = f"Reporte {report_type.title()}"
        ws_summary['A1'].font = Font(size=16, bold=True)
        ws_summary['A2'] = f"Período: {period}"
        ws_summary['A3'] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        # KPIs (si es reporte ejecutivo)
        if report_type == 'executive':
            kpis = report_data['data'].get('summary', {}).get('kpi_summary', {})
            
            # Headers
            ws_summary['A5'] = "Métrica"
            ws_summary['B5'] = "Valor" 
            ws_summary['C5'] = "Cambio %"
            
            for cell in ['A5', 'B5', 'C5']:
                ws_summary[cell].font = header_font
                ws_summary[cell].fill = header_fill
                ws_summary[cell].alignment = Alignment(horizontal='center')
            
            # Datos de KPIs
            row = 6
            for kpi_name, kpi_data_item in kpis.items():
                ws_summary[f'A{row}'] = kpi_name.replace('_', ' ').title()
                ws_summary[f'B{row}'] = kpi_data_item.get('value', 0)
                ws_summary[f'C{row}'] = kpi_data_item.get('change', 0)
                row += 1
            
            # Crear gráfico de KPIs
            self._add_excel_chart(ws_summary, "KPIs Principales", 5, row-1)
        
        # Hoja de canales (si hay datos)
        channels = report_data['data'].get('channel_performance', [])
        if channels:
            ws_channels = workbook.create_sheet(title="Canales")
            
            # Headers
            headers = ['Canal', 'Leads', 'Conversiones', 'Tasa Conv.', 'ROI', 'Costo/Lead']
            for col, header in enumerate(headers, 1):
                cell = ws_channels.cell(row=1, column=col)
                cell.value = header
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
            
            # Datos de canales
            for row, channel in enumerate(channels, 2):
                ws_channels.cell(row=row, column=1).value = channel.get('channel', 'Unknown')
                ws_channels.cell(row=row, column=2).value = channel.get('leads_count', 0)
                ws_channels.cell(row=row, column=3).value = channel.get('conversions', 0)
                ws_channels.cell(row=row, column=4).value = channel.get('conversion_rate', 0)
                ws_channels.cell(row=row, column=5).value = channel.get('roi', 0)
                ws_channels.cell(row=row, column=6).value = channel.get('cost_per_lead', 0)
            
            # Crear gráfico de canales
            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = "Performance por Canal"
            chart.y_axis.title = 'Leads'
            chart.x_axis.title = 'Canal'
            
            data = Reference(ws_channels, min_col=2, min_row=1, max_row=len(channels)+1, max_col=2)
            cats = Reference(ws_channels, min_col=1, min_row=2, max_row=len(channels)+1)
            
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            chart.height = 10
            chart.width = 15
            
            ws_channels.add_chart(chart, "H2")
        
        # Guardar en buffer
        workbook.save(buffer)
        excel_bytes = buffer.getvalue()
        buffer.close()
        
        return excel_bytes
    
    def _add_excel_chart(self, worksheet, title: str, start_row: int, end_row: int):
        """Agrega un gráfico a la hoja de Excel"""
        
        chart = LineChart()
        chart.title = title
        chart.style = 13
        chart.y_axis.title = 'Valor'
        chart.x_axis.title = 'Métrica'
        
        data = Reference(worksheet, min_col=2, min_row=start_row, max_row=end_row)
        cats = Reference(worksheet, min_col=1, min_row=start_row+1, max_row=end_row)
        
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 10
        chart.width = 15
        
        worksheet.add_chart(chart, f"E{start_row}")
    
    async def generate_and_send_report(self,
                                     report_type: str,
                                     period: str,
                                     format_type: str,
                                     email_recipients: Optional[List[str]] = None,
                                     custom_filters: Optional[Dict] = None,
                                     db: Session = None):
        """Genera reporte y lo envía por email"""
        
        try:
            # Generar reporte según formato
            if format_type == 'pdf':
                report_bytes = await self.generate_pdf_report(report_type, period, custom_filters, db)
                filename = f"reporte_{report_type}_{period}_{datetime.now().strftime('%Y%m%d')}.pdf"
                content_type = "application/pdf"
                
            elif format_type == 'excel':
                report_bytes = await self.generate_excel_report(report_type, period, custom_filters, db)
                filename = f"reporte_{report_type}_{period}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                
            else:
                raise ValueError(f"Formato {format_type} no soportado")
            
            # Enviar por email si hay destinatarios
            if email_recipients:
                await self._send_report_email(
                    report_bytes, 
                    filename, 
                    content_type,
                    email_recipients,
                    report_type,
                    period
                )
            
            return {
                "success": True,
                "filename": filename,
                "size_bytes": len(report_bytes),
                "recipients": email_recipients
            }
            
        except Exception as e:
            print(f"❌ Error generando/enviando reporte: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_report_email(self,
                               report_bytes: bytes,
                               filename: str,
                               content_type: str,
                               recipients: List[str],
                               report_type: str,
                               period: str):
        """Envía reporte por email usando SendGrid"""
        
        # En producción, integrar con SendGrid
        # Por ahora, mock del envío
        
        print(f"📧 Enviando reporte {filename} a {len(recipients)} destinatarios")
        print(f"   Tipo: {report_type}, Período: {period}")
        print(f"   Tamaño: {len(report_bytes):,} bytes")
        print(f"   Destinatarios: {', '.join(recipients)}")
        
        # TODO: Implementar envío real con SendGrid
        # from sendgrid import SendGridAPIClient
        # from sendgrid.helpers.mail import Mail, Attachment
        
        return True
    
    # Template functions para diferentes tipos de reporte
    
    async def _executive_template(self, days: int, filters: Optional[Dict], db: Session) -> Dict:
        """Template para reporte ejecutivo"""
        
        return await self.analytics_engine.generate_executive_report(
            "monthly" if days >= 30 else "weekly", db
        )
    
    async def _detailed_analytics_template(self, days: int, filters: Optional[Dict], db: Session) -> Dict:
        """Template para reporte de analytics detallado"""
        
        dashboard_data = await self.analytics_engine.get_executive_dashboard(days, db)
        
        # Agregar análisis detallados específicos
        detailed_data = {
            **dashboard_data,
            "funnel_analysis": await self.analytics_engine.get_detailed_analytics(
                "conversion_funnel", days, "daily", filters, db
            ),
            "quality_breakdown": await self.analytics_engine.get_detailed_analytics(
                "lead_quality_breakdown", days, "daily", filters, db
            ),
            "engagement_metrics": await self.analytics_engine.get_detailed_analytics(
                "engagement_metrics", days, "daily", filters, db
            )
        }
        
        return detailed_data
    
    async def _channel_performance_template(self, days: int, filters: Optional[Dict], db: Session) -> Dict:
        """Template para reporte de performance por canal"""
        
        dashboard_data = await self.analytics_engine.get_executive_dashboard(days, db)
        
        # Enfoque específico en canales
        channel_data = {
            "channel_performance": dashboard_data.get("channel_performance", []),
            "channel_trends": await self._get_channel_trends(days, db),
            "attribution_analysis": await self.analytics_engine.get_detailed_analytics(
                "channel_attribution", days, "daily", filters, db
            ),
            "cost_analysis": await self._get_cost_analysis_by_channel(days, db)
        }
        
        return channel_data
    
    async def _lead_quality_template(self, days: int, filters: Optional[Dict], db: Session) -> Dict:
        """Template para reporte de calidad de leads"""
        
        quality_data = await self.analytics_engine.get_detailed_analytics(
            "lead_quality_breakdown", days, "daily", filters, db
        )
        
        # Agregar análisis específicos de calidad
        enhanced_quality_data = {
            **quality_data,
            "scoring_distribution": await self._get_scoring_distribution(days, db),
            "source_quality_comparison": await self._get_source_quality_comparison(days, db),
            "quality_trends": await self._get_quality_trends(days, db)
        }
        
        return enhanced_quality_data
    
    # Funciones auxiliares para análisis específicos
    
    async def _get_channel_trends(self, days: int, db: Session) -> Dict:
        """Obtiene tendencias de performance por canal"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Query para obtener datos diarios por canal
        from ...models.lead import Lead
        from sqlalchemy import func
        
        daily_channel_data = db.query(
            func.date(Lead.created_at).label('date'),
            Lead.source,
            func.count(Lead.id).label('leads'),
            func.avg(Lead.score).label('avg_score')
        ).filter(Lead.created_at > since_date)\
         .group_by(func.date(Lead.created_at), Lead.source)\
         .order_by(func.date(Lead.created_at))\
         .all()
        
        # Procesar datos para tendencias
        trends = {}
        for date, source, leads, avg_score in daily_channel_data:
            if source not in trends:
                trends[source] = {
                    "dates": [],
                    "leads": [],
                    "avg_scores": []
                }
            
            trends[source]["dates"].append(date.isoformat())
            trends[source]["leads"].append(leads)
            trends[source]["avg_scores"].append(float(avg_score) if avg_score else 0)
        
        return trends
    
    async def _get_cost_analysis_by_channel(self, days: int, db: Session) -> Dict:
        """Análisis de costos por canal"""
        
        # Mock data - en producción integrar con ad APIs
        channels = ['meta_ads', 'google_ads', 'linkedin_ads', 'organic']
        
        cost_analysis = {}
        for channel in channels:
            cost_analysis[channel] = {
                "total_spend": days * 100,  # $100/day mock
                "cost_per_lead": 25,
                "cost_per_conversion": 100,
                "budget_utilization": 0.85,
                "efficiency_score": 0.75
            }
        
        return cost_analysis
    
    async def _get_scoring_distribution(self, days: int, db: Session) -> Dict:
        """Distribución de scoring de leads"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        from ...models.lead import Lead
        from sqlalchemy import func, case
        
        # Query para distribución de scores
        score_distribution = db.query(
            func.sum(case([(Lead.score.between(0, 25), 1)], else_=0)).label('low'),
            func.sum(case([(Lead.score.between(26, 50), 1)], else_=0)).label('medium_low'),
            func.sum(case([(Lead.score.between(51, 75), 1)], else_=0)).label('medium_high'),
            func.sum(case([(Lead.score.between(76, 100), 1)], else_=0)).label('high')
        ).filter(Lead.created_at > since_date).first()
        
        return {
            "0-25": score_distribution.low or 0,
            "26-50": score_distribution.medium_low or 0,
            "51-75": score_distribution.medium_high or 0,
            "76-100": score_distribution.high or 0
        }
    
    async def _get_source_quality_comparison(self, days: int, db: Session) -> Dict:
        """Comparación de calidad por fuente"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        from ...models.lead import Lead
        from sqlalchemy import func
        
        source_quality = db.query(
            Lead.source,
            func.avg(Lead.score).label('avg_score'),
            func.count(Lead.id).label('total_leads'),
            func.sum(func.case([(Lead.score >= 70, 1)], else_=0)).label('high_quality_leads')
        ).filter(Lead.created_at > since_date)\
         .group_by(Lead.source)\
         .all()
        
        comparison = {}
        for source, avg_score, total_leads, high_quality in source_quality:
            comparison[source or 'unknown'] = {
                "avg_score": float(avg_score) if avg_score else 0,
                "total_leads": total_leads,
                "high_quality_leads": high_quality,
                "quality_rate": high_quality / total_leads if total_leads > 0 else 0
            }
        
        return comparison
    
    async def _get_quality_trends(self, days: int, db: Session) -> Dict:
        """Tendencias de calidad de leads"""
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        from ...models.lead import Lead
        from sqlalchemy import func
        
        daily_quality = db.query(
            func.date(Lead.created_at).label('date'),
            func.avg(Lead.score).label('avg_score'),
            func.count(Lead.id).label('total_leads')
        ).filter(Lead.created_at > since_date)\
         .group_by(func.date(Lead.created_at))\
         .order_by(func.date(Lead.created_at))\
         .all()
        
        dates = []
        avg_scores = []
        lead_counts = []
        
        for date, avg_score, total_leads in daily_quality:
            dates.append(date.isoformat())
            avg_scores.append(float(avg_score) if avg_score else 0)
            lead_counts.append(total_leads)
        
        return {
            "dates": dates,
            "avg_scores": avg_scores,
            "lead_counts": lead_counts
        }
    
    def create_visualization(self, data: Dict, chart_type: str, title: str) -> str:
        """Crea visualización usando matplotlib y retorna base64"""
        
        plt.figure(figsize=(10, 6))
        
        if chart_type == 'line':
            plt.plot(data.get('x', []), data.get('y', []))
        elif chart_type == 'bar':
            plt.bar(data.get('x', []), data.get('y', []))
        elif chart_type == 'pie':
            plt.pie(data.get('values', []), labels=data.get('labels', []))
        
        plt.title(title)
        plt.tight_layout()
        
        # Convertir a base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        buffer.close()
        plt.close()
        
        return image_base64
    
    def get_report_metadata(self, report_type: str) -> Dict[str, Any]:
        """Obtiene metadatos de un tipo de reporte"""
        
        metadata = {
            'executive': {
                'name': 'Reporte Ejecutivo',
                'description': 'Resumen ejecutivo con KPIs principales',
                'sections': ['kpis', 'insights', 'recommendations', 'forecast'],
                'estimated_generation_time': '30-60 segundos',
                'supported_formats': ['json', 'pdf', 'excel']
            },
            'detailed_analytics': {
                'name': 'Analytics Detallado',
                'description': 'Análisis profundo de todas las métricas',
                'sections': ['funnel', 'quality', 'engagement', 'trends'],
                'estimated_generation_time': '60-90 segundos',
                'supported_formats': ['json', 'pdf', 'excel']
            },
            'channel_performance': {
                'name': 'Performance por Canal',
                'description': 'Análisis detallado de ROI y performance',
                'sections': ['channels', 'attribution', 'costs', 'trends'],
                'estimated_generation_time': '45-75 segundos',
                'supported_formats': ['json', 'pdf', 'excel']
            },
            'lead_quality': {
                'name': 'Calidad de Leads',
                'description': 'Análisis de scoring y segmentación',
                'sections': ['scoring', 'sources', 'trends', 'recommendations'],
                'estimated_generation_time': '30-45 segundos',
                'supported_formats': ['json', 'pdf']
            }
        }
        
        return metadata.get(report_type, {})
    
    async def schedule_recurring_report(self, 
                                      report_config: Dict,
                                      schedule: str,  # daily, weekly, monthly
                                      recipients: List[str]) -> Dict[str, Any]:
        """Programa reporte recurrente"""
        
        # En producción, integrar con Celery Beat
        scheduled_report = {
            "id": f"scheduled_{datetime.utcnow().timestamp()}",
            "report_type": report_config.get("type"),
            "period": report_config.get("period"),
            "format": report_config.get("format"),
            "schedule": schedule,
            "recipients": recipients,
            "next_execution": self._calculate_next_execution(schedule),
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "scheduled_report": scheduled_report,
            "message": f"Reporte programado {schedule} creado exitosamente"
        }
    
    def _calculate_next_execution(self, schedule: str) -> str:
        """Calcula próxima ejecución según schedule"""
        
        now = datetime.utcnow()
        
        if schedule == 'daily':
            next_exec = now.replace(hour=8, minute=0, second=0) + timedelta(days=1)
        elif schedule == 'weekly':
            days_until_monday = (7 - now.weekday()) % 7
            next_exec = now.replace(hour=8, minute=0, second=0) + timedelta(days=days_until_monday)
        elif schedule == 'monthly':
            if now.day == 1:
                next_exec = now.replace(day=1, hour=8, minute=0, second=0) + timedelta(days=32)
                next_exec = next_exec.replace(day=1)
            else:
                next_exec = now.replace(day=1, hour=8, minute=0, second=0) + timedelta(days=32)
                next_exec = next_exec.replace(day=1)
        else:
            next_exec = now + timedelta(days=1)
        
        return next_exec.isoformat()