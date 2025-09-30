import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import logging
from dataclasses import dataclass
import time

# Base de datos
from sqlalchemy.orm import Session

# Nuestros servicios
from ..core.database import get_db
from ..core.config import settings
from .task_scheduler import TaskScheduler, TaskType, TaskPriority

# Logger
logger = logging.getLogger("periodic_tasks")

@dataclass
class PeriodicTask:
    name: str
    interval_minutes: int
    coroutine: Callable
    last_run: Optional[datetime] = None
    is_running: bool = False
    enabled: bool = True

class PeriodicTaskManager:
    """
    Gestor de tareas periódicas que se ejecutan automáticamente
    en intervalos regulares
    """
    
    def __init__(self):
        self.task_scheduler = TaskScheduler()
        self.periodic_tasks: Dict[str, PeriodicTask] = {}
        self.is_running = False
        
        # Registrar tareas periódicas por defecto
        self._register_default_tasks()
        
        logger.info("PeriodicTaskManager inicializado")
    
    def _register_default_tasks(self):
        """Registra las tareas periódicas por defecto"""
        
        self.periodic_tasks = {
            "hubspot_incremental_sync": PeriodicTask(
                name="HubSpot Incremental Sync",
                interval_minutes=30,  # Cada 30 minutos
                coroutine=self._hubspot_incremental_sync
            ),
            "lead_scoring_batch": PeriodicTask(
                name="Lead Scoring Batch",
                interval_minutes=60,  # Cada hora
                coroutine=self._lead_scoring_batch
            ),
            "workflow_cleanup": PeriodicTask(
                name="Workflow Cleanup",
                interval_minutes=1440,  # Diario
                coroutine=self._workflow_cleanup
            ),
            "system_health_check": PeriodicTask(
                name="System Health Check",
                interval_minutes=5,  # Cada 5 minutos
                coroutine=self._system_health_check
            ),
            "email_queue_processing": PeriodicTask(
                name="Email Queue Processing",
                interval_minutes=1,  # Cada minuto
                coroutine=self._email_queue_processing
            ),
            "realtime_analytics_update": PeriodicTask(
                name="Real-time Analytics Update",
                interval_minutes=10,  # Cada 10 minutos
                coroutine=self._realtime_analytics_update
            )
        }
    
    async def start(self):
        """Inicia el manager de tareas periódicas"""
        
        if self.is_running:
            logger.warning("PeriodicTaskManager ya está corriendo")
            return
        
        self.is_running = True
        logger.info("Iniciando PeriodicTaskManager")
        
        # Iniciar loop principal
        asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """Detiene el manager de tareas periódicas"""
        
        self.is_running = False
        logger.info("Deteniendo PeriodicTaskManager")
    
    async def _main_loop(self):
        """Loop principal que verifica y ejecuta tareas periódicas"""
        
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                for task_id, task in self.periodic_tasks.items():
                    if not task.enabled or task.is_running:
                        continue
                    
                    # Verificar si es tiempo de ejecutar
                    should_run = False
                    if task.last_run is None:
                        should_run = True
                    else:
                        time_since_last_run = current_time - task.last_run
                        should_run = time_since_last_run.total_seconds() >= task.interval_minutes * 60
                    
                    if should_run:
                        # Ejecutar tarea en background
                        asyncio.create_task(self._execute_periodic_task(task_id))
                
                # Esperar 30 segundos antes de la siguiente verificación
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error en loop principal de tareas periódicas: {str(e)}")
                await asyncio.sleep(60)  # Esperar más tiempo en caso de error
    
    async def _execute_periodic_task(self, task_id: str):
        """Ejecuta una tarea periódica específica"""
        
        task = self.periodic_tasks.get(task_id)
        if not task or not task.enabled:
            return
        
        try:
            task.is_running = True
            task.last_run = datetime.utcnow()
            
            logger.info(f"Ejecutando tarea periódica: {task.name}")
            
            # Ejecutar la tarea
            await task.coroutine()
            
            logger.info(f"Tarea periódica completada: {task.name}")
            
        except Exception as e:
            logger.error(f"Error ejecutando tarea periódica {task.name}: {str(e)}")
        
        finally:
            task.is_running = False
    
    # ===========================================
    # IMPLEMENTACIONES DE TAREAS PERIÓDICAS
    # ===========================================
    
    async def _hubspot_incremental_sync(self):
        """Sincronización incremental con HubSpot"""
        
        try:
            await self.task_scheduler.schedule_task(
                task_type=TaskType.HUBSPOT_SYNC,
                parameters={'sync_type': 'incremental'},
                priority=TaskPriority.NORMAL
            )
        except Exception as e:
            logger.error(f"Error programando sync incremental de HubSpot: {str(e)}")
    
    async def _lead_scoring_batch(self):
        """Procesamiento batch de scoring de leads"""
        
        try:
            await self.task_scheduler.schedule_task(
                task_type=TaskType.LEAD_PROCESSING,
                parameters={'process_type': 'batch_scoring', 'batch_size': 200},
                priority=TaskPriority.NORMAL
            )
        except Exception as e:
            logger.error(f"Error programando batch de lead scoring: {str(e)}")
    
    async def _workflow_cleanup(self):
        """Limpieza de workflows stalled"""
        
        try:
            from ..services.workflow_engine import WorkflowEngine
            workflow_engine = WorkflowEngine()
            
            with workflow_engine.database_session() as db:
                cleaned_count = await workflow_engine.cleanup_stalled_executions(db)
                logger.info(f"Workflow cleanup completado: {cleaned_count} ejecuciones limpiadas")
                
        except Exception as e:
            logger.error(f"Error en cleanup de workflows: {str(e)}")
    
    async def _system_health_check(self):
        """Verificación de salud del sistema"""
        
        try:
            health_checks = {}
            
            # Verificar base de datos
            try:
                with self.task_scheduler._get_db_session() as db:
                    db.execute("SELECT 1")
                health_checks['database'] = 'healthy'
            except Exception as e:
                health_checks['database'] = f'unhealthy: {str(e)}'
            
            # Verificar servicios externos
            health_checks['timestamp'] = datetime.utcnow().isoformat()
            health_checks['active_tasks'] = len(self.task_scheduler.active_tasks)
            
            # Log health status
            if all(status == 'healthy' for status in health_checks.values()):
                logger.debug("System health check: OK")
            else:
                logger.warning(f"System health issues: {health_checks}")
                
        except Exception as e:
            logger.error(f"Error en health check: {str(e)}")
    
    async def _email_queue_processing(self):
        """Procesamiento de cola de emails"""
        
        try:
            from ..services.email_automation import EmailAutomationService
            email_service = EmailAutomationService()
            
            with self.task_scheduler._get_db_session() as db:
                # Aquí procesarías la cola de emails pendientes
                # Por ahora es un placeholder
                pending_count = 0  # Obtener de la base de datos
                
                if pending_count > 0:
                    logger.info(f"Procesando cola de emails: {pending_count} pendientes")
                    # await email_service.process_pending_emails(db)
                    
        except Exception as e:
            logger.error(f"Error procesando cola de emails: {str(e)}")
    
    async def _realtime_analytics_update(self):
        """Actualización de analytics en tiempo real"""
        
        try:
            from ..services.analytics_service import AnalyticsService
            analytics_service = AnalyticsService()
            
            with self.task_scheduler._get_db_session() as db:
                # Actualizar dashboards en tiempo real
                await analytics_service.update_realtime_dashboards(db)
                logger.debug("Analytics en tiempo real actualizados")
                
        except Exception as e:
            logger.error(f"Error actualizando analytics en tiempo real: {str(e)}")
    
    # ===========================================
    # MÉTODOS DE GESTIÓN
    # ===========================================
    
    def enable_task(self, task_id: str):
        """Habilita una tarea periódica"""
        
        if task_id in self.periodic_tasks:
            self.periodic_tasks[task_id].enabled = True
            logger.info(f"Tarea periódica habilitada: {task_id}")
    
    def disable_task(self, task_id: str):
        """Deshabilita una tarea periódica"""
        
        if task_id in self.periodic_tasks:
            self.periodic_tasks[task_id].enabled = False
            logger.info(f"Tarea periódica deshabilitada: {task_id}")
    
    def update_task_interval(self, task_id: str, interval_minutes: int):
        """Actualiza el intervalo de una tarea periódica"""
        
        if task_id in self.periodic_tasks:
            self.periodic_tasks[task_id].interval_minutes = interval_minutes
            logger.info(f"Intervalo de tarea {task_id} actualizado a {interval_minutes} minutos")
    
    def get_task_status(self) -> Dict[str, Any]:
        """Obtiene el estado de todas las tareas periódicas"""
        
        status = {}
        
        for task_id, task in self.periodic_tasks.items():
            status[task_id] = {
                'name': task.name,
                'enabled': task.enabled,
                'interval_minutes': task.interval_minutes,
                'is_running': task.is_running,
                'last_run': task.last_run.isoformat() if task.last_run else None,
                'next_run': self._calculate_next_run(task) if task.enabled else None
            }
        
        return {
            'is_running': self.is_running,
            'tasks': status
        }
    
    def _calculate_next_run(self, task: PeriodicTask) -> str:
        """Calcula cuándo se ejecutará la próxima vez la tarea"""
        
        if not task.last_run:
            return "Próximamente"
        
        next_run = task.last_run + timedelta(minutes=task.interval_minutes)
        return next_run.isoformat()
    
    def register_custom_task(self,
                           task_id: str,
                           name: str,
                           coroutine: Callable,
                           interval_minutes: int) -> bool:
        """Registra una tarea periódica personalizada"""
        
        if task_id in self.periodic_tasks:
            logger.warning(f"Tarea {task_id} ya existe")
            return False
        
        self.periodic_tasks[task_id] = PeriodicTask(
            name=name,
            interval_minutes=interval_minutes,
            coroutine=coroutine
        )
        
        logger.info(f"Tarea personalizada registrada: {task_id} ({name})")
        return True

# Instancia global
periodic_task_manager = PeriodicTaskManager()