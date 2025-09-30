import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import aiohttp
import asyncio
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from .integrations.hubspot_service import HubSpotService
from ..models.integration import Lead, LeadStatus, IntegrationProvider
from ..models.workflow import EmailSend, EmailTemplate
from ..core.database import get_db
from ..core.config import settings

logger = logging.getLogger(__name__)

class HubSpotEmailAutomation:
    """Servicio de automatización de emails integrado con HubSpot con mejoras robustas"""
    
    def __init__(self, db_session: Session = None):
        self.hubspot = HubSpotService()
        self.db = db_session
        self.email_templates = self._load_email_templates()
        self.rate_limit_delay = 0.2  # 200ms entre llamadas a HubSpot
        self.max_retries = 3
        
    def _load_email_templates(self) -> Dict[str, Any]:
        """Carga templates de email por score/status con configuración robusta"""
        
        return {
            "score_upgrade": {
                "cold_to_warm": {
                    "template_id": "template_001",
                    "subject": "We noticed your increased interest - Let's talk!",
                    "trigger_score": 40,
                    "category": "score_upgrade",
                    "priority": 1
                },
                "warm_to_hot": {
                    "template_id": "template_002", 
                    "subject": "Ready for a personalized demo?",
                    "trigger_score": 70,
                    "category": "score_upgrade",
                    "priority": 2
                },
                "cold_to_hot": {
                    "template_id": "template_006",
                    "subject": "Impressive progress! Let's accelerate your success",
                    "trigger_score": 70,
                    "category": "score_upgrade", 
                    "priority": 3
                }
            },
            "score_based": {
                "high_score": {
                    "template_id": "template_003",
                    "subject": "Exclusive offer for qualified prospects",
                    "min_score": 80,
                    "max_score": 100,
                    "category": "score_based",
                    "priority": 1
                },
                "medium_score": {
                    "template_id": "template_004",
                    "subject": "See how others in your industry succeed",
                    "min_score": 50,
                    "max_score": 79,
                    "category": "score_based",
                    "priority": 2
                },
                "low_score_engagement": {
                    "template_id": "template_007", 
                    "subject": "Getting started with automation? We can help!",
                    "min_score": 20,
                    "max_score": 49,
                    "category": "score_based",
                    "priority": 3
                }
            },
            "reactivation": {
                "dormant_leads": {
                    "template_id": "template_005",
                    "subject": "We miss you! Here's what's new",
                    "days_inactive": 14,
                    "max_days_inactive": 30,
                    "category": "reactivation",
                    "priority": 1
                },
                "high_value_dormant": {
                    "template_id": "template_008",
                    "subject": "Your expertise is valuable - Let's reconnect",
                    "days_inactive": 7,
                    "min_score": 60,
                    "category": "reactivation", 
                    "priority": 2
                }
            },
            "behavioral": {
                "frequent_visitor": {
                    "template_id": "template_009",
                    "subject": "We see you're interested - Need more information?",
                    "min_visits": 5,
                    "category": "behavioral",
                    "priority": 1
                },
                "content_engaged": {
                    "template_id": "template_010",
                    "subject": "Based on your interests - Here's more you might like",
                    "min_content_views": 3,
                    "category": "behavioral",
                    "priority": 2
                }
            }
        }
    
    async def trigger_score_based_email(self, lead: Lead, old_score: float, new_score: float, db: Session = None) -> Dict[str, Any]:
        """Dispara emails basados en cambios de score con manejo robusto de errores"""
        
        if not db:
            db = self.db or next(get_db())
        
        try:
            # Validar lead y configuración
            if not lead or not lead.email:
                return {"success": False, "error": "Lead inválido o sin email"}
            
            if not lead.hubspot_id:
                logger.warning(f"Lead {lead.id} no tiene HubSpot ID, saltando email automation")
                return {"success": False, "error": "Lead no sincronizado con HubSpot"}
            
            results = {
                "lead_id": lead.id,
                "old_score": old_score,
                "new_score": new_score,
                "emails_triggered": [],
                "errors": []
            }
            
            # Email por upgrade de status
            status_result = await self._handle_status_upgrade(lead, old_score, new_score, db)
            if status_result:
                results["emails_triggered"].append(status_result)
            
            # Email por alcanzar score específico
            score_result = await self._handle_score_thresholds(lead, old_score, new_score, db)
            if score_result:
                results["emails_triggered"].extend(score_result)
            
            # Verificar si necesita reactivación
            reactivation_result = await self._check_reactivation_needed(lead, db)
            if reactivation_result:
                results["emails_triggered"].append(reactivation_result)
            
            results["success"] = len(results["emails_triggered"]) > 0
            return results
            
        except Exception as e:
            logger.error(f"Error en trigger_score_based_email para lead {lead.id}: {e}")
            return {"success": False, "error": str(e), "lead_id": lead.id}
    
    async def _handle_status_upgrade(self, lead: Lead, old_score: float, new_score: float, db: Session) -> Optional[Dict]:
        """Maneja upgrades de status del lead"""
        
        old_status = self._score_to_status(old_score)
        new_status = self._score_to_status(new_score)
        
        if old_status == new_status:
            return None
        
        # Determinar template key basado en la transición
        template_key = f"{old_status}_to_{new_status}"
        
        # Para saltos directos (ej: cold to hot)
        if old_status == "cold" and new_status == "hot":
            template_key = "cold_to_hot"
        
        template_config = self.email_templates["score_upgrade"].get(template_key)
        
        if not template_config:
            logger.debug(f"No template config encontrado para transición: {template_key}")
            return None
        
        # Verificar que el nuevo score alcance el trigger
        if new_score < template_config["trigger_score"]:
            return None
        
        # Enviar email de upgrade
        result = await self._send_score_upgrade_email(lead, old_status, new_status, template_config, db)
        
        if result["success"]:
            logger.info(f"Email de upgrade enviado a lead {lead.id}: {old_status} → {new_status}")
            return {
                "type": "status_upgrade",
                "template_key": template_key,
                "old_status": old_status,
                "new_status": new_status,
                "email_send_id": result.get("email_send_id")
            }
        
        return None
    
    async def _handle_score_thresholds(self, lead: Lead, old_score: float, new_score: float, db: Session) -> List[Dict]:
        """Maneja cruces de thresholds de score"""
        
        triggered_emails = []
        
        for template_key, config in self.email_templates["score_based"].items():
            min_score = config.get("min_score", 0)
            max_score = config.get("max_score", 100)
            
            # Verificar si el nuevo score está en el rango y el old_score no
            if (min_score <= new_score <= max_score and 
                not (min_score <= old_score <= max_score)):
                
                result = await self._send_threshold_email(lead, template_key, config, db)
                
                if result["success"]:
                    triggered_emails.append({
                        "type": "score_threshold",
                        "template_key": template_key,
                        "threshold": f"{min_score}-{max_score}",
                        "email_send_id": result.get("email_send_id")
                    })
        
        return triggered_emails
    
    async def _check_reactivation_needed(self, lead: Lead, db: Session) -> Optional[Dict]:
        """Verifica si el lead necesita email de reactivación"""
        
        if not lead.last_interaction:
            return None
        
        days_inactive = (datetime.utcnow() - lead.last_interaction).days
        
        for template_key, config in self.email_templates["reactivation"].items():
            min_days = config.get("days_inactive", 14)
            max_days = config.get("max_days_inactive", 365)
            
            # Verificar score mínimo si está configurado
            min_score = config.get("min_score", 0)
            if lead.score < min_score:
                continue
            
            if min_days <= days_inactive <= max_days:
                result = await self._send_reactivation_email(lead, template_key, config, days_inactive, db)
                
                if result["success"]:
                    return {
                        "type": "reactivation",
                        "template_key": template_key,
                        "days_inactive": days_inactive,
                        "email_send_id": result.get("email_send_id")
                    }
        
        return None
    
    def _score_to_status(self, score: float) -> str:
        """Convierte score a status con thresholds configurables"""
        if score >= 70:
            return "hot"
        elif score >= 40:
            return "warm"
        else:
            return "cold"
    
    async def _send_score_upgrade_email(self, lead: Lead, old_status: str, new_status: str, 
                                      template_config: Dict, db: Session) -> Dict[str, Any]:
        """Envía email por upgrade de status con personalización"""
        
        try:
            # Preparar datos de personalización
            personalization_data = {
                "lead_score": str(lead.score),
                "status_upgrade": f"{old_status} → {new_status}",
                "first_name": self._extract_first_name(lead.name),
                "new_status": new_status,
                "improvement_percentage": self._calculate_improvement_percentage(lead)
            }
            
            # Enviar email a través de HubSpot
            email_data = await self._prepare_hubspot_email_data(
                lead, template_config, personalization_data
            )
            
            success = await self._send_hubspot_email(email_data)
            
            # Registrar envío en base de datos
            if success:
                email_send = await self._log_email_sent(
                    lead, "score_upgrade", template_config["subject"], 
                    template_config["template_id"], db
                )
                return {"success": True, "email_send_id": email_send.id}
            else:
                return {"success": False, "error": "Error enviando email a HubSpot"}
                
        except Exception as e:
            logger.error(f"Error enviando email de upgrade para lead {lead.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_threshold_email(self, lead: Lead, template_key: str, 
                                  template_config: Dict, db: Session) -> Dict[str, Any]:
        """Envía email por alcanzar threshold de score"""
        
        try:
            # Obtener contenido específico por industria
            industry_content = await self._get_industry_specific_content(lead.company)
            
            personalization_data = {
                "lead_score": str(lead.score),
                "industry_content": industry_content,
                "qualification_level": self._get_qualification_level(lead.score),
                "first_name": self._extract_first_name(lead.name)
            }
            
            email_data = await self._prepare_hubspot_email_data(
                lead, template_config, personalization_data
            )
            
            success = await self._send_hubspot_email(email_data)
            
            if success:
                email_send = await self._log_email_sent(
                    lead, template_key, template_config["subject"],
                    template_config["template_id"], db
                )
                return {"success": True, "email_send_id": email_send.id}
            else:
                return {"success": False, "error": "Error enviando email a HubSpot"}
                
        except Exception as e:
            logger.error(f"Error enviando email de threshold para lead {lead.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_reactivation_email(self, lead: Lead, template_key: str, 
                                     template_config: Dict, days_inactive: int, 
                                     db: Session) -> Dict[str, Any]:
        """Envía email de reactivación para leads dormantes"""
        
        try:
            # Obtener contenido relevante basado en intereses del lead
            recent_content = await self._get_recent_content_for_lead(lead)
            
            personalization_data = {
                "days_inactive": str(days_inactive),
                "recent_content": recent_content,
                "first_name": self._extract_first_name(lead.name),
                "last_engagement": lead.last_interaction.strftime("%B %d, %Y") if lead.last_interaction else "a while ago"
            }
            
            email_data = await self._prepare_hubspot_email_data(
                lead, template_config, personalization_data
            )
            
            success = await self._send_hubspot_email(email_data)
            
            if success:
                email_send = await self._log_email_sent(
                    lead, "reactivation", template_config["subject"],
                    template_config["template_id"], db
                )
                return {"success": True, "email_send_id": email_send.id}
            else:
                return {"success": False, "error": "Error enviando email a HubSpot"}
                
        except Exception as e:
            logger.error(f"Error enviando email de reactivación para lead {lead.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _prepare_hubspot_email_data(self, lead: Lead, template_config: Dict, 
                                        personalization_data: Dict) -> Dict[str, Any]:
        """Prepara los datos para el email de HubSpot"""
        
        return {
            "emailType": "AUTOMATED",
            "recipients": [{"contactId": lead.hubspot_id}],
            "templateId": template_config["template_id"],
            "customProperties": [
                {"name": key, "value": str(value)} 
                for key, value in personalization_data.items()
            ],
            "metadata": {
                "lead_id": lead.id,
                "template_category": template_config.get("category", "unknown"),
                "trigger_type": "score_based",
                "sent_via": "hubspot_automation"
            }
        }
    
    async def _send_hubspot_email(self, email_data: Dict) -> bool:
        """Envía email a través de la API de HubSpot con reintentos y manejo de errores"""
        
        url = f"{self.hubspot.base_url}/marketing/v3/emails/send"
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, 
                        headers=self.hubspot.headers,
                        json=email_data,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        if response.status == 200:
                            logger.info(f"Email enviado exitosamente a HubSpot")
                            return True
                        elif response.status == 429:  # Rate limiting
                            retry_after = int(response.headers.get('Retry-After', 60))
                            logger.warning(f"Rate limit alcanzado, reintentando en {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"Error HubSpot API: {response.status} - {error_text}")
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                            return False
                            
            except aiohttp.ClientError as e:
                logger.error(f"Error de conexión con HubSpot (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return False
            except Exception as e:
                logger.error(f"Error inesperado enviando email a HubSpot: {e}")
                return False
        
        return False
    
    def _extract_first_name(self, full_name: Optional[str]) -> str:
        """Extrae el primer nombre del lead"""
        if not full_name:
            return "there"
        
        # Remover títulos y extraer primer nombre
        titles = ["sr", "sra", "srta", "dr", "lic", "ing", "mr", "ms", "mrs"]
        name_parts = full_name.split()
        clean_parts = [part for part in name_parts if part.lower() not in titles]
        
        return clean_parts[0] if clean_parts else "there"
    
    def _calculate_improvement_percentage(self, lead: Lead) -> str:
        """Calcula porcentaje de mejora para personalización"""
        # Esta sería una implementación más sofisticada en producción
        if lead.score > 70:
            return "significant"
        elif lead.score > 40:
            return "moderate"
        else:
            return "notable"
    
    def _get_qualification_level(self, score: float) -> str:
        """Determina nivel de calificación para personalización"""
        if score >= 80:
            return "Highly Qualified"
        elif score >= 60:
            return "Well Qualified" 
        elif score >= 40:
            return "Qualified"
        else:
            return "Interested"
    
    async def _get_industry_specific_content(self, company: str) -> str:
        """Obtiene contenido específico por industria usando IA o mapeo avanzado"""
        
        if not company:
            return "industry-leading automation solutions"
        
        # Mapeo más sofisticado de industrias
        industry_mapping = {
            "tech": ["tech", "software", "saas", "it", "technology"],
            "healthcare": ["health", "medical", "hospital", "clinic", "pharma"],
            "finance": ["bank", "financial", "insurance", "investment", "fintech"],
            "education": ["school", "university", "education", "learning"],
            "retail": ["retail", "store", "shop", "ecommerce"],
            "manufacturing": ["manufacturing", "factory", "production"]
        }
        
        company_lower = company.lower()
        
        for industry, keywords in industry_mapping.items():
            if any(keyword in company_lower for keyword in keywords):
                content_map = {
                    "tech": "Latest automation trends and AI innovations in technology",
                    "healthcare": "Healthcare automation solutions that improve patient care",
                    "finance": "Financial services automation for compliance and efficiency", 
                    "education": "Education technology automation for enhanced learning",
                    "retail": "Retail automation for inventory and customer experience",
                    "manufacturing": "Manufacturing automation for production optimization"
                }
                return content_map.get(industry, "industry-specific automation solutions")
        
        return "tailored automation solutions for your business"
    
    async def _get_recent_content_for_lead(self, lead: Lead) -> str:
        """Obtiene contenido reciente relevante para el lead basado en intereses"""
        
        # En producción, esto se integraría con el sistema de contenido
        if lead.interests:
            interests = lead.interests if isinstance(lead.interests, str) else str(lead.interests)
            return f"New content and updates related to {interests}"
        
        # Basado en industria de la compañía
        if lead.company:
            industry = await self._get_industry_specific_content(lead.company)
            return f"Recent developments in {industry}"
        
        return "Latest product updates and customer success stories"
    
    async def _log_email_sent(self, lead: Lead, email_type: str, subject: str, 
                            template_id: str, db: Session) -> EmailSend:
        """Registra el email enviado en la base de datos"""
        
        try:
            email_send = EmailSend(
                lead_id=lead.id,
                to_email=lead.email,
                subject=subject,
                provider='hubspot',
                provider_message_id=f"hubspot_auto_{datetime.utcnow().timestamp()}",
                status='sent',
                sent_at=datetime.utcnow(),
                metadata={
                    "email_type": email_type,
                    "template_id": template_id,
                    "hubspot_contact_id": lead.hubspot_id,
                    "automation_trigger": "score_based",
                    "lead_score": lead.score
                }
            )
            
            db.add(email_send)
            db.commit()
            db.refresh(email_send)
            
            logger.info(f"Email registrado en BD: {email_type} para lead {lead.id}")
            return email_send
            
        except SQLAlchemyError as e:
            logger.error(f"Error registrando email en BD: {e}")
            db.rollback()
            raise
    
    async def process_dormant_leads_batch(self, days_inactive: int = 14, batch_size: int = 100, db: Session = None) -> Dict[str, Any]:
        """Procesa leads dormantes en lote para reactivación"""
        
        if not db:
            db = self.db or next(get_db())
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
            
            # Buscar leads inactivos con HubSpot ID
            dormant_leads = db.query(Lead).filter(
                Lead.last_interaction < cutoff_date,
                Lead.hubspot_id.isnot(None),
                Lead.email_unsubscribed == False,
                Lead.email_bounced == False
            ).limit(batch_size).all()
            
            results = {
                "total_processed": len(dormant_leads),
                "emails_sent": 0,
                "errors": [],
                "batch_size": batch_size,
                "days_inactive": days_inactive
            }
            
            for lead in dormant_leads:
                try:
                    reactivation_result = await self._check_reactivation_needed(lead, db)
                    if reactivation_result:
                        results["emails_sent"] += 1
                except Exception as e:
                    results["errors"].append(f"Lead {lead.id}: {str(e)}")
            
            results["success"] = results["emails_sent"] > 0
            logger.info(f"Procesamiento de leads dormantes completado: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error procesando leads dormantes: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_email_automation_stats(self, days: int = 30, db: Session = None) -> Dict[str, Any]:
        """Obtiene estadísticas de la automatización de emails"""
        
        if not db:
            db = self.db or next(get_db())
        
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Estadísticas por tipo de email
            stats = db.query(
                EmailSend.metadata['email_type'].astext.label('email_type'),
                func.count(EmailSend.id).label('total_sent'),
                func.sum(case([(EmailSend.opened_at.isnot(None), 1)], else_=0)).label('opened'),
                func.sum(case([(EmailSend.first_clicked_at.isnot(None), 1)], else_=0)).label('clicked')
            ).filter(
                EmailSend.sent_at > since_date,
                EmailSend.provider == 'hubspot',
                EmailSend.metadata.has_key('email_type')
            ).group_by('email_type').all()
            
            # Conversiones por tipo de email
            conversion_stats = {}
            for email_type in ['score_upgrade', 'reactivation', 'score_based']:
                leads_converted = db.query(Lead).filter(
                    Lead.created_at > since_date,
                    Lead.status == LeadStatus.CONVERTED.value,
                    Lead.id.in_(
                        db.query(EmailSend.lead_id).filter(
                            EmailSend.metadata['email_type'].astext == email_type,
                            EmailSend.sent_at > since_date - timedelta(days=7)
                        )
                    )
                ).count()
                
                conversion_stats[email_type] = leads_converted
            
            return {
                "period_days": days,
                "email_stats": [
                    {
                        "email_type": stat.email_type,
                        "total_sent": stat.total_sent,
                        "open_rate": stat.opened / stat.total_sent if stat.total_sent > 0 else 0,
                        "click_rate": stat.clicked / stat.total_sent if stat.total_sent > 0 else 0
                    }
                    for stat in stats
                ],
                "conversion_stats": conversion_stats,
                "template_configs": {
                    category: len(templates) 
                    for category, templates in self.email_templates.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    def update_template_config(self, category: str, template_key: str, new_config: Dict):
        """Actualiza la configuración de un template"""
        
        if category in self.email_templates and template_key in self.email_templates[category]:
            self.email_templates[category][template_key].update(new_config)
            logger.info(f"Template {category}.{template_key} actualizado")
        else:
            raise ValueError(f"Template {category}.{template_key} no encontrado")

# Función de utilidad para crear instancia
def create_hubspot_email_automation(db_session: Session = None) -> HubSpotEmailAutomation:
    return HubSpotEmailAutomation(db_session=db_session)