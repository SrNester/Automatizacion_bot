import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...core.config import settings

class WhatsAppService:
    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.base_url = f"https://graph.facebook.com/v17.0"
        
    async def send_message(self, 
                          to: str, 
                          message: str, 
                          message_type: str = "text") -> Dict[str, Any]:
        """
        Envía un mensaje de texto por WhatsApp
        """
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": message_type,
            "text": {
                "body": message
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        return {"success": True, "data": result}
                    else:
                        return {"success": False, "error": result}
                        
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la API de WhatsApp"""
        
        url = f"{self.base_url}/{self.phone_number_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "status": "healthy",
                            "phone_number_id": self.phone_number_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            "status": "unhealthy", 
                            "error": f"HTTP {response.status}",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }