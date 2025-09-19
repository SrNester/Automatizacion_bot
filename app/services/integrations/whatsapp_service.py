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
                          message_type: str = "text") -> Dict:
        """
        Envía un mensaje de texto por WhatsApp
        
        Args:
            to: Número de teléfono del destinatario
            message: Contenido del mensaje
            message_type: Tipo de mensaje (text, template, etc.)
            
        Returns:
            dict: Respuesta de la API de WhatsApp
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
                        print(f"✅ Mensaje WhatsApp enviado a {to}")
                        return {"success": True, "data": result}
                    else:
                        print(f"❌ Error enviando mensaje WhatsApp: {result}")
                        return {"success": False, "error": result}
                        
        except Exception as e:
            print(f"❌ Excepción enviando mensaje WhatsApp: {e}")
            return {"success": False, "error": str(e)}

    async def send_template_message(self, 
                                  to: str, 
                                  template_name: str, 
                                  language_code: str = "es",
                                  parameters: List[str] = None) -> Dict:
        """
        Envía un mensaje template por WhatsApp
        
        Args:
            to: Número de teléfono
            template_name: Nombre del template aprobado
            language_code: Código de idioma (es, en, etc.)
            parameters: Parámetros para el template
        """
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        template_payload = {
            "name": template_name,
            "language": {"code": language_code}
        }
        
        if parameters:
            template_payload["components"] = [{
                "type": "body",
                "parameters": [{"type": "text", "text": param} for param in parameters]
            }]
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template_payload
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print(f"✅ Template WhatsApp enviado a {to}: {template_name}")
                        return {"success": True, "data": result}
                    else:
                        print(f"❌ Error enviando template WhatsApp: {result}")
                        return {"success": False, "error": result}
                        
        except Exception as e:
            print(f"❌ Excepción enviando template WhatsApp: {e}")
            return {"success": False, "error": str(e)}

    async def send_interactive_message(self, 
                                     to: str, 
                                     header: str,
                                     body: str,
                                     footer: str,
                                     buttons: List[Dict]) -> Dict:
        """
        Envía un mensaje interactivo con botones
        
        Args:
            to: Número de teléfono
            header: Título del mensaje
            body: Cuerpo del mensaje
            footer: Pie del mensaje
            buttons: Lista de botones [{"id": "1", "title": "Opción 1"}]
        """
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        interactive_buttons = []
        for button in buttons[:3]:  # Máximo 3 botones
            interactive_buttons.append({
                "type": "reply",
                "reply": {
                    "id": button["id"],
                    "title": button["title"][:20]  # Máximo 20 caracteres
                }
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "footer": {"text": footer},
                "action": {
                    "buttons": interactive_buttons
                }
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print(f"✅ Mensaje interactivo WhatsApp enviado a {to}")
                        return {"success": True, "data": result}
                    else:
                        print(f"❌ Error enviando mensaje interactivo: {result}")
                        return {"success": False, "error": result}
                        
        except Exception as e:
            print(f"❌ Excepción enviando mensaje interactivo: {e}")
            return {"success": False, "error": str(e)}

    async def send_list_message(self, 
                              to: str,
                              header: str,
                              body: str,
                              button_text: str,
                              sections: List[Dict]) -> Dict:
        """
        Envía un mensaje de lista interactiva
        
        Args:
            to: Número de teléfono
            header: Título
            body: Descripción
            button_text: Texto del botón (ej: "Ver opciones")
            sections: Secciones con opciones
        """
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print(f"✅ Lista WhatsApp enviada a {to}")
                        return {"success": True, "data": result}
                    else:
                        print(f"❌ Error enviando lista: {result}")
                        return {"success": False, "error": result}
                        
        except Exception as e:
            print(f"❌ Excepción enviando lista: {e}")
            return {"success": False, "error": str(e)}

    async def mark_as_read(self, message_id: str) -> Dict:
        """Marca un mensaje como leído"""
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()
                    return {"success": response.status == 200, "data": result}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_media(self, media_id: str) -> Dict:
        """Obtiene información de un archivo multimedia"""
        
        url = f"{self.base_url}/{media_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    result = await response.json()
                    return {"success": response.status == 200, "data": result}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_product_list_sections(self, products: List[Dict]) -> List[Dict]:
        """
        Crea secciones para mensaje de lista con productos
        
        Args:
            products: Lista de productos con name, price, description
            
        Returns:
            List[Dict]: Secciones formateadas para WhatsApp
        """
        
        rows = []
        for i, product in enumerate(products[:10]):  # Máximo 10 productos
            rows.append({
                "id": f"product_{i}",
                "title": product.get("name", "Producto")[:24],  # Máximo 24 chars
                "description": f"${product.get('price', 'Consultar')} - {product.get('description', '')[:72]}"  # Máximo 72 chars
            })
        
        return [{
            "title": "Nuestros Productos",
            "rows": rows
        }]

    def create_service_buttons(self) -> List[Dict]:
        """Crea botones para servicios comunes"""
        
        return [
            {"id": "info_productos", "title": "Ver Productos"},
            {"id": "agendar_demo", "title": "Agendar Demo"}, 
            {"id": "hablar_humano", "title": "Hablar con Humano"}
        ]

    async def send_welcome_message(self, to: str, lead_name: str = None) -> Dict:
        """Envía mensaje de bienvenida personalizado"""
        
        name = lead_name if lead_name else "¡Hola!"
        
        welcome_text = f"""
{name} 👋

Soy Sofia, tu asistente de automatización empresarial. 

¿En qué puedo ayudarte hoy?

🤖 Consultas sobre nuestros productos
📅 Agendar una demo personalizada  
💬 Hablar con un especialista
📊 Ver casos de éxito

¡Escríbeme lo que necesites!
        """.strip()
        
        buttons = self.create_service_buttons()
        
        return await self.send_interactive_message(
            to=to,
            header="¡Bienvenido a nuestra automatización!",
            body=welcome_text,
            footer="Automatización Inteligente · 24/7",
            buttons=buttons
        )

    async def send_products_list(self, to: str) -> Dict:
        """Envía lista de productos disponibles"""
        
        products = [
            {
                "name": "Automatización CRM",
                "price": "299/mes",
                "description": "Lead scoring, email automation, reporting"
            },
            {
                "name": "Chatbot IA Premium",
                "price": "199/mes", 
                "description": "Soporte 24/7, multi-idioma, WhatsApp"
            },
            {
                "name": "Analytics Suite",
                "price": "149/mes",
                "description": "Dashboard, reportes, métricas de conversión"
            }
        ]
        
        sections = self.create_product_list_sections(products)
        
        return await self.send_list_message(
            to=to,
            header="Nuestras Soluciones",
            body="Elige el producto que más te interese para recibir información detallada:",
            button_text="Ver Productos",
            sections=sections
        )

    async def health_check(self) -> Dict:
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
                            "verified_name": result.get("verified_name"),
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