import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...core.config import settings
from ...models.integration import Lead
from ...models.interaction import Interaction

class HubSpotService:
    def __init__(self):
        self.api_key = settings.HUBSPOT_API_KEY
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la conexión con HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts"
        params = {"limit": 1}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "provider": "hubspot",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}",
                            "provider": "hubspot",
                            "timestamp": datetime.utcnow().isoformat()
                        }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": "hubspot",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def find_contact_by_email(self, email: str) -> Dict[str, Any]:
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
            "properties": ["email", "firstname", "lastname", "company", "phone", "lifecyclestage"]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=search_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        contacts = result.get('results', [])
                        if contacts:
                            return {
                                "success": True,
                                "contact": contacts[0]
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def find_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """Busca un contacto por teléfono en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        
        search_data = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "phone",
                    "operator": "EQ",
                    "value": phone
                }]
            }],
            "properties": ["email", "firstname", "lastname", "company", "phone", "lifecyclestage"]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=search_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        contacts = result.get('results', [])
                        if contacts:
                            return {
                                "success": True,
                                "contact": contacts[0]
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo contacto en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts"
        
        # Preparar propiedades para HubSpot
        properties = {}
        for key, value in contact_data.items():
            if value is not None:
                properties[key] = str(value)
        
        payload = {
            "properties": properties
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    if response.status == 201:
                        result = await response.json()
                        return {
                            "success": True,
                            "contact_id": result.get('id'),
                            "data": result
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un contacto existente en HubSpot"""
        
        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        
        # Preparar propiedades para HubSpot
        properties = {}
        for key, value in contact_data.items():
            if value is not None:
                properties[key] = str(value)
        
        payload = {
            "properties": properties
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "contact_id": contact_id,
                            "data": result
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_contact_properties(self, lead: Lead) -> Dict[str, str]:
        """Construye las propiedades del contacto para HubSpot"""
        
        # Dividir nombre si es necesario
        first_name = ""
        last_name = ""
        if lead.name:
            name_parts = lead.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        properties = {
            "email": lead.email or "",
            "firstname": first_name,
            "lastname": last_name,
            "phone": lead.phone or "",
            "company": lead.company or "",
            "jobtitle": lead.job_title or "",
            "lifecyclestage": self._map_lifecycle_stage(lead.status),
            "hs_lead_source": lead.source or "api",
        }
        
        # Agregar score si existe
        if lead.score is not None:
            properties["hs_score"] = str(lead.score)
        
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
        
        return mapping.get(lead_status, "lead")