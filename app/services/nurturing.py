from datetime import datetime, timedelta
from typing import List, Dict
import openai
from ..core.config import settings
from .integrations.email_service import EmailService
from .integrations.whatsapp_service import WhatsAppService

class NurturingService:
    def __init__(self):
        self.email_service = EmailService()
        self.whatsapp_service = WhatsAppService()
        openai.api_key = settings.OPENAI_API_KEY
    
    async def create_nurturing_sequence(self, lead: Dict, sequence_type: str):
        """Crea una secuencia de nurturing personalizada"""
        
        sequences = {
            "new_lead": self._get_new_lead_sequence(),
            "download_followup": self._get_download_sequence(),
            "demo_followup": self._get_demo_sequence(),
            "cold_reactivation": self._get_reactivation_sequence()
        }
        
        sequence = sequences.get(sequence_type, sequences["new_lead"])
        
        for step in sequence:
            await self._schedule_message(lead, step)
    
    def _get_new_lead_sequence(self) -> List[Dict]:
        """Secuencia para leads nuevos"""
        return [
            {
                "delay_days": 0,
                "channel": "email",
                "template": "welcome",
                "personalize": True
            },
            {
                "delay_days": 2,
                "channel": "email",
                "template": "value_content",
                "personalize": True
            },
            {
                "delay_days": 5,
                "channel": "whatsapp",
                "template": "check_in",
                "personalize": True
            },
            {
                "delay_days": 10,
                "channel": "email",
                "template": "case_study",
                "personalize": True
            }
        ]
    
    async def _schedule_message(self, lead: Dict, step: Dict):
        """Programa el envío de un mensaje"""
        send_time = datetime.now() + timedelta(days=step["delay_days"])
        
        if step["personalize"]:
            content = await self._personalize_content(lead, step["template"])
        else:
            content = self._get_template_content(step["template"])
        
        # Aquí programarías la tarea en Celery
        if step["channel"] == "email":
            await self.email_service.schedule_email(
                to=lead["email"],
                subject=content["subject"],
                body=content["body"],
                send_at=send_time
            )
        elif step["channel"] == "whatsapp":
            await self.whatsapp_service.schedule_message(
                to=lead["phone"],
                message=content["message"],
                send_at=send_time
            )
    
    async def _personalize_content(self, lead: Dict, template: str) -> Dict:
        """Personaliza el contenido usando IA"""
        
        prompt = f"""
        Personaliza este email para:
        Nombre: {lead.get('name', 'Usuario')}
        Empresa: {lead.get('company', 'No especificada')}
        Cargo: {lead.get('job_title', 'No especificado')}
        Intereses: {lead.get('interests', 'Automatización')}
        
        Template: {template}
        
        Genera un email profesional, personalizado y relevante.
        Incluye asunto y cuerpo del mensaje.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400
            )
            
            # Parsear respuesta (implementar lógica de parsing)
            content = response.choices[0].message.content
            
            return {
                "subject": "Asunto personalizado",
                "body": content,
                "message": content
            }
            
        except Exception as e:
            return self._get_template_content(template)