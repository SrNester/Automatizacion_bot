# core/fastapi_client.py - VERSIÓN MEJORADA
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

class FastAPIClient:
    """Cliente mejorado para conectarse a tu backend FastAPI"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.logger = self.setup_logger()
        self.session = requests.Session()
        self.is_connected = False
        self.connection_error = None
        self.test_connection()
    
    def setup_logger(self):
        """Configurar logger"""
        logger = logging.getLogger('FastAPIClient')
        if not logger.handlers:
            handler = logging.FileHandler('logs/fastapi_client.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def test_connection(self):
        """Probar conexión con el backend FastAPI"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                self.is_connected = True
                self.connection_error = None
                self.logger.info(" Conectado al backend FastAPI")
                return True
            else:
                self.connection_error = f"Backend respondió con código: {response.status_code}"
                self.logger.warning(f" {self.connection_error}")
                return False
        except requests.exceptions.ConnectionError as e:
            self.connection_error = f"No se pudo conectar al backend: {e}"
            self.logger.error(f" {self.connection_error}")
            return False
        except Exception as e:
            self.connection_error = f"Error probando conexión: {e}"
            self.logger.error(f" {self.connection_error}")
            return False
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Método helper para hacer requests con manejo de errores"""
        if not self.is_connected:
            self.test_connection()  # Reintentar conexión
        
        if not self.is_connected:
            return {
                "success": False,
                "error": self.connection_error or "Backend no disponible",
                "is_fallback": True
            }
        
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.request(method, url, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            self.is_connected = False
            return {
                "success": False,
                "error": "Error de conexión con el backend",
                "is_fallback": True
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout en la conexión con el backend",
                "is_fallback": True
            }
        except requests.exceptions.HTTPError as e:
            return {
                "success": False,
                "error": f"Error HTTP {e.response.status_code}: {e.response.text}",
                "is_fallback": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error inesperado: {str(e)}",
                "is_fallback": True
            }
    
    def get_dashboard_analytics(self) -> Dict[str, Any]:
        """Obtener analytics del dashboard"""
        result = self._make_request("GET", "/dashboard/analytics")
        if result.get("is_fallback"):
            return self._get_fallback_analytics()
        return result
    
    def capture_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Capturar nuevo lead"""
        result = self._make_request("POST", "/webhook/lead", json=lead_data)
        if result.get("is_fallback"):
            return self._get_fallback_lead_response(lead_data)
        return result
    
    def send_chat_message(self, lead_id: int, message: str) -> Dict[str, Any]:
        """Enviar mensaje al chatbot"""
        message_data = {
            "lead_id": lead_id,
            "message": message,
            "conversation_id": f"conv_{datetime.now().timestamp()}"
        }
        result = self._make_request("POST", "/chat/message", json=message_data)
        if result.get("is_fallback"):
            return self._get_fallback_chat_response(message)
        return result
    
    def get_lead_details(self, lead_id: int) -> Dict[str, Any]:
        """Obtener detalles de un lead"""
        result = self._make_request("GET", f"/leads/{lead_id}")
        if result.get("is_fallback"):
            return self._get_fallback_lead_details(lead_id)
        return result
    
    def sync_lead_to_hubspot(self, lead_id: int) -> Dict[str, Any]:
        """Sincronizar lead con HubSpot"""
        result = self._make_request("POST", f"/hubspot/sync-lead/{lead_id}")
        if result.get("is_fallback"):
            return self._get_fallback_sync_response(lead_id)
        return result
    
    def get_hubspot_sync_status(self) -> Dict[str, Any]:
        """Obtener estado de sincronización con HubSpot"""
        result = self._make_request("GET", "/hubspot/sync-status")
        if result.get("is_fallback"):
            return self._get_fallback_sync_status()
        return result
    
    def trigger_bulk_sync(self) -> Dict[str, Any]:
        """Disparar sincronización masiva"""
        result = self._make_request("POST", "/hubspot/bulk-sync")
        if result.get("is_fallback"):
            return self._get_fallback_bulk_sync()
        return result
    
    def trigger_nurturing(self, lead_id: int, sequence_type: str = "default") -> Dict[str, Any]:
        """Disparar secuencia de nurturing"""
        result = self._make_request("POST", f"/leads/{lead_id}/nurture", params={"sequence_type": sequence_type})
        if result.get("is_fallback"):
            return self._get_fallback_nurturing(lead_id)
        return result
    
    def create_hubspot_deal(self, lead_id: int, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crear oportunidad en HubSpot"""
        result = self._make_request("POST", f"/hubspot/create-deal/{lead_id}", json=deal_data)
        if result.get("is_fallback"):
            return self._get_fallback_deal_response(deal_data)
        return result
    
    # Métodos de fallback para cuando el backend no está disponible
    def _get_fallback_analytics(self) -> Dict[str, Any]:
        return {
            "total_leads": 45,
            "hot_leads": 12,
            "conversion_rate": 15.5,
            "top_sources": [
                {"source": "website", "count": 15},
                {"source": "social_media", "count": 12},
                {"source": "referral", "count": 8}
            ],
            "average_score": 67.8,
            "is_fallback": True
        }
    
    def _get_fallback_lead_response(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "lead_id": 999,
            "score": 75,
            "message": f"Lead {lead_data.get('name', 'demo')} capturado en modo demo",
            "is_fallback": True
        }
    
    def _get_fallback_chat_response(self, message: str) -> Dict[str, Any]:
        responses = [
            "¡Hola! Estamos en modo demostración. En producción, me conectaría con tu IA real para ayudarte mejor.",
            "Interesante pregunta. En un entorno real, analizaría esto con tu historial de leads y datos de comportamiento.",
            "Gracias por tu mensaje. El sistema de IA procesaría esto para darte una respuesta personalizada.",
            "Excelente consulta. En producción, usaría machine learning para optimizar la respuesta.",
            "Entiendo tu necesidad. El sistema real aprendería de esta interacción para mejorar futuras conversaciones."
        ]
        import random
        return {
            "response": random.choice(responses),
            "lead_score": random.randint(60, 85),
            "is_fallback": True
        }
    
    def _get_fallback_lead_details(self, lead_id: int) -> Dict[str, Any]:
        return {
            "lead": {
                "id": lead_id,
                "name": f"Lead Demo {lead_id}",
                "email": f"lead{lead_id}@demo.com",
                "score": 75,
                "source": "demo",
                "status": "active"
            },
            "interactions": [
                {"message": "Mensaje inicial", "response": "Bienvenido al sistema", "timestamp": "2024-01-15T10:00:00"},
                {"message": "Consulta sobre servicios", "response": "Te puedo ayudar con...", "timestamp": "2024-01-15T10:05:00"}
            ],
            "is_fallback": True
        }
    
    def _get_fallback_sync_response(self, lead_id: int) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Lead {lead_id} marcado para sincronización (modo demo)",
            "is_fallback": True
        }
    
    def _get_fallback_sync_status(self) -> Dict[str, Any]:
        return {
            "total_leads": 45,
            "synced_to_hubspot": 32,
            "pending_sync": 13,
            "sync_percentage": 71.1,
            "hubspot_configured": False,
            "is_fallback": True
        }
    
    def _get_fallback_bulk_sync(self) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "Sincronización masiva iniciada en modo demo",
            "is_fallback": True
        }
    
    def _get_fallback_nurturing(self, lead_id: int) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Secuencia de nurturing iniciada para lead {lead_id} (demo)",
            "is_fallback": True
        }
    
    def _get_fallback_deal_response(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "deal_id": f"deal_{int(datetime.now().timestamp())}",
            "deal_name": deal_data.get('deal_name', 'Demo Deal'),
            "message": "Oportunidad creada en modo demostración",
            "is_fallback": True
        }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Obtener estado detallado de la conexión"""
        return {
            "is_connected": self.is_connected,
            "base_url": self.base_url,
            "last_check": datetime.now().isoformat(),
            "error": self.connection_error,
            "mode": "real" if self.is_connected else "demo"
        }