# core/automation_bot.py
import time
import logging
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from enum import Enum

class BotState(Enum):
    STOPPED = "stopped"
    RUNNING = "running" 
    PAUSED = "paused"
    ERROR = "error"

class AutomationBot:
    def __init__(self):
        self.state = BotState.STOPPED
        self.active_sessions = []
        self.scheduled_tasks = []
        self.logger = self.setup_logger()
        self.performance_metrics = {}
        self.last_execution = None
        
        # Propiedades de estado para el método get_status()
        self.is_running = False
        self.is_paused = False
        self.current_platform = None
        self.current_action = None
        self.progress = 0
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.last_activity = datetime.now()
        self.start_time = None
        self.estimated_completion = None
        self.current_session_id = None
        self.status_message = "Bot listo para iniciar"
        self.error_message = None
        
        # CONECTAR CON TU BACKEND FASTAPI
        from core.fastapi_client import FastAPIClient
        self.api_client = FastAPIClient()
        
        # Datos simulados para fallback
        self.simulation_data = SimulationData()
        
        self.logger.info(f"Estado conexión FastAPI: {self.api_client.get_connection_status()}")
    
    def setup_logger(self):
        """Configurar logger"""
        logger = logging.getLogger('AutomationBot')
        if not logger.handlers:
            handler = logging.FileHandler('logs/automation_bot.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def get_status(self) -> Dict[str, Any]:
        """
        Obtener el estado actual del bot para el dashboard
        """
        try:
            # Sincronizar con el estado interno de la clase
            self.is_running = self.state == BotState.RUNNING
            self.is_paused = self.state == BotState.PAUSED
            
            return {
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'current_platform': self.current_platform,
                'current_action': self.current_action,
                'progress': self.progress,
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks,
                'last_activity': self.last_activity.isoformat() if self.last_activity else None,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
                'current_session_id': self.current_session_id,
                'status_message': self.status_message,
                'error_message': self.error_message,
                'state': self.state.value,
                'active_sessions_count': len(self.active_sessions),
                'scheduled_tasks_count': len(self.scheduled_tasks),
                'api_connection_status': self.api_client.get_connection_status(),
                'uptime': self._calculate_uptime()
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo estado del bot: {e}")
            return {
                'is_running': False,
                'is_paused': False,
                'current_platform': None,
                'current_action': None,
                'progress': 0,
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'last_activity': None,
                'start_time': None,
                'estimated_completion': None,
                'current_session_id': None,
                'status_message': f'Error obteniendo estado: {str(e)}',
                'error_message': str(e),
                'state': 'error',
                'active_sessions_count': 0,
                'scheduled_tasks_count': 0,
                'api_connection_status': {'is_connected': False},
                'uptime': 0
            }
    
    def _calculate_uptime(self) -> float:
        """Calcular tiempo de actividad desde el inicio"""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0
    
    def update_status(self, **kwargs):
        """Actualizar propiedades de estado"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_activity = datetime.now()
    
    def start_automation(self, config: Dict[str, Any]):
        """Iniciar automatización"""
        try:
            self.state = BotState.RUNNING
            self.update_status(
                is_running=True,
                is_paused=False,
                start_time=datetime.now(),
                current_platform=config.get('platform'),
                current_action=config.get('action'),
                status_message=f"Iniciando {config.get('action')} en {config.get('platform')}",
                error_message=None,
                progress=0,
                completed_tasks=0,
                failed_tasks=0
            )
            self.logger.info(f"Automatización iniciada: {config}")
            
        except Exception as e:
            self.state = BotState.ERROR
            self.update_status(
                status_message="Error al iniciar automatización",
                error_message=str(e)
            )
            self.logger.error(f"Error iniciando automatización: {e}")
    
    def stop_automation(self):
        """Detener automatización"""
        self.state = BotState.STOPPED
        self.update_status(
            is_running=False,
            is_paused=False,
            status_message="Automatización detenida",
            progress=100,
            current_platform=None,
            current_action=None
        )
        self.logger.info("Automatización detenida")
    
    def pause_automation(self):
        """Pausar automatización"""
        if self.state == BotState.RUNNING:
            self.state = BotState.PAUSED
            self.update_status(
                is_paused=True,
                status_message="Automatización pausada"
            )
            self.logger.info("Automatización pausada")
    
    def resume_automation(self):
        """Reanudar automatización"""
        if self.state == BotState.PAUSED:
            self.state = BotState.RUNNING
            self.update_status(
                is_paused=False,
                status_message="Automatización reanudada"
            )
            self.logger.info("Automatización reanudada")

    def execute_automation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar automatización - PRIMERO intentar con backend REAL"""
        try:
            platform = config.get('platform', '')
            action = config.get('action', '')
            
            self.logger.info(f"Ejecutando: {action} en {platform}")
            
            # Actualizar estado durante la ejecución
            self.update_status(
                current_platform=platform,
                current_action=action,
                status_message=f"Ejecutando {action}..."
            )
            
            # USAR BACKEND REAL si está disponible y es una acción de sales
            if (self.api_client.is_connected and 
                platform in ["Sales Automation", "FastAPI Backend"]):
                return self._execute_real_sales_automation(config)
            else:
                # Usar simulación para e-commerce
                return self._execute_simulation(config)
                
        except Exception as e:
            error_msg = f"Error en ejecución: {str(e)}"
            self.logger.error(error_msg)
            self.update_status(
                status_message="Error en ejecución",
                error_message=error_msg,
                failed_tasks=self.failed_tasks + 1
            )
            return {
                "success": False, 
                "error": error_msg,
                "products_processed": 0,
                "duration": 0,
                "errors": 1,
                "is_real_data": False
            }

    def _execute_real_sales_automation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar automatización usando tu backend FastAPI"""
        action = config.get('action', '')
        
        # MAPEAR ACCIONES A TU BACKEND FASTAPI
        if action == "Capturar Lead":
            return self._execute_capture_lead(config)
        elif action == "Chat con Lead":
            return self._execute_chat_lead(config)
        elif action == "Sincronizar HubSpot":
            return self._execute_hubspot_sync(config)
        elif action == "Analizar Leads":
            return self._execute_analyze_leads(config)
        elif action == "Nurturing Sequence":
            return self._execute_nurturing(config)
        elif action == "Crear Oportunidad":
            return self._execute_create_deal(config)
        else:
            return self._execute_general_sales_action(config)

    def _execute_capture_lead(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar captura de lead usando tu backend"""
        try:
            lead_data = {
                "name": config.get('name', 'Lead desde Dashboard'),
                "email": config.get('email', ''),
                "phone": config.get('phone', ''),
                "company": config.get('company', ''),
                "source": config.get('source', 'dashboard'),
                "tags": config.get('tags', []),
                "metadata": config.get('metadata', {})
            }
            
            result = self.api_client.capture_lead(lead_data)
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": result.get('success', False),
                "lead_id": result.get('lead_id'),
                "score": result.get('score', 0),
                "message": result.get('message', 'Lead procesado'),
                "is_real_data": True,
                "products_processed": 1,
                "duration": 2.5,
                "errors": 0 if result.get('success') else 1,
                "data": result
            }
            
        except Exception as e:
            self.logger.error(f"Error capturando lead: {e}")
            return self._fallback_simulation(config)

    def _execute_chat_lead(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar chat con lead usando tu IA Assistant"""
        try:
            lead_id = config.get('lead_id')
            message = config.get('message', 'Hola')
            
            if not lead_id:
                return {
                    "success": False,
                    "error": "Se requiere lead_id para chat",
                    "is_real_data": False
                }
            
            result = self.api_client.send_chat_message(lead_id, message)
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": True,
                "response": result.get('response', ''),
                "lead_score": result.get('lead_score', 0),
                "message": "Mensaje enviado exitosamente",
                "is_real_data": True,
                "products_processed": 1,
                "duration": 3.2,
                "errors": 0,
                "data": result
            }
            
        except Exception as e:
            self.logger.error(f"Error en chat: {e}")
            return self._fallback_simulation(config)

    def _execute_hubspot_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar sincronización con HubSpot"""
        try:
            lead_id = config.get('lead_id')
            
            if lead_id:
                result = self.api_client.sync_lead_to_hubspot(lead_id)
                message = f"Lead {lead_id} sincronizado"
            else:
                result = self.api_client.trigger_bulk_sync()
                message = "Sincronización masiva iniciada"
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": result.get('success', False),
                "message": result.get('message', message),
                "is_real_data": True,
                "products_processed": 1,
                "duration": 4.1,
                "errors": 0 if result.get('success') else 1,
                "data": result
            }
            
        except Exception as e:
            self.logger.error(f"Error en sync HubSpot: {e}")
            return self._fallback_simulation(config)

    def _execute_analyze_leads(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar análisis de leads"""
        try:
            analytics = self.api_client.get_dashboard_analytics()
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": True,
                "analytics": analytics,
                "message": f"Análisis completado: {analytics.get('total_leads', 0)} leads",
                "is_real_data": True,
                "products_processed": analytics.get('total_leads', 0),
                "duration": 1.8,
                "errors": 0,
                "data": analytics
            }
            
        except Exception as e:
            self.logger.error(f"Error analizando leads: {e}")
            return self._fallback_simulation(config)

    def _execute_nurturing(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar secuencia de nurturing"""
        try:
            lead_id = config.get('lead_id')
            sequence_type = config.get('sequence_type', 'default')
            
            result = self.api_client.trigger_nurturing(lead_id, sequence_type)
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": result.get('success', False),
                "message": result.get('message', 'Nurturing iniciado'),
                "is_real_data": True,
                "products_processed": 1,
                "duration": 2.3,
                "errors": 0 if result.get('success') else 1,
                "data": result
            }
            
        except Exception as e:
            self.logger.error(f"Error en nurturing: {e}")
            return self._fallback_simulation(config)

    def _execute_create_deal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crear oportunidad en HubSpot"""
        try:
            lead_id = config.get('lead_id')
            deal_data = {
                "deal_name": config.get('deal_name', 'Nueva Oportunidad'),
                "amount": config.get('amount', 0),
                "stage": config.get('stage', 'qualifiedtobuy'),
                "priority": config.get('priority', 'medium')
            }
            
            result = self.api_client.create_hubspot_deal(lead_id, deal_data)
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return {
                "success": result.get('success', False),
                "deal_id": result.get('deal_id'),
                "message": result.get('message', 'Oportunidad creada'),
                "is_real_data": True,
                "products_processed": 1,
                "duration": 3.5,
                "errors": 0 if result.get('success') else 1,
                "data": result
            }
            
        except Exception as e:
            self.logger.error(f"Error creando oportunidad: {e}")
            return self._fallback_simulation(config)

    def _execute_general_sales_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecución genérica para acciones de sales no mapeadas"""
        return self._fallback_simulation(config)

    def _execute_simulation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar simulación para e-commerce"""
        try:
            # Simular tiempo de procesamiento
            processing_time = random.uniform(2.0, 8.0)
            time.sleep(min(processing_time, 3.0))
            
            # Generar resultados simulados
            result = self.simulation_data.generate_simulation_result(config)
            result["is_real_data"] = False
            
            # Actualizar progreso
            self.completed_tasks += 1
            self.progress = (self.completed_tasks / max(self.total_tasks, 1)) * 100
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error en simulación: {e}")
            return self._fallback_simulation(config)

    def _fallback_simulation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback a simulación si hay error"""
        result = self.simulation_data.generate_simulation_result(config)
        result["is_real_data"] = False
        
        # Actualizar contadores de error
        self.failed_tasks += 1
        
        return result

    def get_connection_status(self) -> Dict[str, Any]:
        """Obtener estado de la conexión"""
        api_status = self.api_client.get_connection_status()
        
        return {
            "backend_type": "FastAPI",
            "is_connected": api_status["is_connected"],
            "base_url": api_status["base_url"],
            "last_check": api_status["last_check"],
            "available_endpoints": [
                "/webhook/lead", "/chat/message", "/dashboard/analytics",
                "/hubspot/sync-lead", "/hubspot/sync-status", "/leads/{id}",
                "/hubspot/create-deal", "/leads/{id}/nurture"
            ]
        }

class SimulationData:
    """Generador de datos simulados para e-commerce (fallback)"""
    
    def __init__(self):
        self.products_db = self._initialize_product_database()
        self.competitors = self._initialize_competitors()
        
    def _initialize_product_database(self):
        """Base de datos de productos simulados"""
        return {
            "electronics": [
                {"name": "iPhone 15 Pro", "base_price": 24999, "category": "smartphone"},
                {"name": "Samsung Galaxy S24", "base_price": 18999, "category": "smartphone"},
                {"name": "MacBook Air M2", "base_price": 32999, "category": "laptop"},
            ],
            "home": [
                {"name": "Nintendo Switch", "base_price": 7999, "category": "gaming"},
                {"name": "PlayStation 5", "base_price": 12999, "category": "gaming"},
            ]
        }
    
    def _initialize_competitors(self):
        """Competidores simulados"""
        return {
            "TechStoreMX": {"rating": 4.7, "shipping_speed": "1-2 días"},
            "ElectroWorld": {"rating": 4.5, "shipping_speed": "2-3 días"},
        }
    
    def generate_simulation_result(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generar resultado de simulación"""
        platform = config.get('platform', 'Mercado Libre')
        action = config.get('action', 'Monitorear Precios')
        
        # Simular diferentes resultados basados en la acción
        if "Monitorear" in action:
            return {
                "success": True,
                "products_processed": 25,
                "duration": 45.2,
                "errors": 0,
                "message": f"Monitoreo de precios completado en {platform}",
                "data_extracted": {
                    "products_found": 25,
                    "price_changes": 3,
                    "out_of_stock": 2
                }
            }
        elif "Actualizar" in action:
            return {
                "success": True,
                "products_processed": 18,
                "duration": 32.1,
                "errors": 1,
                "message": f"Actualización de inventario completada en {platform}",
                "data_extracted": {
                    "updated_products": 17,
                    "failed_updates": 1,
                    "new_listings": 2
                }
            }
        else:
            return {
                "success": True,
                "products_processed": random.randint(15, 40),
                "duration": random.uniform(20.0, 60.0),
                "errors": random.randint(0, 2),
                "message": f"Acción {action} completada exitosamente en {platform}",
                "data_extracted": {
                    "operation": action,
                    "items_processed": random.randint(15, 40),
                    "efficiency": random.randint(85, 98)
                }
            }