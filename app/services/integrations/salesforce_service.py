import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...core.config import settings

class SalesforceService:
    """Servicio completo para integración con Salesforce CRM"""
    
    def __init__(self):
        self.access_token = settings.SALESFORCE_ACCESS_TOKEN
        self.instance_url = settings.SALESFORCE_INSTANCE_URL
        self.base_url = f"{self.instance_url}/services/data/v58.0"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la conexión con Salesforce"""
        
        url = f"{self.base_url}/sobjects/Contact"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "provider": "salesforce",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}: {error_text}",
                            "provider": "salesforce",
                            "timestamp": datetime.utcnow().isoformat()
                        }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": "salesforce",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def find_contact_by_email(self, email: str) -> Dict[str, Any]:
        """Busca un contacto por email en Salesforce"""
        
        url = f"{self.base_url}/query"
        params = {
            "q": f"SELECT Id, Name, Email, Phone, Company__c, Title, LeadSource FROM Contact WHERE Email = '{email}' LIMIT 1"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        records = result.get('records', [])
                        if records:
                            return {
                                "success": True,
                                "contact": records[0]
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
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
    
    async def find_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """Busca un contacto por teléfono en Salesforce"""
        
        url = f"{self.base_url}/query"
        params = {
            "q": f"SELECT Id, Name, Email, Phone, Company__c, Title, LeadSource FROM Contact WHERE Phone = '{phone}' LIMIT 1"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        records = result.get('records', [])
                        if records:
                            return {
                                "success": True,
                                "contact": records[0]
                            }
                        else:
                            return {
                                "success": True,
                                "contact": None
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
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo contacto en Salesforce"""
        
        url = f"{self.base_url}/sobjects/Contact"
        
        # Mapear campos a estructura de Salesforce
        sf_contact = {
            "LastName": contact_data.get("LastName", "Contact"),
            "FirstName": contact_data.get("FirstName", ""),
            "Email": contact_data.get("Email"),
            "Phone": contact_data.get("Phone"),
            "Company__c": contact_data.get("Company"),
            "Title": contact_data.get("Title"),
            "LeadSource": contact_data.get("LeadSource", "API"),
            "Lead_Score__c": contact_data.get("Lead_Score__c")
        }
        
        # Limpiar campos vacíos
        sf_contact = {k: v for k, v in sf_contact.items() if v is not None}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=sf_contact) as response:
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
        """Actualiza un contacto existente en Salesforce"""
        
        url = f"{self.base_url}/sobjects/Contact/{contact_id}"
        
        # Mapear campos a estructura de Salesforce
        sf_contact = {}
        
        field_mapping = {
            "FirstName": "FirstName",
            "LastName": "LastName", 
            "Email": "Email",
            "Phone": "Phone",
            "Company": "Company__c",
            "Title": "Title",
            "LeadSource": "LeadSource",
            "Lead_Score__c": "Lead_Score__c"
        }
        
        for internal_field, sf_field in field_mapping.items():
            if internal_field in contact_data and contact_data[internal_field] is not None:
                sf_contact[sf_field] = contact_data[internal_field]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=self.headers, json=sf_contact) as response:
                    if response.status == 204:
                        return {
                            "success": True,
                            "contact_id": contact_id
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
    
    async def create_opportunity(self, contact_id: str, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una oportunidad en Salesforce vinculada a un contacto"""
        
        url = f"{self.base_url}/sobjects/Opportunity"
        
        sf_opportunity = {
            "Name": opportunity_data.get("Name", "New Opportunity"),
            "StageName": opportunity_data.get("StageName", "Prospecting"),
            "CloseDate": opportunity_data.get("CloseDate", datetime.utcnow().strftime("%Y-%m-%d")),
            "Amount": opportunity_data.get("Amount", 0),
            "ContactId": contact_id,
            "LeadSource": opportunity_data.get("LeadSource", "API")
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=sf_opportunity) as response:
                    if response.status == 201:
                        result = await response.json()
                        return {
                            "success": True,
                            "opportunity_id": result.get('id'),
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
    
    async def get_contact_details(self, contact_id: str) -> Dict[str, Any]:
        """Obtiene detalles completos de un contacto"""
        
        url = f"{self.base_url}/sobjects/Contact/{contact_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "contact": result
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
    
    async def search_contacts(self, search_term: str, limit: int = 10) -> Dict[str, Any]:
        """Busca contactos por término de búsqueda"""
        
        url = f"{self.base_url}/query"
        query = f"""
        SELECT Id, Name, Email, Phone, Company__c, Title, LeadSource 
        FROM Contact 
        WHERE Name LIKE '%{search_term}%' 
        OR Email LIKE '%{search_term}%' 
        OR Phone LIKE '%{search_term}%'
        LIMIT {limit}
        """
        
        params = {"q": query}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "contacts": result.get('records', []),
                            "total_size": result.get('totalSize', 0)
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