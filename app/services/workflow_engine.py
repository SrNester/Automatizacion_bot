from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.orm import Session
import json
import asyncio
from dataclasses import dataclass

from ..models.workflow import Workflow, WorkflowExecution, WorkflowStep
from ..models.integration import Lead
from ..services.email_automation import EmailAutomationService
from ..services.lead_scoring import LeadScoringService
from ..core.database import get_db

class TriggerType(str, Enum):
    SCORE_CHANGE = "score_change"
    TIME_DELAY = "time_delay"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    PAGE_VISITED = "page_visited"
    FORM_SUBMITTED = "form_submitted"
    CHATBOT_INTERACTION = "chatbot_interaction"
    MANUAL = "manual"

class ActionType(str, Enum):
    SEND_EMAIL = "send_email"
    UPDATE_SCORE = "update_score"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    CHANGE_SEGMENT = "change_segment"
    CREATE_TASK = "create_task"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_FIELD = "update_field"
    WEBHOOK = "webhook"

class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused" 
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TriggerCondition:
    field: str
    operator: str  # eq, gt, lt, gte, lte, contains, in
    value: Any
    
@dataclass
class WorkflowAction:
    type: ActionType
    parameters: Dict[str, Any]
    delay_minutes: int = 0

class WorkflowEngine:
    """Motor principal para ejecutar workflows de nurturing"""
    
    def __init__(self):
        self.email_service = EmailAutomationService()
        self.scoring_service = LeadScoringService()
        self.active_workflows = {}  # Cache de workflows activos
        
        # Registro de handlers para diferentes tipos de acciones
        self.action_handlers: Dict[ActionType, Callable] = {
            ActionType.SEND_EMAIL: self._handle_send_email,
            ActionType.UPDATE_SCORE: self._handle_update_score,
            ActionType.ADD_TAG: self._handle_add_tag,
            ActionType.REMOVE_TAG: self._handle_remove_tag,
            ActionType.CHANGE_SEGMENT: self._handle_change_segment,
            ActionType.CREATE_TASK: self._handle_create_task,
            ActionType.SEND_NOTIFICATION: self._handle_send_notification,
            ActionType.UPDATE_FIELD: self._handle_update_field,
            ActionType.WEBHOOK: self._handle_webhook
        }
    
    async def trigger_workflow(self, 
                             trigger_type: TriggerType,
                             lead_id: int,
                             trigger_data: Dict[str, Any] = None,
                             db: Session = None) -> List[int]:
        """
        Dispara workflows basados en un trigger específico
        
        Args:
            trigger_type: Tipo de trigger que activó el workflow
            lead_id: ID del lead que disparó el trigger
            trigger_data: Datos adicionales del trigger
            db: Sesión de base de datos
            
        Returns:
            List[int]: IDs de las ejecuciones de workflow iniciadas
        """
        
        if not db:
            db = next(get_db())
        
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return []
        
        # Buscar workflows que coincidan con el trigger
        matching_workflows = await self._find_matching_workflows(
            trigger_type, lead, trigger_data, db
        )
        
        executions_started = []
        
        for workflow in matching_workflows:
            # Verificar si el lead ya está en este workflow
            existing_execution = db.query(WorkflowExecution)\
                .filter(WorkflowExecution.workflow_id == workflow.id)\
                .filter(WorkflowExecution.lead_id == lead_id)\
                .filter(WorkflowExecution.status.in_([WorkflowStatus.ACTIVE]))\
                .first()
            
            if existing_execution:
                continue  # Skip si ya está en el workflow
            
            # Iniciar nueva ejecución del workflow
            execution = await self._start_workflow_execution(
                workflow, lead, trigger_data, db
            )
            
            if execution:
                executions_started.append(execution.id)
        
        return executions_started
    
    async def _find_matching_workflows(self,
                                     trigger_type: TriggerType,
                                     lead: Lead,
                                     trigger_data: Dict,
                                     db: Session) -> List[Workflow]:
        """Encuentra workflows que coincidan con el trigger y condiciones"""
        
        # Obtener workflows activos del tipo de trigger
        workflows = db.query(Workflow)\
            .filter(Workflow.trigger_type == trigger_type)\
            .filter(Workflow.is_active == True)\
            .all()
        
        matching_workflows = []
        
        for workflow in workflows:
            if await self._evaluate_workflow_conditions(workflow, lead, trigger_data):
                matching_workflows.append(workflow)
        
        return matching_workflows
    
    async def _evaluate_workflow_conditions(self,
                                          workflow: Workflow,
                                          lead: Lead,
                                          trigger_data: Dict) -> bool:
        """Evalúa si un lead cumple las condiciones para entrar en el workflow"""
        
        if not workflow.conditions:
            return True  # Sin condiciones = siempre aplicable
        
        conditions = json.loads(workflow.conditions) if isinstance(workflow.conditions, str) else workflow.conditions
        
        for condition in conditions:
            if not await self._evaluate_single_condition(condition, lead, trigger_data):
                return False  # AND logic: todas las condiciones deben cumplirse
        
        return True
    
    async def _evaluate_single_condition(self,
                                       condition: Dict,
                                       lead: Lead,
                                       trigger_data: Dict) -> bool:
        """Evalúa una condición individual"""
        
        field = condition.get('field')
        operator = condition.get('operator')
        expected_value = condition.get('value')
        
        # Obtener valor actual del campo
        if field.startswith('trigger.'):
            # Datos del trigger actual
            field_name = field.replace('trigger.', '')
            actual_value = trigger_data.get(field_name)
        else:
            # Datos del lead
            actual_value = getattr(lead, field, None)
        
        # Evaluar condición
        return self._compare_values(actual_value, operator, expected_value)
    
    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compara valores según el operador especificado"""
        
        if operator == 'eq':
            return actual == expected
        elif operator == 'gt':
            return actual > expected
        elif operator == 'lt':
            return actual < expected
        elif operator == 'gte':
            return actual >= expected
        elif operator == 'lte':
            return actual <= expected
        elif operator == 'contains':
            return expected in str(actual) if actual else False
        elif operator == 'in':
            return actual in expected if isinstance(expected, list) else False
        elif operator == 'not_eq':
            return actual != expected
        else:
            return False
    
    async def _start_workflow_execution(self,
                                      workflow: Workflow,
                                      lead: Lead,
                                      trigger_data: Dict,
                                      db: Session) -> Optional[WorkflowExecution]:
        """Inicia una nueva ejecución de workflow"""
        
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            lead_id=lead.id,
            status=WorkflowStatus.ACTIVE,
            trigger_data=trigger_data,
            started_at=datetime.utcnow(),
            current_step=0,
            context={}
        )
        
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        # Ejecutar primer step inmediatamente si no tiene delay
        await self._execute_next_step(execution, db)
        
        return execution
    
    async def _execute_next_step(self, execution: WorkflowExecution, db: Session):
        """Ejecuta el siguiente paso en el workflow"""
        
        workflow = db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow or not workflow.steps:
            return
        
        steps = json.loads(workflow.steps) if isinstance(workflow.steps, str) else workflow.steps
        
        if execution.current_step >= len(steps):
            # Workflow completado
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            db.commit()
            return
        
        current_step = steps[execution.current_step]
        
        try:
            # Ejecutar acción del step actual
            await self._execute_workflow_action(
                execution, current_step, db
            )
            
            # Avanzar al siguiente step
            execution.current_step += 1
            execution.last_executed_at = datetime.utcnow()
            db.commit()
            
            # Programar siguiente step si tiene delay
            next_step_index = execution.current_step
            if next_step_index < len(steps):
                next_step = steps[next_step_index]
                delay_minutes = next_step.get('delay_minutes', 0)
                
                if delay_minutes > 0:
                    # Programar ejecución con delay
                    await self._schedule_step_execution(
                        execution.id, delay_minutes
                    )
                else:
                    # Ejecutar inmediatamente
                    await self._execute_next_step(execution, db)
        
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error_message = str(e)
            execution.failed_at = datetime.utcnow()
            db.commit()
            
            print(f"❌ Error ejecutando workflow {execution.id}: {e}")
    
    async def _execute_workflow_action(self,
                                     execution: WorkflowExecution,
                                     step: Dict,
                                     db: Session):
        """Ejecuta una acción específica del workflow"""
        
        action_type = ActionType(step.get('action_type'))
        parameters = step.get('parameters', {})
        
        if action_type in self.action_handlers:
            handler = self.action_handlers[action_type]
            await handler(execution, parameters, db)
        else:
            raise ValueError(f"Handler no encontrado para acción: {action_type}")
    
    # ===========================================
    # HANDLERS PARA DIFERENTES TIPOS DE ACCIONES
    # ===========================================
    
    async def _handle_send_email(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para envío de emails"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        template_id = params.get('template_id')
        subject = params.get('subject', '')
        
        # Personalizar email con datos del lead
        personalization_data = {
            'lead_name': lead.name or 'Cliente',
            'lead_company': lead.company or '',
            'lead_score': lead.score,
            'workflow_context': execution.context
        }
        
        result = await self.email_service.send_template_email(
            to_email=lead.email,
            template_id=template_id,
            subject=subject,
            personalization_data=personalization_data
        )
        
        # Actualizar contexto con resultado
        execution.context = execution.context or {}
        execution.context['last_email_sent'] = {
            'template_id': template_id,
            'sent_at': datetime.utcnow().isoformat(),
            'success': result.get('success', False),
            'message_id': result.get('message_id')
        }
    
    async def _handle_update_score(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para actualizar score del lead"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        score_change = params.get('score_change', 0)
        
        new_score = min(100, max(0, lead.score + score_change))
        lead.score = new_score
        lead.updated_at = datetime.utcnow()
        
        # Log del cambio en contexto
        execution.context = execution.context or {}
        execution.context['score_changes'] = execution.context.get('score_changes', [])
        execution.context['score_changes'].append({
            'from': lead.score - score_change,
            'to': new_score,
            'change': score_change,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def _handle_add_tag(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para agregar tags al lead"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        tag = params.get('tag')
        
        if tag:
            lead.tags = lead.tags or []
            if tag not in lead.tags:
                lead.tags.append(tag)
                lead.updated_at = datetime.utcnow()
    
    async def _handle_remove_tag(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para remover tags del lead"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        tag = params.get('tag')
        
        if tag and lead.tags and tag in lead.tags:
            lead.tags.remove(tag)
            lead.updated_at = datetime.utcnow()
    
    async def _handle_change_segment(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para cambiar segmento del lead"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        new_segment = params.get('segment')
        
        if new_segment:
            old_segment = lead.segment
            lead.segment = new_segment
            lead.updated_at = datetime.utcnow()
            
            # Log del cambio
            execution.context = execution.context or {}
            execution.context['segment_change'] = {
                'from': old_segment,
                'to': new_segment,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_create_task(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para crear tareas para el equipo"""
        
        # Aquí integrarías con tu sistema de tareas (Asana, Monday, etc.)
        task_data = {
            'title': params.get('title', 'Tarea de Workflow'),
            'description': params.get('description', ''),
            'assignee': params.get('assignee'),
            'due_date': params.get('due_date'),
            'lead_id': execution.lead_id,
            'workflow_execution_id': execution.id
        }
        
        # Por ahora, guardar en contexto
        execution.context = execution.context or {}
        execution.context['tasks_created'] = execution.context.get('tasks_created', [])
        execution.context['tasks_created'].append(task_data)
        
        print(f"📋 Tarea creada: {task_data['title']}")
    
    async def _handle_send_notification(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para enviar notificaciones al equipo"""
        
        notification_data = {
            'type': params.get('type', 'workflow_notification'),
            'message': params.get('message', ''),
            'channel': params.get('channel', 'slack'),  # slack, email, teams
            'lead_id': execution.lead_id,
            'execution_id': execution.id
        }
        
        # Aquí integrarías con Slack, Teams, etc.
        print(f"📢 Notificación: {notification_data['message']}")
        
        execution.context = execution.context or {}
        execution.context['notifications_sent'] = execution.context.get('notifications_sent', [])
        execution.context['notifications_sent'].append(notification_data)
    
    async def _handle_update_field(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para actualizar campos del lead"""
        
        lead = db.query(Lead).filter(Lead.id == execution.lead_id).first()
        field_name = params.get('field')
        field_value = params.get('value')
        
        if hasattr(lead, field_name):
            setattr(lead, field_name, field_value)
            lead.updated_at = datetime.utcnow()
    
    async def _handle_webhook(self, execution: WorkflowExecution, params: Dict, db: Session):
        """Handler para ejecutar webhooks"""
        
        import aiohttp
        
        webhook_url = params.get('url')
        webhook_data = {
            'lead_id': execution.lead_id,
            'execution_id': execution.id,
            'workflow_id': execution.workflow_id,
            'custom_data': params.get('data', {})
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(webhook_url, json=webhook_data) as response:
                    result = {
                        'status': response.status,
                        'response': await response.text()
                    }
                    
                    execution.context = execution.context or {}
                    execution.context['webhook_results'] = execution.context.get('webhook_results', [])
                    execution.context['webhook_results'].append(result)
                    
            except Exception as e:
                print(f"❌ Error en webhook: {e}")
    
    async def _schedule_step_execution(self, execution_id: int, delay_minutes: int):
        """Programa la ejecución de un step con delay"""
        
        # Aquí integrarías con Celery o tu sistema de colas
        # Por ahora, usar asyncio para demo
        
        async def delayed_execution():
            await asyncio.sleep(delay_minutes * 60)  # Convertir a segundos
            db = next(get_db())
            execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
            
            if execution and execution.status == WorkflowStatus.ACTIVE:
                await self._execute_next_step(execution, db)
        
        asyncio.create_task(delayed_execution())
    
    # ===========================================
    # MÉTODOS DE UTILIDAD Y MANAGEMENT
    # ===========================================
    
    async def pause_workflow_execution(self, execution_id: int, db: Session):
        """Pausa una ejecución de workflow"""
        
        execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
        if execution:
            execution.status = WorkflowStatus.PAUSED
            execution.paused_at = datetime.utcnow()
            db.commit()
    
    async def resume_workflow_execution(self, execution_id: int, db: Session):
        """Reanuda una ejecución de workflow pausada"""
        
        execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
        if execution and execution.status == WorkflowStatus.PAUSED:
            execution.status = WorkflowStatus.ACTIVE
            execution.resumed_at = datetime.utcnow()
            db.commit()
            
            # Continuar con el siguiente step
            await self._execute_next_step(execution, db)
    
    async def get_workflow_metrics(self, workflow_id: int, days: int = 30, db: Session = None) -> Dict:
        """Obtiene métricas de performance de un workflow"""
        
        if not db:
            db = next(get_db())
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        executions = db.query(WorkflowExecution)\
            .filter(WorkflowExecution.workflow_id == workflow_id)\
            .filter(WorkflowExecution.started_at > since_date)\
            .all()
        
        total_executions = len(executions)
        completed_executions = len([e for e in executions if e.status == WorkflowStatus.COMPLETED])
        failed_executions = len([e for e in executions if e.status == WorkflowStatus.FAILED])
        active_executions = len([e for e in executions if e.status == WorkflowStatus.ACTIVE])
        
        completion_rate = completed_executions / total_executions if total_executions > 0 else 0
        
        # Tiempo promedio de completion
        completed = [e for e in executions if e.completed_at]
        avg_completion_time = 0
        if completed:
            total_time = sum([(e.completed_at - e.started_at).total_seconds() for e in completed])
            avg_completion_time = total_time / len(completed) / 3600  # En horas
        
        return {
            'workflow_id': workflow_id,
            'period_days': days,
            'total_executions': total_executions,
            'completed_executions': completed_executions,
            'failed_executions': failed_executions,
            'active_executions': active_executions,
            'completion_rate': completion_rate,
            'failure_rate': failed_executions / total_executions if total_executions > 0 else 0,
            'avg_completion_time_hours': avg_completion_time
        }