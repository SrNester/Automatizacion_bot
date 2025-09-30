import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import logging
from dataclasses import dataclass
import uuid
from concurrent.futures import ThreadPoolExecutor

# Base de datos
from sqlalchemy.orm import Session

# Nuestros servicios
from ..core.database import get_db
from .task_scheduler import TaskScheduler, TaskType, TaskPriority

# Logger
logger = logging.getLogger("background_tasks")

@dataclass
class BackgroundTask:
    id: str
    name: str
    coroutine: Callable
    params: Dict[str, Any]
    created_at: datetime
    status: str = "pending"
    result: Any = None
    error: str = None

class BackgroundTaskManager:
    """
    Gestor de tareas en background para operaciones asíncronas
    que no requieren scheduling complejo
    """
    
    def __init__(self):
        self.task_scheduler = TaskScheduler()
        self.active_tasks: Dict[str, BackgroundTask] = {}
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.task_history: List[BackgroundTask] = []
        
        logger.info("BackgroundTaskManager inicializado")
    
    async def execute_in_background(self,
                                 name: str,
                                 coroutine: Callable,
                                 params: Dict[str, Any] = None,
                                 db: Session = None) -> str:
        """
        Ejecuta una coroutine en background y retorna inmediatamente
        
        Args:
            name: Nombre descriptivo de la tarea
            coroutine: Función asíncrona a ejecutar
            params: Parámetros para la coroutine
            db: Sesión de base de datos
            
        Returns:
            str: ID de la tarea
        """
        
        task_id = str(uuid.uuid4())
        params = params or {}
        
        task = BackgroundTask(
            id=task_id,
            name=name,
            coroutine=coroutine,
            params=params,
            created_at=datetime.utcnow()
        )
        
        self.active_tasks[task_id] = task
        
        # Ejecutar en background
        asyncio.create_task(self._execute_task(task, db))
        
        logger.info(f"Tarea background iniciada: {task_id} ({name})")
        return task_id
    
    async def _execute_task(self, task: BackgroundTask, db: Session = None):
        """Ejecuta una tarea en background"""
        
        try:
            task.status = "running"
            
            # Ejecutar la coroutine
            if db:
                result = await task.coroutine(**task.params, db=db)
            else:
                result = await task.coroutine(**task.params)
            
            task.status = "completed"
            task.result = result
            
            logger.info(f"Tarea background completada: {task.id} ({task.name})")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"Tarea background falló: {task.id} ({task.name}): {str(e)}")
        
        finally:
            # Mover a historial y limpiar activas
            self.task_history.append(task)
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            
            # Mantener sólo las últimas 1000 tareas en historial
            if len(self.task_history) > 1000:
                self.task_history = self.task_history[-1000:]
    
    async def schedule_workflow_trigger(self,
                                      trigger_type: str,
                                      lead_id: int,
                                      trigger_data: Dict = None,
                                      db: Session = None) -> str:
        """Programa un trigger de workflow en background"""
        
        from ..services.workflow_engine import WorkflowEngine
        workflow_engine = WorkflowEngine()
        
        return await self.execute_in_background(
            name=f"workflow_trigger_{trigger_type}",
            coroutine=workflow_engine.trigger_workflow,
            params={
                'trigger_type': trigger_type,
                'lead_id': lead_id,
                'trigger_data': trigger_data or {}
            },
            db=db
        )
    
    async def schedule_email_send(self,
                                template_id: int,
                                lead_ids: List[int],
                                personalization_data: Dict = None,
                                db: Session = None) -> str:
        """Programa envío de emails en background"""
        
        return await self.task_scheduler.schedule_task(
            task_type=TaskType.EMAIL_BATCH,
            parameters={
                'template_id': template_id,
                'lead_ids': lead_ids,
                'personalization_data': personalization_data
            },
            priority=TaskPriority.HIGH,
            db=db
        )
    
    async def schedule_report_generation(self,
                                       report_type: str,
                                       period: str,
                                       recipients: List[str],
                                       db: Session = None) -> str:
        """Programa generación de reporte en background"""
        
        return await self.task_scheduler.schedule_task(
            task_type=TaskType.REPORT_GENERATION,
            parameters={
                'report_type': report_type,
                'period': period,
                'recipients': recipients
            },
            priority=TaskPriority.NORMAL,
            db=db
        )
    
    async def schedule_hubspot_sync(self,
                                  sync_type: str = "incremental",
                                  lead_ids: List[int] = None,
                                  db: Session = None) -> str:
        """Programa sincronización con HubSpot en background"""
        
        return await self.task_scheduler.schedule_task(
            task_type=TaskType.HUBSPOT_SYNC,
            parameters={
                'sync_type': sync_type,
                'lead_ids': lead_ids
            },
            priority=TaskPriority.NORMAL,
            db=db
        )
    
    async def schedule_lead_processing(self,
                                    process_type: str = "batch_scoring",
                                    lead_ids: List[int] = None,
                                    batch_size: int = 100,
                                    db: Session = None) -> str:
        """Programa procesamiento de leads en background"""
        
        return await self.task_scheduler.schedule_task(
            task_type=TaskType.LEAD_PROCESSING,
            parameters={
                'process_type': process_type,
                'lead_ids': lead_ids,
                'batch_size': batch_size
            },
            priority=TaskPriority.NORMAL,
            db=db
        )
    
    async def schedule_notification(self,
                                 notification_type: str,
                                 recipients: List[str],
                                 message: str,
                                 subject: str = None,
                                 db: Session = None) -> str:
        """Programa envío de notificación en background"""
        
        return await self.task_scheduler.schedule_task(
            task_type=TaskType.NOTIFICATION_SEND,
            parameters={
                'type': notification_type,
                'recipients': recipients,
                'message': message,
                'subject': subject
            },
            priority=TaskPriority.HIGH,
            db=db
        )
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Obtiene el estado de una tarea background"""
        
        # Buscar en tareas activas
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                'task_id': task_id,
                'name': task.name,
                'status': task.status,
                'created_at': task.created_at.isoformat(),
                'is_active': True
            }
        
        # Buscar en historial
        for task in reversed(self.task_history):
            if task.id == task_id:
                return {
                    'task_id': task_id,
                    'name': task.name,
                    'status': task.status,
                    'created_at': task.created_at.isoformat(),
                    'completed_at': datetime.utcnow().isoformat(),
                    'result': task.result,
                    'error': task.error,
                    'is_active': False
                }
        
        return {
            'task_id': task_id,
            'found': False,
            'error': 'Tarea no encontrada'
        }
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Obtiene lista de tareas activas"""
        
        return [
            {
                'task_id': task.id,
                'name': task.name,
                'status': task.status,
                'created_at': task.created_at.isoformat()
            }
            for task in self.active_tasks.values()
        ]
    
    def get_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene tareas recientes del historial"""
        
        recent_tasks = self.task_history[-limit:] if self.task_history else []
        
        return [
            {
                'task_id': task.id,
                'name': task.name,
                'status': task.status,
                'created_at': task.created_at.isoformat(),
                'result': task.result,
                'error': task.error
            }
            for task in recent_tasks
        ]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancela una tarea background (si es posible)"""
        
        if task_id in self.active_tasks:
            # Marcar como cancelada (no podemos realmente cancelar la coroutine)
            task = self.active_tasks[task_id]
            task.status = "cancelled"
            del self.active_tasks[task_id]
            self.task_history.append(task)
            return True
        
        return False

# Instancia global
background_task_manager = BackgroundTaskManager()