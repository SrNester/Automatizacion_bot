from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import asyncio
import aiohttp

# Celery
from celery import Celery

# Base de datos
from sqlalchemy.orm import Session

# Nuestros servicios
from ..services.email_automation import EmailAutomationService
from ..core.database import get_db
from ..core.config import settings
from ..models.integration import Lead
from ..models.workflow import NotificationLog, NotificationType, NotificationStatus

# Logger
logger = logging.getLogger("notifications")

@dataclass
class NotificationResult:
    success: bool
    message: str
    sent_count: int = 0
    failed_count: int = 0
    details: Optional[Dict] = None

class NotificationManager:
    """
    Gestor centralizado de notificaciones
    Soporta email, Slack, SMS y webhooks
    """
    
    def __init__(self):
        self.email_service = EmailAutomationService()
        self.slack_webhook_url = settings.SLACK_WEBHOOK_URL
        self.sms_config = settings.SMS_CONFIG
        
        logger.info("NotificationManager inicializado")
    
    async def send_email_notification(self,
                                   recipients: List[str],
                                   subject: str,
                                   message: str,
                                   template_data: Optional[Dict] = None,
                                   db: Session = None) -> NotificationResult:
        """
        Envía notificación por email
        """
        
        logger.info(f"Enviando notificación email a {len(recipients)} destinatarios: {subject}")
        
        try:
            template_data = template_data or {}
            
            # Usar template básico si no se proporciona uno específico
            html_content = self._create_basic_email_template(subject, message, template_data)
            
            results = {
                "sent": 0,
                "failed": 0,
                "failures": []
            }
            
            for recipient in recipients:
                try:
                    email_result = await self.email_service.send_email(
                        to_email=recipient,
                        subject=subject,
                        html_content=html_content,
                        text_content=message
                    )
                    
                    if email_result.get('success'):
                        results["sent"] += 1
                        logger.debug(f"Email enviado a {recipient}")
                    else:
                        results["failed"] += 1
                        results["failures"].append({
                            'recipient': recipient,
                            'error': email_result.get('error', 'Unknown error')
                        })
                        logger.warning(f"Error enviando email a {recipient}: {email_result.get('error')}")
                    
                except Exception as e:
                    results["failed"] += 1
                    results["failures"].append({
                        'recipient': recipient,
                        'error': str(e)
                    })
                    logger.error(f"Excepción enviando email a {recipient}: {str(e)}")
            
            # Log de la operación
            if db:
                await self._log_notification(
                    db, NotificationType.EMAIL, subject, results["sent"], results["failed"], recipients
                )
            
            return NotificationResult(
                success=results["failed"] == 0,
                message=f"Notificación email: {results['sent']} enviados, {results['failed']} fallos",
                sent_count=results["sent"],
                failed_count=results["failed"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en notificación email: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error en notificación email: {str(e)}",
                failed_count=len(recipients)
            )
    
    async def send_slack_notification(self,
                                   channel: str,
                                   message: str,
                                   attachments: Optional[List[Dict]] = None,
                                   db: Session = None) -> NotificationResult:
        """
        Envía notificación a Slack
        """
        
        logger.info(f"Enviando notificación Slack al canal {channel}")
        
        try:
            if not self.slack_webhook_url:
                return NotificationResult(
                    success=False,
                    message="Slack webhook URL no configurada",
                    failed_count=1
                )
            
            payload = {
                "channel": channel,
                "text": message,
                "attachments": attachments or [],
                "mrkdwn": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook_url, json=payload) as response:
                    if response.status == 200:
                        # Log de la operación
                        if db:
                            await self._log_notification(
                                db, NotificationType.SLACK, message, 1, 0, [channel]
                            )
                        
                        return NotificationResult(
                            success=True,
                            message="Notificación Slack enviada exitosamente",
                            sent_count=1
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"Error enviando a Slack: {response.status} - {error_text}")
                        
                        return NotificationResult(
                            success=False,
                            message=f"Error Slack: {response.status} - {error_text}",
                            failed_count=1
                        )
                        
        except Exception as e:
            logger.error(f"Error en notificación Slack: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error en notificación Slack: {str(e)}",
                failed_count=1
            )
    
    async def send_sms_notification(self,
                                 phone_numbers: List[str],
                                 message: str,
                                 db: Session = None) -> NotificationResult:
        """
        Envía notificación por SMS
        """
        
        logger.info(f"Enviando notificación SMS a {len(phone_numbers)} números")
        
        try:
            if not self.sms_config or not self.sms_config.get('enabled'):
                return NotificationResult(
                    success=False,
                    message="SMS no configurado",
                    failed_count=len(phone_numbers)
                )
            
            # Placeholder para integración con proveedor SMS (Twilio, etc.)
            # En producción, integrarías con tu proveedor SMS aquí
            
            results = {
                "sent": 0,
                "failed": 0,
                "failures": []
            }
            
            for phone in phone_numbers:
                try:
                    # Simular envío de SMS (reemplazar con llamada real a API)
                    sms_sent = await self._send_sms_via_provider(phone, message)
                    
                    if sms_sent:
                        results["sent"] += 1
                        logger.debug(f"SMS enviado a {phone}")
                    else:
                        results["failed"] += 1
                        results["failures"].append({
                            'phone': phone,
                            'error': 'SMS provider error'
                        })
                        logger.warning(f"Error enviando SMS a {phone}")
                    
                except Exception as e:
                    results["failed"] += 1
                    results["failures"].append({
                        'phone': phone,
                        'error': str(e)
                    })
                    logger.error(f"Excepción enviando SMS a {phone}: {str(e)}")
            
            # Log de la operación
            if db:
                await self._log_notification(
                    db, NotificationType.SMS, message, results["sent"], results["failed"], phone_numbers
                )
            
            return NotificationResult(
                success=results["failed"] == 0,
                message=f"Notificación SMS: {results['sent']} enviados, {results['failed']} fallos",
                sent_count=results["sent"],
                failed_count=results["failed"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en notificación SMS: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error en notificación SMS: {str(e)}",
                failed_count=len(phone_numbers)
            )
    
    async def send_webhook_notification(self,
                                     webhook_url: str,
                                     payload: Dict,
                                     db: Session = None) -> NotificationResult:
        """
        Envía notificación via webhook
        """
        
        logger.info(f"Enviando notificación webhook a {webhook_url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status in [200, 201, 202]:
                        # Log de la operación
                        if db:
                            await self._log_notification(
                                db, NotificationType.WEBHOOK, "Webhook notification", 1, 0, [webhook_url]
                            )
                        
                        return NotificationResult(
                            success=True,
                            message="Webhook enviado exitosamente",
                            sent_count=1
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"Error en webhook: {response.status} - {error_text}")
                        
                        return NotificationResult(
                            success=False,
                            message=f"Error webhook: {response.status} - {error_text}",
                            failed_count=1
                        )
                        
        except Exception as e:
            logger.error(f"Error en notificación webhook: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error en notificación webhook: {str(e)}",
                failed_count=1
            )
    
    async def send_system_alert(self,
                             alert_type: str,
                             message: str,
                             severity: str = "warning",
                             db: Session = None) -> NotificationResult:
        """
        Envía alerta del sistema a múltiples canales
        """
        
        logger.info(f"Enviando alerta del sistema: {alert_type} - {message}")
        
        try:
            results = {}
            
            # 1. Slack para alertas críticas
            if severity in ["critical", "error"]:
                slack_result = await self.send_slack_notification(
                    channel="#system-alerts",
                    message=f"🚨 *{alert_type.upper()}*: {message}",
                    attachments=[{
                        "color": "danger" if severity == "critical" else "warning",
                        "fields": [
                            {"title": "Tipo", "value": alert_type, "short": True},
                            {"title": "Severidad", "value": severity, "short": True},
                            {"title": "Mensaje", "value": message, "short": False},
                            {"title": "Timestamp", "value": datetime.utcnow().isoformat(), "short": True}
                        ]
                    }],
                    db=db
                )
                results['slack'] = slack_result
            
            # 2. Email para alertas importantes
            if severity in ["critical", "error", "warning"]:
                email_recipients = settings.ALERT_EMAIL_RECIPIENTS
                if email_recipients:
                    email_result = await self.send_email_notification(
                        recipients=email_recipients,
                        subject=f"[{severity.upper()}] {alert_type}",
                        message=f"""
                        Alerta del Sistema:
                        
                        Tipo: {alert_type}
                        Severidad: {severity}
                        Mensaje: {message}
                        
                        Timestamp: {datetime.utcnow().isoformat()}
                        """,
                        db=db
                    )
                    results['email'] = email_result
            
            # Determinar éxito general
            all_success = all(result.success for result in results.values())
            total_sent = sum(result.sent_count for result in results.values())
            total_failed = sum(result.failed_count for result in results.values())
            
            return NotificationResult(
                success=all_success,
                message=f"Alerta del sistema enviada: {total_sent} notificaciones enviadas, {total_failed} fallos",
                sent_count=total_sent,
                failed_count=total_failed,
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error enviando alerta del sistema: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error enviando alerta del sistema: {str(e)}",
                failed_count=1
            )
    
    async def send_lead_assignment_notification(self,
                                             lead_id: int,
                                             assigned_to: str,
                                             db: Session = None) -> NotificationResult:
        """
        Notificación cuando un lead es asignado a un vendedor
        """
        
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return NotificationResult(
                    success=False,
                    message="Lead no encontrado",
                    failed_count=1
                )
            
            message = f"🎯 Nuevo lead asignado: {lead.name or lead.email} (Score: {lead.score})"
            details = f"""
            Lead asignado a: {assigned_to}
            Nombre: {lead.name or 'N/A'}
            Email: {lead.email}
            Compañía: {lead.company or 'N/A'}
            Score: {lead.score}
            Fuente: {lead.source}
            """
            
            # Enviar notificación Slack
            slack_result = await self.send_slack_notification(
                channel="#lead-assignments",
                message=message,
                attachments=[{
                    "color": "good",
                    "fields": [
                        {"title": "Lead", "value": lead.name or lead.email, "short": True},
                        {"title": "Score", "value": str(lead.score), "short": True},
                        {"title": "Asignado a", "value": assigned_to, "short": True},
                        {"title": "Compañía", "value": lead.company or "N/A", "short": True},
                        {"title": "Fuente", "value": lead.source, "short": True},
                        {"title": "Enlace", "value": f"{settings.APP_URL}/leads/{lead.id}", "short": False}
                    ]
                }],
                db=db
            )
            
            return slack_result
            
        except Exception as e:
            logger.error(f"Error en notificación de asignación: {str(e)}")
            return NotificationResult(
                success=False,
                message=f"Error en notificación de asignación: {str(e)}",
                failed_count=1
            )
    
    def _create_basic_email_template(self, subject: str, message: str, template_data: Dict) -> str:
        """Crea un template básico de email"""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f6f6f6; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
                .header {{ background: #3B82F6; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ padding: 20px; }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{subject}</h1>
                </div>
                <div class="content">
                    {message}
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático de {settings.COMPANY_NAME}</p>
                    <p>© {datetime.now().year} {settings.COMPANY_NAME}. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def _send_sms_via_provider(self, phone: str, message: str) -> bool:
        """
        Envía SMS usando el proveedor configurado
        Placeholder - implementar con Twilio u otro proveedor
        """
        
        # Ejemplo con Twilio:
        # from twilio.rest import Client
        # client = Client(self.sms_config['account_sid'], self.sms_config['auth_token'])
        # message = client.messages.create(
        #     body=message,
        #     from_=self.sms_config['from_number'],
        #     to=phone
        # )
        # return message.sid is not None
        
        logger.info(f"[SIMULADO] SMS enviado a {phone}: {message}")
        return True  # Simular éxito
    
    async def _log_notification(self,
                             db: Session,
                             notification_type: NotificationType,
                             message: str,
                             sent_count: int,
                             failed_count: int,
                             recipients: List[str]):
        """Registra notificación en el log"""
        
        log_entry = NotificationLog(
            notification_type=notification_type,
            message=message,
            recipients=recipients,
            sent_count=sent_count,
            failed_count=failed_count,
            status=NotificationStatus.SENT if failed_count == 0 else NotificationStatus.FAILED,
            created_at=datetime.utcnow()
        )
        
        db.add(log_entry)
        db.commit()

# ===========================================
# TAREAS CELERY
# ===========================================

# Instancia de Celery
celery_app = Celery("sales_automation")

@celery_app.task(name="email_notification_task")
def email_notification_task(recipients: List[str], subject: str, message: str):
    """Tarea Celery para notificación por email"""
    
    async def _send_email():
        db = next(get_db())
        try:
            manager = NotificationManager()
            result = await manager.send_email_notification(recipients, subject, message, None, db)
            logger.info(f"Notificación email completada: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_send_email())

@celery_app.task(name="slack_notification_task")
def slack_notification_task(channel: str, message: str):
    """Tarea Celery para notificación por Slack"""
    
    async def _send_slack():
        db = next(get_db())
        try:
            manager = NotificationManager()
            result = await manager.send_slack_notification(channel, message, None, db)
            logger.info(f"Notificación Slack completada: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_send_slack())

@celery_app.task(name="system_alert_task")
def system_alert_task(alert_type: str, message: str, severity: str = "warning"):
    """Tarea Celery para alertas del sistema"""
    
    async def _send_alert():
        db = next(get_db())
        try:
            manager = NotificationManager()
            result = await manager.send_system_alert(alert_type, message, severity, db)
            logger.info(f"Alerta del sistema enviada: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_send_alert())

@celery_app.task(name="lead_assignment_notification_task")
def lead_assignment_notification_task(lead_id: int, assigned_to: str):
    """Tarea Celery para notificación de asignación de lead"""
    
    async def _send_assignment():
        db = next(get_db())
        try:
            manager = NotificationManager()
            result = await manager.send_lead_assignment_notification(lead_id, assigned_to, db)
            logger.info(f"Notificación de asignación enviada: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_send_assignment())

# Instancia global
notification_manager = NotificationManager()