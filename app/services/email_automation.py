import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Substitution
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import re
from jinja2 import Template
from sqlalchemy.orm import Session
import asyncio

from ..models.workflow import EmailTemplate, EmailSend, LeadSegment
from ..models.integration import Lead
from ..core.config import settings
from ..core.database import get_db

class EmailAutomationService:
    """Servicio completo para automatización de emails"""
    
    def __init__(self):
        self.sendgrid_client = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        self.default_sender = Email(settings.FROM_EMAIL)
        
    async def send_template_email(self,
                                to_email: str,
                                template_id: int,
                                subject: str = None,
                                personalization_data: Dict[str, Any] = None,
                                workflow_execution_id: int = None,
                                ab_variant: str = None,
                                db: Session = None) -> Dict[str, Any]:
        """
        Envía un email usando un template personalizable
        
        Args:
            to_email: Email del destinatario
            template_id: ID del template en base de datos
            subject: Subject personalizado (opcional)
            personalization_data: Datos para personalización
            workflow_execution_id: ID de ejecución del workflow
            ab_variant: Variante A/B si aplica
            db: Sesión de base de datos
            
        Returns:
            dict: Resultado del envío
        """
        
        if not db:
            db = next(get_db())
        
        # Obtener template
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            return {"success": False, "error": "Template no encontrado"}
        
        # Obtener lead
        lead = db.query(Lead).filter(Lead.email == to_email).first()
        if not lead:
            return {"success": False, "error": "Lead no encontrado"}
        
        # Personalizar contenido
        personalized_content = await self._personalize_template(
            template, lead, personalization_data or {}
        )
        
        # Usar subject personalizado o del template
        email_subject = subject or personalized_content["subject"]
        
        try:
            # Crear email con SendGrid
            message = Mail(
                from_email=self.default_sender,
                to_emails=To(to_email),
                subject=email_subject,
                html_content=personalized_content["html_content"]
            )
            
            # Agregar contenido de texto si existe
            if personalized_content.get("text_content"):
                message.content = [
                    Content("text/plain", personalized_content["text_content"]),
                    Content("text/html", personalized_content["html_content"])
                ]
            
            # Configurar tracking
            message.tracking_settings = self._get_tracking_settings()
            
            # Agregar custom args para tracking
            message.custom_args = {
                "lead_id": str(lead.id),
                "template_id": str(template_id),
                "workflow_execution_id": str(workflow_execution_id) if workflow_execution_id else "",
                "ab_variant": ab_variant or "",
                "sent_at": datetime.utcnow().isoformat()
            }
            
            # Enviar email
            response = self.sendgrid_client.send(message)
            
            # Guardar registro del envío
            email_send = EmailSend(
                template_id=template_id,
                lead_id=lead.id,
                workflow_execution_id=workflow_execution_id,
                to_email=to_email,
                subject=email_subject,
                provider_message_id=response.headers.get('X-Message-Id'),
                provider='sendgrid',
                status='sent',
                sent_at=datetime.utcnow(),
                ab_variant=ab_variant
            )
            
            db.add(email_send)
            
            # Actualizar contador del template
            template.sent_count += 1
            
            db.commit()
            
            return {
                "success": True,
                "message_id": response.headers.get('X-Message-Id'),
                "status_code": response.status_code,
                "email_send_id": email_send.id
            }
            
        except Exception as e:
            # Guardar error
            email_send = EmailSend(
                template_id=template_id,
                lead_id=lead.id,
                workflow_execution_id=workflow_execution_id,
                to_email=to_email,
                subject=email_subject,
                status='failed',
                error_message=str(e),
                ab_variant=ab_variant
            )
            
            db.add(email_send)
            db.commit()
            
            return {
                "success": False,
                "error": str(e),
                "email_send_id": email_send.id
            }
    
    async def _personalize_template(self,
                                  template: EmailTemplate,
                                  lead: Lead,
                                  custom_data: Dict[str, Any]) -> Dict[str, str]:
        """Personaliza el contenido del template con datos del lead"""
        
        # Datos base para personalización
        personalization_data = {
            # Datos del lead
            "lead_name": lead.name or "Cliente",
            "lead_first_name": (lead.name or "").split(" ")[0] if lead.name else "Cliente",
            "lead_email": lead.email,
            "lead_phone": lead.phone or "",
            "lead_company": lead.company or "",
            "lead_score": lead.score,
            "lead_source": lead.source or "",
            "lead_status": lead.status or "",
            "lead_segment": lead.segment or "",
            
            # Datos temporales
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "current_month": datetime.now().strftime("%B"),
            "current_year": datetime.now().strftime("%Y"),
            
            # Datos de la empresa
            "company_name": settings.APP_NAME,
            "from_email": settings.FROM_EMAIL,
            
            # Datos custom
            **custom_data
        }
        
        # Personalizar subject
        subject_template = Template(template.subject)
        personalized_subject = subject_template.render(**personalization_data)
        
        # Personalizar HTML content
        html_template = Template(template.html_content)
        personalized_html = html_template.render(**personalization_data)
        
        # Personalizar text content si existe
        personalized_text = None
        if template.text_content:
            text_template = Template(template.text_content)
            personalized_text = text_template.render(**personalization_data)
        
        # Contenido dinámico basado en segmentación
        if template.dynamic_content and lead.segment:
            dynamic_content = template.dynamic_content.get(lead.segment, {})
            if dynamic_content:
                # Reemplazar contenido dinámico
                for key, value in dynamic_content.items():
                    placeholder = f"{{{{{key}}}}}"
                    personalized_html = personalized_html.replace(placeholder, value)
                    if personalized_text:
                        personalized_text = personalized_text.replace(placeholder, value)
        
        return {
            "subject": personalized_subject,
            "html_content": personalized_html,
            "text_content": personalized_text
        }
    
    def _get_tracking_settings(self) -> dict:
        """Configuración de tracking para SendGrid"""
        
        return {
            "click_tracking": {"enable": True},
            "open_tracking": {"enable": True},
            "subscription_tracking": {"enable": True},
            "ganalytics": {"enable": False}  # Configurar si usas Google Analytics
        }
    
    async def create_email_template(self,
                                  name: str,
                                  subject: str,
                                  html_content: str,
                                  text_content: str = None,
                                  category: str = "general",
                                  variables: List[str] = None,
                                  dynamic_content: Dict = None,
                                  created_by: str = "system",
                                  db: Session = None) -> EmailTemplate:
        """Crea un nuevo template de email"""
        
        if not db:
            db = next(get_db())
        
        template = EmailTemplate(
            name=name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            category=category,
            variables=variables or [],
            dynamic_content=dynamic_content or {},
            created_by=created_by,
            is_active=True
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return template
    
    async def send_bulk_emails(self,
                             template_id: int,
                             lead_ids: List[int],
                             personalization_data: Dict[int, Dict] = None,
                             batch_size: int = 100,
                             db: Session = None) -> Dict[str, Any]:
        """Envía emails en bulk a múltiples leads"""
        
        if not db:
            db = next(get_db())
        
        # Obtener leads
        leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
        
        results = {
            "total_leads": len(leads),
            "successful_sends": 0,
            "failed_sends": 0,
            "errors": []
        }
        
        # Procesar en lotes
        for i in range(0, len(leads), batch_size):
            batch_leads = leads[i:i + batch_size]
            
            for lead in batch_leads:
                if not lead.email:
                    results["failed_sends"] += 1
                    results["errors"].append(f"Lead {lead.id}: Sin email")
                    continue
                
                # Datos de personalización específicos para este lead
                lead_personalization = personalization_data.get(lead.id, {}) if personalization_data else {}
                
                # Enviar email
                result = await self.send_template_email(
                    to_email=lead.email,
                    template_id=template_id,
                    personalization_data=lead_personalization,
                    db=db
                )
                
                if result["success"]:
                    results["successful_sends"] += 1
                else:
                    results["failed_sends"] += 1
                    results["errors"].append(f"Lead {lead.id}: {result.get('error', 'Error desconocido')}")
            
            # Pequeña pausa entre lotes para no saturar SendGrid
            await asyncio.sleep(1)
        
        return results
    
    async def create_email_sequence(self,
                                  sequence_name: str,
                                  templates_data: List[Dict],
                                  trigger_conditions: Dict = None,
                                  db: Session = None) -> int:
        """Crea una secuencia de emails automatizada"""
        
        if not db:
            db = next(get_db())
        
        # Crear templates para la secuencia
        template_ids = []
        
        for i, template_data in enumerate(templates_data):
            template = await self.create_email_template(
                name=f"{sequence_name} - Email {i+1}",
                subject=template_data["subject"],
                html_content=template_data["html_content"],
                text_content=template_data.get("text_content"),
                category="sequence",
                variables=template_data.get("variables"),
                created_by="email_sequence",
                db=db
            )
            template_ids.append(template.id)
        
        # Crear workflow para la secuencia
        from ..services.workflow_engine import WorkflowEngine, ActionType, TriggerType
        
        # Construir steps del workflow
        steps = []
        for i, (template_id, template_data) in enumerate(zip(template_ids, templates_data)):
            steps.append({
                "step_number": i + 1,
                "action_type": ActionType.SEND_EMAIL,
                "parameters": {
                    "template_id": template_id,
                    "subject": template_data["subject"]
                },
                "delay_minutes": template_data.get("delay_days", 0) * 24 * 60
            })
        
        # Crear workflow
        from ..models.workflow import Workflow
        
        workflow = Workflow(
            name=f"Secuencia: {sequence_name}",
            description=f"Secuencia automática de {len(templates_data)} emails",
            trigger_type=TriggerType.MANUAL,  # Se disparará manualmente
            steps=steps,
            conditions=[trigger_conditions] if trigger_conditions else [],
            is_active=True,
            category="email_sequence",
            created_by="email_automation"
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        return workflow.id
    
    async def handle_email_event(self,
                                event_type: str,
                                message_id: str,
                                event_data: Dict[str, Any],
                                db: Session = None):
        """Maneja eventos de email (opens, clicks, bounces, etc.) desde webhooks"""
        
        if not db:
            db = next(get_db())
        
        # Buscar el email send por message_id
        email_send = db.query(EmailSend)\
            .filter(EmailSend.provider_message_id == message_id)\
            .first()
        
        if not email_send:
            print(f"⚠️ Email send no encontrado para message_id: {message_id}")
            return
        
        # Procesar según tipo de evento
        if event_type == "delivered":
            email_send.status = "delivered"
            email_send.delivered_at = datetime.utcnow()
            
        elif event_type == "open":
            if not email_send.opened_at:
                email_send.opened_at = datetime.utcnow()
                # Actualizar stats del template
                template = db.query(EmailTemplate).filter(EmailTemplate.id == email_send.template_id).first()
                if template:
                    template.opened_count += 1
                    template.open_rate = template.opened_count / template.sent_count if template.sent_count > 0 else 0
            
            email_send.open_count += 1
            email_send.status = "opened"
            
        elif event_type == "click":
            if not email_send.first_clicked_at:
                email_send.first_clicked_at = datetime.utcnow()
                # Actualizar stats del template
                template = db.query(EmailTemplate).filter(EmailTemplate.id == email_send.template_id).first()
                if template:
                    template.clicked_count += 1
                    template.click_rate = template.clicked_count / template.sent_count if template.sent_count > 0 else 0
            
            email_send.click_count += 1
            
            # Guardar URL clickeada
            clicked_url = event_data.get("url", "")
            if clicked_url:
                links_clicked = email_send.links_clicked or []
                links_clicked.append({
                    "url": clicked_url,
                    "timestamp": datetime.utcnow().isoformat()
                })
                email_send.links_clicked = links_clicked
            
            email_send.status = "clicked"
            
        elif event_type == "bounce":
            email_send.status = "bounced"
            email_send.bounced_at = datetime.utcnow()
            email_send.error_message = event_data.get("reason", "Email bounced")
            
            # Actualizar stats del template
            template = db.query(EmailTemplate).filter(EmailTemplate.id == email_send.template_id).first()
            if template:
                template.bounced_count += 1
                template.bounce_rate = template.bounced_count / template.sent_count if template.sent_count > 0 else 0
            
        elif event_type == "unsubscribe":
            email_send.unsubscribed_at = datetime.utcnow()
            
            # Marcar lead como unsubscribed
            lead = db.query(Lead).filter(Lead.id == email_send.lead_id).first()
            if lead:
                lead.email_unsubscribed = True
                lead.unsubscribed_at = datetime.utcnow()
            
            # Actualizar stats del template
            template = db.query(EmailTemplate).filter(EmailTemplate.id == email_send.template_id).first()
            if template:
                template.unsubscribed_count += 1
                template.unsubscribe_rate = template.unsubscribed_count / template.sent_count if template.sent_count > 0 else 0
        
        db.commit()
        
        # Disparar workflows basados en eventos de email
        if event_type in ["open", "click"]:
            from ..services.workflow_engine import WorkflowEngine, TriggerType
            
            workflow_engine = WorkflowEngine()
            trigger_type = TriggerType.EMAIL_OPENED if event_type == "open" else TriggerType.EMAIL_CLICKED
            
            await workflow_engine.trigger_workflow(
                trigger_type=trigger_type,
                lead_id=email_send.lead_id,
                trigger_data={
                    "email_send_id": email_send.id,
                    "template_id": email_send.template_id,
                    "message_id": message_id,
                    "event_data": event_data
                },
                db=db
            )
    
    async def get_email_analytics(self,
                                template_id: int = None,
                                days: int = 30,
                                segment: str = None,
                                db: Session = None) -> Dict[str, Any]:
        """Obtiene analytics detallados de emails"""
        
        if not db:
            db = next(get_db())
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Query base
        query = db.query(EmailSend).filter(EmailSend.created_at > since_date)
        
        if template_id:
            query = query.filter(EmailSend.template_id == template_id)
        
        if segment:
            query = query.join(Lead).filter(Lead.segment == segment)
        
        email_sends = query.all()
        
        # Calcular métricas
        total_sent = len(email_sends)
        total_delivered = len([e for e in email_sends if e.delivered_at])
        total_opened = len([e for e in email_sends if e.opened_at])
        total_clicked = len([e for e in email_sends if e.first_clicked_at])
        total_bounced = len([e for e in email_sends if e.bounced_at])
        total_unsubscribed = len([e for e in email_sends if e.unsubscribed_at])
        
        # Calcular rates
        delivery_rate = total_delivered / total_sent if total_sent > 0 else 0
        open_rate = total_opened / total_delivered if total_delivered > 0 else 0
        click_rate = total_clicked / total_delivered if total_delivered > 0 else 0
        bounce_rate = total_bounced / total_sent if total_sent > 0 else 0
        unsubscribe_rate = total_unsubscribed / total_delivered if total_delivered > 0 else 0
        
        # Click-through rate (clicks / opens)
        ctr = total_clicked / total_opened if total_opened > 0 else 0
        
        # Top performing templates
        template_performance = {}
        for email_send in email_sends:
            tid = email_send.template_id
            if tid not in template_performance:
                template_performance[tid] = {
                    "template_id": tid,
                    "sent": 0,
                    "opened": 0,
                    "clicked": 0
                }
            
            template_performance[tid]["sent"] += 1
            if email_send.opened_at:
                template_performance[tid]["opened"] += 1
            if email_send.first_clicked_at:
                template_performance[tid]["clicked"] += 1
        
        # Calcular rates por template y ordenar
        top_templates = []
        for tid, stats in template_performance.items():
            template = db.query(EmailTemplate).filter(EmailTemplate.id == tid).first()
            open_rate_template = stats["opened"] / stats["sent"] if stats["sent"] > 0 else 0
            click_rate_template = stats["clicked"] / stats["sent"] if stats["sent"] > 0 else 0
            
            top_templates.append({
                "template_id": tid,
                "template_name": template.name if template else f"Template {tid}",
                "sent": stats["sent"],
                "open_rate": open_rate_template,
                "click_rate": click_rate_template
            })
        
        top_templates.sort(key=lambda x: x["click_rate"], reverse=True)
        
        return {
            "period_days": days,
            "totals": {
                "sent": total_sent,
                "delivered": total_delivered,
                "opened": total_opened,
                "clicked": total_clicked,
                "bounced": total_bounced,
                "unsubscribed": total_unsubscribed
            },
            "rates": {
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "bounce_rate": bounce_rate,
                "unsubscribe_rate": unsubscribe_rate,
                "ctr": ctr  # Click-through rate
            },
            "top_templates": top_templates[:10],
            "trends": await self._calculate_email_trends(email_sends, days)
        }
    
    async def _calculate_email_trends(self, email_sends: List[EmailSend], days: int) -> Dict[str, List]:
        """Calcula tendencias de métricas de email por día"""
        
        from collections import defaultdict
        
        daily_stats = defaultdict(lambda: {"sent": 0, "opened": 0, "clicked": 0})
        
        for email_send in email_sends:
            date_key = email_send.created_at.strftime("%Y-%m-%d")
            daily_stats[date_key]["sent"] += 1
            
            if email_send.opened_at:
                daily_stats[date_key]["opened"] += 1
            
            if email_send.first_clicked_at:
                daily_stats[date_key]["clicked"] += 1
        
        # Convertir a listas ordenadas por fecha
        sorted_dates = sorted(daily_stats.keys())
        
        trends = {
            "dates": sorted_dates,
            "sent": [daily_stats[date]["sent"] for date in sorted_dates],
            "opened": [daily_stats[date]["opened"] for date in sorted_dates],
            "clicked": [daily_stats[date]["clicked"] for date in sorted_dates],
            "open_rates": [
                daily_stats[date]["opened"] / daily_stats[date]["sent"] if daily_stats[date]["sent"] > 0 else 0
                for date in sorted_dates
            ],
            "click_rates": [
                daily_stats[date]["clicked"] / daily_stats[date]["sent"] if daily_stats[date]["sent"] > 0 else 0
                for date in sorted_dates
            ]
        }
        
        return trends
    
    async def create_ab_test_templates(self,
                                     base_template_id: int,
                                     variants: List[Dict[str, str]],
                                     test_name: str,
                                     db: Session = None) -> List[int]:
        """Crea templates para A/B testing"""
        
        if not db:
            db = next(get_db())
        
        base_template = db.query(EmailTemplate).filter(EmailTemplate.id == base_template_id).first()
        if not base_template:
            raise ValueError("Template base no encontrado")
        
        variant_template_ids = []
        
        for i, variant in enumerate(variants):
            variant_letter = chr(65 + i)  # A, B, C, etc.
            
            variant_template = EmailTemplate(
                name=f"{base_template.name} - Variant {variant_letter}",
                subject=variant.get("subject", base_template.subject),
                html_content=variant.get("html_content", base_template.html_content),
                text_content=variant.get("text_content", base_template.text_content),
                category=base_template.category,
                variables=base_template.variables,
                dynamic_content=base_template.dynamic_content,
                is_ab_test=True,
                ab_variant=variant_letter,
                parent_template_id=base_template_id,
                created_by="ab_test"
            )
            
            db.add(variant_template)
            db.commit()
            db.refresh(variant_template)
            
            variant_template_ids.append(variant_template.id)
        
        # Marcar template base como A/B test
        base_template.is_ab_test = True
        db.commit()
        
        return variant_template_ids
    
    async def send_ab_test_emails(self,
                                template_ids: List[int],
                                lead_ids: List[int],
                                split_percentages: List[float] = None,
                                db: Session = None) -> Dict[str, Any]:
        """Envía emails A/B test distribuyendo leads según percentages"""
        
        if not db:
            db = next(get_db())
        
        if not split_percentages:
            # Distribución uniforme
            split_percentages = [100.0 / len(template_ids)] * len(template_ids)
        
        import random
        
        results = {"variants": {}, "total_leads": len(lead_ids)}
        
        for lead_id in lead_ids:
            # Determinar variante basada en percentages
            rand_num = random.random() * 100
            cumulative = 0
            selected_template_idx = 0
            
            for i, percentage in enumerate(split_percentages):
                cumulative += percentage
                if rand_num <= cumulative:
                    selected_template_idx = i
                    break
            
            template_id = template_ids[selected_template_idx]
            template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
            variant = template.ab_variant if template else f"Variant_{selected_template_idx}"
            
            # Obtener lead
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead or not lead.email:
                continue
            
            # Enviar email
            result = await self.send_template_email(
                to_email=lead.email,
                template_id=template_id,
                ab_variant=variant,
                db=db
            )
            
            # Registrar resultado
            if variant not in results["variants"]:
                results["variants"][variant] = {"sent": 0, "failed": 0}
            
            if result["success"]:
                results["variants"][variant]["sent"] += 1
            else:
                results["variants"][variant]["failed"] += 1
        
        return results
    
    async def get_ab_test_results(self,
                                parent_template_id: int,
                                days: int = 30,
                                db: Session = None) -> Dict[str, Any]:
        """Analiza resultados de A/B test"""
        
        if not db:
            db = next(get_db())
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Obtener todas las variantes del A/B test
        variants = db.query(EmailTemplate).filter(
            EmailTemplate.parent_template_id == parent_template_id
        ).all()
        
        # Incluir template original
        base_template = db.query(EmailTemplate).filter(EmailTemplate.id == parent_template_id).first()
        if base_template:
            variants.append(base_template)
        
        variant_results = {}
        
        for variant in variants:
            # Obtener email sends para esta variante
            email_sends = db.query(EmailSend)\
                .filter(EmailSend.template_id == variant.id)\
                .filter(EmailSend.created_at > since_date)\
                .all()
            
            sent = len(email_sends)
            opened = len([e for e in email_sends if e.opened_at])
            clicked = len([e for e in email_sends if e.first_clicked_at])
            
            variant_key = variant.ab_variant or "Original"
            
            variant_results[variant_key] = {
                "template_id": variant.id,
                "template_name": variant.name,
                "sent": sent,
                "opened": opened,
                "clicked": clicked,
                "open_rate": opened / sent if sent > 0 else 0,
                "click_rate": clicked / sent if sent > 0 else 0,
                "ctr": clicked / opened if opened > 0 else 0
            }
        
        # Determinar ganador (mayor click rate)
        winner = None
        best_click_rate = 0
        
        for variant_key, stats in variant_results.items():
            if stats["click_rate"] > best_click_rate:
                best_click_rate = stats["click_rate"]
                winner = variant_key
        
        return {
            "parent_template_id": parent_template_id,
            "test_period_days": days,
            "variants": variant_results,
            "winner": winner,
            "statistical_significance": await self._calculate_significance(variant_results)
        }
    
    async def _calculate_significance(self, variant_results: Dict) -> Dict[str, Any]:
        """Calcula significancia estadística del A/B test"""
        
        # Implementación básica - en producción usar librerías estadísticas más robustas
        variants = list(variant_results.values())
        
        if len(variants) != 2:
            return {"significant": False, "note": "Significancia solo calculada para 2 variantes"}
        
        v1, v2 = variants[0], variants[1]
        
        # Chi-square test básico
        n1, n2 = v1["sent"], v2["sent"]
        x1, x2 = v1["clicked"], v2["clicked"]
        
        if n1 < 30 or n2 < 30:
            return {"significant": False, "note": "Muestra insuficiente (min 30 por variante)"}
        
        p1, p2 = x1/n1 if n1 > 0 else 0, x2/n2 if n2 > 0 else 0
        p_pooled = (x1 + x2) / (n1 + n2) if (n1 + n2) > 0 else 0
        
        # Cálculo simplificado del z-score
        if p_pooled > 0 and p_pooled < 1:
            se = ((p_pooled * (1 - p_pooled)) * (1/n1 + 1/n2)) ** 0.5
            z_score = abs(p1 - p2) / se if se > 0 else 0
            significant = z_score > 1.96  # 95% confidence
        else:
            significant = False
            z_score = 0
        
        return {
            "significant": significant,
            "z_score": z_score,
            "confidence_level": 0.95,
            "note": "Cálculo básico - usar herramientas estadísticas más robustas en producción"
        }
    
    async def cleanup_old_email_data(self, days_to_keep: int = 90, db: Session = None):
        """Limpia datos antiguos de emails para mantener performance"""
        
        if not db:
            db = next(get_db())
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Eliminar email sends antiguos
        old_email_sends = db.query(EmailSend)\
            .filter(EmailSend.created_at < cutoff_date)\
            .count()
        
        db.query(EmailSend).filter(EmailSend.created_at < cutoff_date).delete()
        
        db.commit()
        
        print(f"🧹 Eliminados {old_email_sends} registros de email antiguos")
        
        return {"deleted_email_sends": old_email_sends}