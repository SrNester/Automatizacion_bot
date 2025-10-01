import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import threading
import json

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
        self.next_execution = None
        
    def setup_logger(self):
        """Configurar logger para AutomationBot"""
        logger = logging.getLogger('AutomationBot')
        if not logger.handlers:
            handler = logging.FileHandler('logs/automation_bot.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def get_status(self) -> Dict[str, Any]:
        """Obtener estado actual del bot"""
        return {
            "state": self.state.value,
            "active_sessions": len(self.active_sessions),
            "scheduled_tasks": len(self.scheduled_tasks),
            "last_execution": self.last_execution.strftime("%Y-%m-%d %H:%M:%S") if self.last_execution else "Nunca",
            "next_execution": self.next_execution.strftime("%Y-%m-%d %H:%M:%S") if self.next_execution else "No programado",
            "performance_metrics": self.performance_metrics
        }

    def execute_automation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar una automatización específica"""
        try:
            if self.state == BotState.PAUSED:
                return {"success": False, "error": "Bot está pausado"}
            
            self.logger.info(f"Iniciando automatización: {config.get('action')} en {config.get('platform')}")
            
            # Simular ejecución (en una implementación real aquí iría Selenium)
            result = self.simulate_automation_execution(config)
            
            if result["success"]:
                self.last_execution = datetime.now()
                self.update_performance_metrics(result)
                self.logger.info(f"Automatización completada exitosamente: {result}")
            else:
                self.logger.error(f"Error en automatización: {result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error crítico en automatización: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def simulate_automation_execution(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Simular ejecución de automatización (para demo)"""
        platform = config.get('platform', 'Unknown')
        action = config.get('action', 'Unknown')
        
        # Simular diferentes resultados basados en la acción
        if "Monitorear" in action:
            return {
                "success": True,
                "products_processed": 25,
                "duration": 45.2,
                "errors": 0,
                "data_extracted": {
                    "products_found": 25,
                    "price_changes": 3,
                    "out_of_stock": 2
                },
                "message": f"Monitoreo de precios completado en {platform}"
            }
        elif "Actualizar" in action:
            return {
                "success": True,
                "products_processed": 18,
                "duration": 32.1,
                "errors": 1,
                "data_extracted": {
                    "updated_products": 17,
                    "failed_updates": 1,
                    "new_listings": 2
                },
                "message": f"Actualización de inventario completada en {platform}"
            }
        elif "Buscar" in action:
            return {
                "success": True,
                "products_processed": 50,
                "duration": 28.5,
                "errors": 0,
                "data_extracted": {
                    "search_results": 50,
                    "new_opportunities": 12,
                    "trending_products": 5
                },
                "message": f"Búsqueda de productos completada en {platform}"
            }
        else:
            # Simular fallo ocasional
            import random
            if random.random() < 0.2:  # 20% de probabilidad de fallo
                return {
                    "success": False,
                    "products_processed": 0,
                    "duration": 15.3,
                    "errors": 3,
                    "error": f"Error de conexión con {platform}",
                    "message": f"Fallo en {action} para {platform}"
                }
            else:
                return {
                    "success": True,
                    "products_processed": 30,
                    "duration": 35.7,
                    "errors": 0,
                    "message": f"{action} completada exitosamente en {platform}"
                }

    def schedule_task(self, task_config: Dict[str, Any]) -> str:
        """Programar una tarea automatizada"""
        task_id = f"TASK_{len(self.scheduled_tasks) + 1:04d}"
        
        task = {
            "id": task_id,
            "config": task_config,
            "scheduled_time": datetime.now() + timedelta(minutes=task_config.get('delay_minutes', 0)),
            "status": "scheduled",
            "created_at": datetime.now()
        }
        
        self.scheduled_tasks.append(task)
        self.logger.info(f"Tarea programada: {task_id}")
        
        # En una implementación real, aquí se usaría un scheduler como APScheduler
        return task_id

    def start(self):
        """Iniciar el bot"""
        if self.state == BotState.RUNNING:
            self.logger.warning("Bot ya está en ejecución")
            return False
        
        try:
            self.state = BotState.RUNNING
            self.logger.info("Bot de automatización iniciado")
            
            # Iniciar hilo para procesar tareas programadas
            self.scheduler_thread = threading.Thread(target=self._process_scheduled_tasks, daemon=True)
            self.scheduler_thread.start()
            
            return True
            
        except Exception as e:
            self.state = BotState.ERROR
            self.logger.error(f"Error iniciando bot: {e}")
            return False

    def pause(self):
        """Pausar el bot"""
        if self.state == BotState.RUNNING:
            self.state = BotState.PAUSED
            self.logger.info("Bot pausado")
            return True
        return False

    def resume(self):
        """Reanudar el bot"""
        if self.state == BotState.PAUSED:
            self.state = BotState.RUNNING
            self.logger.info("Bot reanudado")
            return True
        return False

    def stop(self):
        """Detener el bot"""
        self.state = BotState.STOPPED
        self.active_sessions.clear()
        self.logger.info("Bot detenido")
        return True

    def restart(self):
        """Reiniciar el bot"""
        self.stop()
        time.sleep(1)
        return self.start()

    def _process_scheduled_tasks(self):
        """Procesar tareas programadas (ejecutado en hilo separado)"""
        while self.state == BotState.RUNNING:
            try:
                now = datetime.now()
                
                for task in self.scheduled_tasks[:]:  # Copia para iteración segura
                    if task['status'] == 'scheduled' and now >= task['scheduled_time']:
                        self._execute_scheduled_task(task)
                
                time.sleep(10)  # Revisar cada 10 segundos
                
            except Exception as e:
                self.logger.error(f"Error en procesador de tareas: {e}")
                time.sleep(30)

    def _execute_scheduled_task(self, task: Dict[str, Any]):
        """Ejecutar una tarea programada"""
        try:
            task['status'] = 'running'
            task['started_at'] = datetime.now()
            
            self.logger.info(f"Ejecutando tarea programada: {task['id']}")
            
            # Ejecutar la automatización
            result = self.execute_automation(task['config'])
            
            task['status'] = 'completed' if result['success'] else 'failed'
            task['completed_at'] = datetime.now()
            task['result'] = result
            
            self.logger.info(f"Tarea {task['id']} {'completada' if result['success'] else 'fallida'}")
            
        except Exception as e:
            task['status'] = 'error'
            task['error'] = str(e)
            self.logger.error(f"Error ejecutando tarea {task['id']}: {e}")

    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Obtener lista de tareas programadas"""
        return self.scheduled_tasks

    def cancel_task(self, task_id: str) -> bool:
        """Cancelar una tarea programada"""
        for task in self.scheduled_tasks:
            if task['id'] == task_id and task['status'] == 'scheduled':
                task['status'] = 'cancelled'
                self.logger.info(f"Tarea cancelada: {task_id}")
                return True
        return False

    def update_performance_metrics(self, result: Dict[str, Any]):
        """Actualizar métricas de performance"""
        timestamp = datetime.now().isoformat()
        
        if 'performance_metrics' not in self.performance_metrics:
            self.performance_metrics = {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'total_products_processed': 0,
                'total_duration': 0,
                'average_duration': 0,
                'success_rate': 0,
                'last_updated': timestamp
            }
        
        metrics = self.performance_metrics
        metrics['total_executions'] += 1
        
        if result['success']:
            metrics['successful_executions'] += 1
        else:
            metrics['failed_executions'] += 1
        
        metrics['total_products_processed'] += result.get('products_processed', 0)
        metrics['total_duration'] += result.get('duration', 0)
        metrics['average_duration'] = metrics['total_duration'] / metrics['total_executions']
        metrics['success_rate'] = (metrics['successful_executions'] / metrics['total_executions']) * 100
        metrics['last_updated'] = timestamp

    def get_performance_report(self) -> Dict[str, Any]:
        """Obtener reporte de performance"""
        return self.performance_metrics

    def cleanup_old_tasks(self, days: int = 7):
        """Limpiar tareas antiguas"""
        cutoff_date = datetime.now() - timedelta(days=days)
        initial_count = len(self.scheduled_tasks)
        
        self.scheduled_tasks = [
            task for task in self.scheduled_tasks
            if task.get('created_at', datetime.now()) > cutoff_date
        ]
        
        removed_count = initial_count - len(self.scheduled_tasks)
        self.logger.info(f"Tareas antiguas limpiadas: {removed_count} removidas")

    def export_tasks(self, file_path: str):
        """Exportar tareas programadas a archivo"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.scheduled_tasks, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Tareas exportadas a {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error exportando tareas: {e}")
            return False

    def import_tasks(self, file_path: str):
        """Importar tareas desde archivo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            
            # Convertir strings de fecha a objetos datetime
            for task in tasks:
                for date_field in ['scheduled_time', 'created_at', 'started_at', 'completed_at']:
                    if task.get(date_field) and isinstance(task[date_field], str):
                        task[date_field] = datetime.fromisoformat(task[date_field])
            
            self.scheduled_tasks.extend(tasks)
            self.logger.info(f"Tareas importadas desde {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error importando tareas: {e}")
            return False