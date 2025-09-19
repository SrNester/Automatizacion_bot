import requests
from typing import Dict, List, Optional
from datetime import datetime
import json
from ...core.config import settings
from ...models.lead import Lead, Interaction

class HubSpotService:
    def __init__(self):
        self.api_key = settings.HUBSPOT_API_KEY
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    # CONTACTS - Gestión de Contactos
    async def create_or_update_contact(self, lead: Lead) -> Dict:
        """Crea o actualiza un contacto en HubSpot"""
        
        # Buscar si el contacto ya existe
        existing_contact = await self.find_contact_by_email(lead.email)
        
        contact_data = self._build_contact_properties(lead)
        
        if existing_contact:
            # Actualizar contacto existente
            contact_id = existing_contact['id']
            response = await self._update_contact(contact_id, contact_data)
            action = "updated"
        else:
            # Crear nuevo contacto
            response = await self._create_contact(contact_data)
            action = "created"
        
        # Guardar HubSpot ID en nuestro sistema
        if response and 'id' in response:
            lead.hubspot_id = response['id']
            
        return {
            "action": action,
            "hubspot_id": response.get('id') if response else None,
            "success": response is not None
        }
    
    async def find_contact_by_email(self, email: str) -> Optional[Dict]:
        """Busca un contacto por email en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        
        search_data = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            }],
            "properties": ["email", "firstname", "lastname", "company", "jobtitle"]
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=search_data)
            
            if response.status_code == 200:
                results = response.json()
                return results['results'][0] if results['results'] else None
            
            return None
            
        except Exception as e:
            print(f"Error buscando contacto: {e}")
            return None
    
    async def _create_contact(self, properties: Dict) -> Optional[Dict]:
        """Crea un nuevo contacto en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts"
        
        contact_data = {"properties": properties}
        
        try:
            response = requests.post(url, headers=self.headers, json=contact_data)
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"Error creando contacto: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error en API de HubSpot: {e}")
            return None
    
    async def _update_contact(self, contact_id: str, properties: Dict) -> Optional[Dict]:
        """Actualiza un contacto existente en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        
        update_data = {"properties": properties}
        
        try:
            response = requests.patch(url, headers=self.headers, json=update_data)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error actualizando contacto: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error actualizando contacto: {e}")
            return None
    
    def _build_contact_properties(self, lead: Lead) -> Dict:
        """Construye las propiedades del contacto para HubSpot"""
        
        properties = {
            "email": lead.email,
            "firstname": lead.name.split()[0] if lead.name else "",
            "lastname": " ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else "",
            "phone": lead.phone or "",
            "company": lead.company or "",
            "jobtitle": lead.job_title or "",
            
            # Propiedades personalizadas
            "lead_score": str(lead.score),
            "lead_status": lead.status,
            "lead_source": lead.source or "",
            "utm_campaign": lead.utm_campaign or "",
            "first_interaction_date": lead.first_interaction.isoformat() if lead.first_interaction else "",
            "budget_range": lead.budget_range or "",
            "timeline": lead.timeline or "",
            
            # Campos calculados
            "lifecycle_stage": self._map_lifecycle_stage(lead.status),
            "ai_qualification_score": str(lead.score)
        }
        
        return {k: v for k, v in properties.items() if v}  # Remover valores vacíos
    
    def _map_lifecycle_stage(self, lead_status: str) -> str:
        """Mapea nuestro status a lifecycle stages de HubSpot"""
        
        mapping = {
            "cold": "lead",
            "warm": "marketingqualifiedlead", 
            "hot": "salesqualifiedlead",
            "converted": "customer",
            "lost": "other"
        }
        
        return mapping.get(lead_status, "subscriber")
    
    # DEALS - Gestión de Oportunidades
    async def create_deal(self, lead: Lead, deal_data: Dict) -> Optional[Dict]:
        """Crea una oportunidad en HubSpot"""
        
        # Primero asegurar que el contacto existe
        contact_result = await self.create_or_update_contact(lead)
        
        if not contact_result['success']:
            return None
        
        url = f"{self.base_url}/crm/v3/objects/deals"
        
        properties = {
            "dealname": deal_data.get('name', f"Oportunidad - {lead.name}"),
            "amount": deal_data.get('amount', '0'),
            "dealstage": deal_data.get('stage', 'appointmentscheduled'),
            "pipeline": deal_data.get('pipeline', 'default'),
            "closedate": deal_data.get('close_date', ''),
            "deal_source": lead.source or '',
            "lead_score_at_creation": str(lead.score)
        }
        
        deal_payload = {"properties": properties}
        
        try:
            response = requests.post(url, headers=self.headers, json=deal_payload)
            
            if response.status_code == 201:
                deal = response.json()
                
                # Asociar deal con contacto
                await self._associate_deal_to_contact(deal['id'], contact_result['hubspot_id'])
                
                return deal
            else:
                print(f"Error creando deal: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error creando deal: {e}")
            return None
    
    async def _associate_deal_to_contact(self, deal_id: str, contact_id: str):
        """Asocia un deal con un contacto"""
        
        url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/deal_to_contact"
        
        try:
            response = requests.put(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"Error asociando deal a contacto: {e}")
            return False
    
    # ACTIVITIES - Registro de Actividades
    async def log_interaction(self, lead: Lead, interaction: Interaction) -> bool:
        """Registra una interacción como actividad en HubSpot"""
        
        # Mapear tipo de interacción a tipo de actividad de HubSpot
        activity_type = self._map_interaction_to_activity_type(interaction.type)
        
        if not activity_type:
            return False
        
        # Obtener el contact_id de HubSpot
        contact = await self.find_contact_by_email(lead.email)
        if not contact:
            return False
        
        url = f"{self.base_url}/crm/v3/objects/{activity_type}"
        
        properties = {
            "hs_activity_type": activity_type,
            "hs_timestamp": interaction.timestamp.isoformat(),
            "subject": f"Interacción AI Bot - {interaction.type}",
            "hs_body_preview": interaction.content[:200] if interaction.content else "",
            "sentiment_score": str(interaction.sentiment_score) if interaction.sentiment_score else ""
        }
        
        activity_data = {
            "properties": properties,
            "associations": [
                {
                    "to": {"id": contact['id']},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}]
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=activity_data)
            return response.status_code == 201
        except Exception as e:
            print(f"Error registrando actividad: {e}")
            return False
    
    def _map_interaction_to_activity_type(self, interaction_type: str) -> Optional[str]:
        """Mapea tipos de interacción a tipos de actividad de HubSpot"""
        
        mapping = {
            "email": "emails",
            "call": "calls", 
            "whatsapp": "communications",
            "website_visit": "communications",
            "download": "communications",
            "chat": "communications"
        }
        
        return mapping.get(interaction_type)
    
    # WEBHOOKS - Sincronización bidireccional
    async def setup_webhooks(self) -> bool:
        """Configura webhooks de HubSpot para sincronización bidireccional"""
        
        webhook_url = f"{settings.BASE_URL}/webhooks/hubspot"
        
        webhook_config = {
            "subscriptions": [
                {
                    "subscriptionDetails": {
                        "subscriptionType": "contact.propertyChange",
                        "propertyName": "email"
                    },
                    "enabled": True
                },
                {
                    "subscriptionDetails": {
                        "subscriptionType": "deal.creation"
                    },
                    "enabled": True
                },
                {
                    "subscriptionDetails": {
                        "subscriptionType": "deal.propertyChange",
                        "propertyName": "dealstage"
                    },
                    "enabled": True
                }
            ],
            "webhookUrl": webhook_url
        }
        
        url = f"{self.base_url}/webhooks/v3/{settings.HUBSPOT_APP_ID}/settings"
        
        try:
            response = requests.put(url, headers=self.headers, json=webhook_config)
            return response.status_code == 200
        except Exception as e:
            print(f"Error configurando webhooks: {e}")
            return False
    
    # SYNC UTILITIES
    async def sync_all_contacts(self, limit: int = 100) -> Dict:
        """Sincroniza todos los contactos desde HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts"
        
        params = {
            "limit": limit,
            "properties": ["email", "firstname", "lastname", "company", "jobtitle", "phone"]
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('results', [])
                
                sync_results = {
                    "total_contacts": len(contacts),
                    "synced": 0,
                    "errors": 0
                }
                
                for contact in contacts:
                    try:
                        # Convertir contacto de HubSpot a nuestro formato
                        # y crear/actualizar en nuestra BD
                        await self._sync_contact_to_local(contact)
                        sync_results["synced"] += 1
                    except Exception as e:
                        print(f"Error sincronizando contacto {contact.get('id')}: {e}")
                        sync_results["errors"] += 1
                
                return sync_results
            
            return {"error": "Failed to fetch contacts"}
            
        except Exception as e:
            return {"error": f"Sync failed: {e}"}
    
    async def _sync_contact_to_local(self, hubspot_contact: Dict):
        """Sincroniza un contacto de HubSpot a nuestra base de datos local"""
        
        properties = hubspot_contact.get('properties', {})
        
        # Aquí implementarías la lógica para crear/actualizar
        # el lead en tu base de datos local basado en los datos de HubSpot
        pass