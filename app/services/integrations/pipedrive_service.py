import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ...core.config import settings

class PipedriveService:
    """Servicio completo para integración con Pipedrive CRM"""
    
    def __init__(self):
        self.api_token = settings.PIPEDRIVE_API_TOKEN
        self.base_url = "https://api.pipedrive.com/v1"
        
        # Mapeo de campos personalizados (se configura dinámicamente)
        self.custom_fields = {
            "lead_score": None,
            "lead_source": None,
            "utm_campaign": None,
            "utm_source": None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la conexión con Pipedrive"""
        
        url = f"{self.base_url}/users/me"
        params = {"api_token": self.api_token}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        user_data = result.get("data", {})
                        return {
                            "status": "healthy",
                            "provider": "pipedrive",
                            "user_id": user_data.get("id"),
                            "user_name": user_data.get("name"),
                            "company": user_data.get("company_name"),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": result.get("error", "Authentication failed"),
                            "provider": "pipedrive",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": "pipedrive",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo contacto en Pipedrive"""
        
        url = f"{self.base_url}/persons"
        
        # Preparar datos para Pipedrive
        pipedrive_data = {
            "name": contact_data.get("name", ""),
            "email": contact_data.get("email"),
            "phone": contact_data.get("phone"),
            "org_name": contact_data.get("company", ""),
            "api_token": self.api_token
        }
        
        # Agregar campos personalizados si están configurados
        if self.custom_fields["lead_score"] and contact_data.get("lead_score"):
            pipedrive_data[self.custom_fields["lead_score"]] = contact_data["lead_score"]
        
        if self.custom_fields["lead_source"] and contact_data.get("lead_source"):
            pipedrive_data[self.custom_fields["lead_source"]] = contact_data["lead_source"]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=pipedrive_data) as response:
                    result = await response.json()
                    
                    if response.status == 201 and result.get("success"):
                        contact_id = result["data"]["id"]
                        return {
                            "success": True,
                            "contact_id": contact_id,
                            "data": result["data"]
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un contacto existente en Pipedrive"""
        
        url = f"{self.base_url}/persons/{contact_id}"
        
        # Preparar datos actualizados
        pipedrive_data = {
            "api_token": self.api_token
        }
        
        # Mapear campos básicos
        if "name" in contact_data:
            pipedrive_data["name"] = contact_data["name"]
        
        if "email" in contact_data:
            pipedrive_data["email"] = contact_data["email"]
        
        if "phone" in contact_data:
            pipedrive_data["phone"] = contact_data["phone"]
        
        if "company" in contact_data:
            pipedrive_data["org_name"] = contact_data["company"]
        
        # Campos personalizados
        if self.custom_fields["lead_score"] and "lead_score" in contact_data:
            pipedrive_data[self.custom_fields["lead_score"]] = contact_data["lead_score"]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=pipedrive_data) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        return {
                            "success": True,
                            "contact_id": contact_id,
                            "data": result["data"]
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def find_contact_by_email(self, email: str) -> Dict[str, Any]:
        """Busca un contacto por email"""
        
        url = f"{self.base_url}/persons/search"
        params = {
            "term": email,
            "fields": "email",
            "exact_match": True,
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        items = result.get("data", {}).get("items", [])
                        
                        if items:
                            contact = items[0].get("item", {})
                            return {
                                "success": True,
                                "contact": {
                                    "id": contact.get("id"),
                                    "name": contact.get("name"),
                                    "email": email,
                                    "phone": self._extract_phone_from_contact(contact),
                                    "company": contact.get("org_name"),
                                    "owner_id": contact.get("owner_id")
                                }
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Search failed")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def find_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """Busca un contacto por teléfono"""
        
        url = f"{self.base_url}/persons/search"
        params = {
            "term": phone,
            "fields": "phone",
            "exact_match": True,
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        items = result.get("data", {}).get("items", [])
                        
                        if items:
                            contact = items[0].get("item", {})
                            return {
                                "success": True,
                                "contact": {
                                    "id": contact.get("id"),
                                    "name": contact.get("name"),
                                    "email": self._extract_email_from_contact(contact),
                                    "phone": phone,
                                    "company": contact.get("org_name"),
                                    "owner_id": contact.get("owner_id")
                                }
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Search failed")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_email_from_contact(self, contact: Dict) -> Optional[str]:
        """Extrae el email de un contacto"""
        return contact.get("email")
    
    def _extract_phone_from_contact(self, contact: Dict) -> Optional[str]:
        """Extrae el teléfono de un contacto"""
        return contact.get("phone")
    
    async def create_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo deal en Pipedrive"""
        
        url = f"{self.base_url}/deals"
        
        pipedrive_data = {
            "title": deal_data.get("title", "New Deal"),
            "value": deal_data.get("value", 0),
            "currency": deal_data.get("currency", "USD"),
            "person_id": deal_data.get("person_id"),
            "org_id": deal_data.get("org_id"),
            "pipeline_id": deal_data.get("pipeline_id", 1),  # Pipeline por defecto
            "stage_id": deal_data.get("stage_id", 1),  # Stage por defecto
            "status": deal_data.get("status", "open"),
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=pipedrive_data) as response:
                    result = await response.json()
                    
                    if response.status == 201 and result.get("success"):
                        deal_id = result["data"]["id"]
                        return {
                            "success": True,
                            "deal_id": deal_id,
                            "data": result["data"]
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_pipelines(self) -> List[Dict[str, Any]]:
        """Obtiene todos los pipelines disponibles"""
        
        url = f"{self.base_url}/pipelines"
        params = {"api_token": self.api_token}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        return result.get("data", [])
                    else:
                        return []
                        
        except Exception as e:
            return []
    
    async def get_pipeline_stages(self, pipeline_id: int) -> List[Dict[str, Any]]:
        """Obtiene las etapas de un pipeline específico"""
        
        url = f"{self.base_url}/stages"
        params = {
            "pipeline_id": pipeline_id,
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        return result.get("data", [])
                    else:
                        return []
                        
        except Exception as e:
            return []
    
    async def get_custom_fields(self) -> Dict[str, List[Dict]]:
        """Obtiene los campos personalizados disponibles"""
        
        endpoints = {
            "person": f"{self.base_url}/personFields",
            "deal": f"{self.base_url}/dealFields",
            "organization": f"{self.base_url}/organizationFields"
        }
        
        all_custom_fields = {}
        
        for entity_type, url in endpoints.items():
            params = {"api_token": self.api_token}
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        result = await response.json()
                        
                        if response.status == 200 and result.get("success"):
                            custom_fields = [
                                field for field in result.get("data", [])
                                if field.get("key", "").startswith(("custom_", "cf_")) or 
                                   field.get("field_type") == "custom"
                            ]
                            all_custom_fields[entity_type] = custom_fields
                        else:
                            all_custom_fields[entity_type] = []
                            
            except Exception as e:
                all_custom_fields[entity_type] = []
        
        return all_custom_fields
    
    async def configure_custom_fields(self) -> Dict[str, str]:
        """Configura automáticamente los campos personalizados"""
        
        custom_fields = await self.get_custom_fields()
        person_fields = custom_fields.get("person", [])
        
        configured_fields = {}
        
        field_mapping = {
            "lead_score": ["lead_score", "score", "lead score", "puntaje"],
            "lead_source": ["lead_source", "source", "fuente", "origen"],
            "utm_campaign": ["utm_campaign", "campaign", "campaña"],
            "utm_source": ["utm_source", "utm source", "fuente utm"]
        }
        
        for internal_name, possible_names in field_mapping.items():
            for field in person_fields:
                field_name = field.get("name", "").lower()
                field_key = field.get("key", "")
                
                if any(name.lower() in field_name for name in possible_names):
                    configured_fields[internal_name] = field_key
                    self.custom_fields[internal_name] = field_key
                    break
        
        return configured_fields
    
    async def create_activity(self, activity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una actividad/tarea en Pipedrive"""
        
        url = f"{self.base_url}/activities"
        
        pipedrive_data = {
            "subject": activity_data.get("subject", "Follow up"),
            "type": activity_data.get("type", "call"),
            "due_date": activity_data.get("due_date"),
            "due_time": activity_data.get("due_time"),
            "person_id": activity_data.get("person_id"),
            "deal_id": activity_data.get("deal_id"),
            "note": activity_data.get("note", ""),
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=pipedrive_data) as response:
                    result = await response.json()
                    
                    if response.status == 201 and result.get("success"):
                        activity_id = result["data"]["id"]
                        return {
                            "success": True,
                            "activity_id": activity_id,
                            "data": result["data"]
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """Obtiene actividades recientes"""
        
        url = f"{self.base_url}/activities"
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "start": 0,
            "limit": 100,
            "since": since_date,
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        return result.get("data", [])
                    else:
                        return []
                        
        except Exception as e:
            return []
    
    async def setup_webhook(self, webhook_url: str, events: List[str] = None) -> Dict[str, Any]:
        """Configura webhook para recibir eventos de Pipedrive"""
        
        url = f"{self.base_url}/webhooks"
        
        webhook_data = {
            "subscription_url": webhook_url,
            "event_action": "*",
            "event_object": "*",
            "api_token": self.api_token
        }
        
        if events:
            webhook_data["event_action"] = ",".join(events)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=webhook_data) as response:
                    result = await response.json()
                    
                    if response.status == 201 and result.get("success"):
                        webhook_id = result["data"]["id"]
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "data": result["data"]
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa un evento recibido via webhook"""
        
        try:
            event_type = event_data.get("event")
            object_type = event_data.get("object")
            object_id = event_data.get("id")
            
            if object_type == "person" and event_type in ["added", "updated"]:
                return await self._handle_person_event(object_id, event_type, event_data)
            elif object_type == "deal" and event_type in ["added", "updated"]:
                return await self._handle_deal_event(object_id, event_type, event_data)
            elif object_type == "activity" and event_type == "added":
                return await self._handle_activity_event(object_id, event_data)
            else:
                return {
                    "success": True,
                    "message": f"Evento {event_type} {object_type} procesado"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_person_event(self, person_id: str, event_type: str, event_data: Dict) -> Dict[str, Any]:
        """Maneja eventos de personas (contactos)"""
        
        person_data = event_data.get("current", {})
        return {
            "success": True,
            "message": f"Persona {event_type} procesada",
            "person_id": person_id,
            "person_name": person_data.get("name")
        }
    
    async def _handle_deal_event(self, deal_id: str, event_type: str, event_data: Dict) -> Dict[str, Any]:
        """Maneja eventos de deals (oportunidades)"""
        
        deal_data = event_data.get("current", {})
        return {
            "success": True,
            "message": f"Deal {event_type} procesado",
            "deal_id": deal_id,
            "deal_title": deal_data.get("title"),
            "person_id": deal_data.get("person_id"),
            "status": deal_data.get("status")
        }
    
    async def _handle_activity_event(self, activity_id: str, event_data: Dict) -> Dict[str, Any]:
        """Maneja eventos de actividades"""
        
        activity_data = event_data.get("current", {})
        return {
            "success": True,
            "message": "Actividad procesada",
            "activity_id": activity_id,
            "person_id": activity_data.get("person_id"),
            "type": activity_data.get("type")
        }
    
    async def get_deals_summary(self, days: int = 30) -> Dict[str, Any]:
        """Obtiene resumen de deals para analytics"""
        
        url = f"{self.base_url}/deals"
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "start": 0,
            "limit": 500,
            "since": since_date,
            "api_token": self.api_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("success"):
                        deals = result.get("data", [])
                        
                        total_deals = len(deals)
                        won_deals = len([d for d in deals if d.get("status") == "won"])
                        lost_deals = len([d for d in deals if d.get("status") == "lost"])
                        open_deals = total_deals - won_deals - lost_deals
                        
                        total_value = sum(float(d.get("value", 0)) for d in deals)
                        won_value = sum(float(d.get("value", 0)) for d in deals if d.get("status") == "won")
                        
                        win_rate = won_deals / total_deals if total_deals > 0 else 0
                        
                        return {
                            "period_days": days,
                            "total_deals": total_deals,
                            "won_deals": won_deals,
                            "lost_deals": lost_deals,
                            "open_deals": open_deals,
                            "win_rate": win_rate,
                            "total_value": total_value,
                            "won_value": won_value,
                            "avg_deal_size": total_value / total_deals if total_deals > 0 else 0
                        }
                    else:
                        return {"error": "Failed to fetch deals"}
                        
        except Exception as e:
            return {"error": str(e)}