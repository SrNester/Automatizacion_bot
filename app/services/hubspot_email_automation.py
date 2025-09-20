from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .integrations.hubspot_service import HubSpotService
from ..models.lead import Lead, LeadStatus
import requests

class HubSpotEmailAutomation:
    def __init__(self):
        self.hubspot = HubSpotService()
        self.email_templates = self._load_email_templates()
    
    def _load_email_templates(self) -> Dict:
        """Carga templates de email por score/status"""
        
        return {
            "score_upgrade": {
                "cold_to_warm": {
                    "template_id": "template_001",
                    "subject": "We noticed your increased interest - Let's talk!",
                    "trigger_score": 40
                },
                "warm_to_hot": {
                    "template_id": "template_002", 
                    "subject": "Ready for a personalized demo?",
                    "trigger_score": 70
                }
            },
            "score_based": {
                "high_score": {
                    "template_id": "template_003",
                    "subject": "Exclusive offer for qualified prospects",
                    "min_score": 80
                },
                "medium_score": {
                    "template_id": "template_004",
                    "subject": "See how others in your industry succeed",
                    "min_score": 50,
                    "max_score": 79
                }
            },
            "reactivation": {
                "dormant_leads": {
                    "template_id": "template_005",
                    "subject": "We miss you! Here's what's new",
                    "days_inactive": 14
                }
            }
        }
    
    async def trigger_score_based_email(self, lead: Lead, old_score: float, new_score: float):
        """Dispara emails basados en cambios de score"""
        
        # Email por upgrade de status
        old_status = self._score_to_status(old_score)
        new_status = self._score_to_status(new_score)
        
        if old_status != new_status and new_status in ["warm", "hot"]:
            await self._send_score_upgrade_email(lead, old_status, new_status)
        
        # Email por alcanzar score específico
        if new_score >= 80 and old_score < 80:
            await self._send_high_score_email(lead)
        elif 50 <= new_score < 80 and old_score < 50:
            await self._send_medium_score_email(lead)
    
    def _score_to_status(self, score: float) -> str:
        """Convierte score a status"""
        if score >= 70:
            return "hot"
        elif score >= 40:
            return "warm"
        else:
            return "cold"
    
    async def _send_score_upgrade_email(self, lead: Lead, old_status: str, new_status: str):
        """Envía email por upgrade de status"""
        
        template_key = f"{old_status}_to_{new_status}"
        template_config = self.email_templates["score_upgrade"].get(template_key)
        
        if not template_config:
            return
        
        # Crear email en HubSpot
        email_data = {
            "emailType": "AUTOMATED",
            "recipients": [{"contactId": lead.hubspot_id}],
            "templateId": template_config["template_id"],
            "customProperties": [
                {
                    "name": "lead_score",
                    "value": str(lead.score)
                },
                {
                    "name": "status_upgrade", 
                    "value": f"{old_status} → {new_status}"
                },
                {
                    "name": "first_name",
                    "value": lead.name.split()[0] if lead.name else "there"
                }
            ]
        }
        
        success = await self._send_hubspot_email(email_data)
        
        if success:
            await self._log_email_sent(lead.id, "score_upgrade", template_config["subject"])
    
    async def _send_high_score_email(self, lead: Lead):
        """Email para leads con score alto"""
        
        template_config = self.email_templates["score_based"]["high_score"]
        
        email_data = {
            "emailType": "AUTOMATED",
            "recipients": [{"contactId": lead.hubspot_id}],
            "templateId": template_config["template_id"],
            "customProperties": [
                {
                    "name": "lead_score",
                    "value": str(lead.score)
                },
                {
                    "name": "qualification_level",
                    "value": "Highly Qualified"
                }
            ]
        }
        
        success = await self._send_hubspot_email(email_data)
        
        if success:
            await self._log_email_sent(lead.id, "high_score", template_config["subject"])
    
    async def _send_medium_score_email(self, lead: Lead):
        """Email para leads con score medio"""
        
        template_config = self.email_templates["score_based"]["medium_score"]
        
        # Personalizar contenido basado en industria/intereses
        industry_content = await self._get_industry_specific_content(lead.company)
        
        email_data = {
            "emailType": "AUTOMATED",
            "recipients": [{"contactId": lead.hubspot_id}],
            "templateId": template_config["template_id"],
            "customProperties": [
                {
                    "name": "industry_content",
                    "value": industry_content
                },
                {
                    "name": "lead_score",
                    "value": str(lead.score)
                }
            ]
        }
        
        success = await self._send_hubspot_email(email_data)
        
        if success:
            await self._log_email_sent(lead.id, "medium_score", template_config["subject"])
    
    async def process_dormant_leads(self):
        """Procesa leads dormantes para reactivación"""
        
        # Buscar leads inactivos por más de 14 días
        cutoff_date = datetime.now() - timedelta(days=14)
        
        dormant_leads = await self._get_dormant_leads(cutoff_date)
        
        template_config = self.email_templates["reactivation"]["dormant_leads"]
        
        for lead in dormant_leads:
            # Personalizar reactivation email
            recent_content = await self._get_recent_content_for_lead(lead)
            
            email_data = {
                "emailType": "AUTOMATED",
                "recipients": [{"contactId": lead.hubspot_id}],
                "templateId": template_config["template_id"],
                "customProperties": [
                    {
                        "name": "days_inactive",
                        "value": str((datetime.now() - lead.last_interaction).days)
                    },
                    {
                        "name": "recent_content",
                        "value": recent_content
                    }
                ]
            }
            
            success = await self._send_hubspot_email(email_data)
            
            if success:
                await self._log_email_sent(lead.id, "reactivation", template_config["subject"])
    
    async def _send_hubspot_email(self, email_data: Dict) -> bool:
        """Envía email a través de la API de HubSpot"""
        
        url = f"{self.hubspot.base_url}/marketing/v3/emails/send"
        
        try:
            response = requests.post(
                url, 
                headers=self.hubspot.headers,
                json=email_data
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False
    
    async def _get_industry_specific_content(self, company: str) -> str:
        """Obtiene contenido específico por industria"""
        
        # Aquí podrías usar IA para determinar la industria y contenido relevante
        industry_mapping = {
            "tech": "Latest automation trends in technology",
            "healthcare": "Healthcare automation case studies",
            "finance": "Financial services automation solutions",
            "default": "Industry-leading automation solutions"
        }
        
        # Lógica simple para determinar industria
        if company:
            company_lower = company.lower()
            for industry, content in industry_mapping.items():
                if industry in company_lower:
                    return content
        
        return industry_mapping["default"]
    
    async def _get_recent_content_for_lead(self, lead: Lead) -> str:
        """Obtiene contenido reciente relevante para el lead"""
        
        # Basado en intereses del lead
        if lead.interests:
            return f"New updates on {lead.interests}"
        
        return "Latest product updates and success stories"
    
    async def _log_email_sent(self, lead_id: int, email_type: str, subject: str):
        """Registra el email enviado"""
        
        # Aquí registrarías en tu BD el email enviado
        print(f"Email sent to lead {lead_id}: {email_type} - {subject}")