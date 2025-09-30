import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, olumn, Integer, String, DateTime
from sqlalchemy.orm import selectinload
import numpy as np
from collections import defaultdict

# ✅ IMPORTS CORREGIDOS - Usar integration.py en lugar de leads.py
from ...models.integration import Lead, LeadStatus, ExternalLead, Integration
from ...models.interaction import Interaction, ConversationSummary
from ...models.workflow import WorkflowExecution, EmailSend

@dataclass
class MetricConfig:
    """Configuración para métricas del sistema"""
    name: str
    calculation_type: str
    refresh_interval: int
    cache_ttl: int
    aggregation_window: str

class AnalyticsEngine:
    """Motor principal de analytics con procesamiento en tiempo real"""
    
    def __init__(self, redis_client: redis.Redis, db_session: AsyncSession):
        self.redis = redis_client
        self.db = db_session
        self.metrics_config = self._initialize_metrics()
        self.pipeline_queue = asyncio.Queue()
        self.processing_tasks = []
        
    def _initialize_metrics(self) -> Dict[str, MetricConfig]:
        """Inicializa la configuración de métricas"""
        return {
            'active_leads': MetricConfig(
                name='Leads Activos',
                calculation_type='count',
                refresh_interval=300,
                cache_ttl=600,
                aggregation_window='day'
            ),
            'conversion_rate': MetricConfig(
                name='Tasa de Conversión',
                calculation_type='average',
                refresh_interval=1800,
                cache_ttl=3600,
                aggregation_window='week'
            ),
            'response_time': MetricConfig(
                name='Tiempo de Respuesta Promedio',
                calculation_type='average',
                refresh_interval=900,
                cache_ttl=1800,
                aggregation_window='day'
            ),
            'lead_velocity': MetricConfig(
                name='Velocidad de Leads',
                calculation_type='custom',
                refresh_interval=3600,
                cache_ttl=7200,
                aggregation_window='month'
            ),
            'workflow_efficiency': MetricConfig(
                name='Eficiencia de Workflows',
                calculation_type='custom',
                refresh_interval=3600,
                cache_ttl=7200,
                aggregation_window='week'
            )
        }
    
    async def start_engine(self):
        """Inicia el motor de analytics"""
        print("🚀 Starting Analytics Engine...")
        
        # Iniciar workers de procesamiento
        for i in range(3):  # 3 workers concurrentes
            task = asyncio.create_task(self._process_pipeline())
            self.processing_tasks.append(task)
        
        # Iniciar actualizaciones automáticas de métricas
        asyncio.create_task(self._auto_refresh_metrics())
        
        print("✅ Analytics Engine started successfully")
    
    async def stop_engine(self):
        """Detiene el motor de analytics"""
        for task in self.processing_tasks:
            task.cancel()
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)
    
    async def _process_pipeline(self):
        """Worker que procesa datos del pipeline"""
        while True:
            try:
                data_batch = await self.pipeline_queue.get()
                await self._process_batch(data_batch)
                self.pipeline_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error in pipeline processing: {e}")
    
    async def _process_batch(self, batch: List[Dict]):
        """Procesa un batch de datos"""
        # Agrupar por tipo de evento
        events_by_type = defaultdict(list)
        for event in batch:
            events_by_type[event.get('type', 'unknown')].append(event)
        
        # Procesar cada tipo de evento
        for event_type, events in events_by_type.items():
            await self._update_real_time_metrics(event_type, events)
    
    async def _update_real_time_metrics(self, event_type: str, events: List[Dict]):
        """Actualiza métricas en tiempo real"""
        pipe = self.redis.pipeline()
        
        for event in events:
            # Incrementar contadores generales
            pipe.hincrby(f"metrics:counters:{event_type}", "total", 1)
            pipe.hincrby(f"metrics:counters:{event_type}:daily:{datetime.utcnow().date()}", "count", 1)
            
            # Guardar evento para procesamiento posterior
            event_timestamp = datetime.utcnow().timestamp()
            pipe.zadd(
                f"metrics:events:{event_type}",
                {json.dumps(event): event_timestamp}
            )
            
            # Mantener solo los últimos 1000 eventos
            pipe.zremrangebyrank(f"metrics:events:{event_type}", 0, -1000)
        
        await pipe.execute()
    
    async def ingest_data(self, data: Dict[str, Any]):
        """Ingesta de datos al pipeline de analytics"""
        # Validar y enriquecer datos
        enriched_data = await self._enrich_data(data)
        
        # Añadir al pipeline de procesamiento
        await self.pipeline_queue.put([enriched_data])
        
        # Trigger para métricas críticas en tiempo real
        if data.get('type') in ['lead_conversion', 'lead_qualified', 'interaction_completed']:
            await self._trigger_critical_metric_update(data)
    
    async def _enrich_data(self, data: Dict) -> Dict:
        """Enriquece los datos con información adicional"""
        enriched = data.copy()
        enriched['timestamp'] = datetime.utcnow().isoformat()
        enriched['processing_id'] = f"{data.get('type', 'unknown')}_{datetime.utcnow().timestamp()}"
        
        # Añadir metadatos según el tipo
        if data.get('type') == 'lead_created':
            enriched['lead_score'] = await self._calculate_lead_score(data)
        elif data.get('type') == 'lead_conversion':
            enriched['conversion_value'] = await self._calculate_conversion_value(data)
        
        return enriched
    
    async def _calculate_lead_score(self, lead_data: Dict) -> float:
        """Calcula el score de un lead basado en datos reales"""
        try:
            # Si tenemos un lead_id, obtener datos reales de la base de datos
            if 'lead_id' in lead_data:
                stmt = select(Lead).where(Lead.id == lead_data['lead_id'])
                result = await self.db.execute(stmt)
                lead = result.scalar_one_or_none()
                
                if lead:
                    return lead.score or 0.0
            
            # Fallback a cálculo básico
            score = 0.0
            if lead_data.get('email'):
                score += 10
            if lead_data.get('company'):
                score += 15
            if lead_data.get('job_title') in ['director', 'manager', 'ceo']:
                score += 20
            
            return min(score, 100)
            
        except Exception as e:
            print(f"Error calculating lead score: {e}")
            return 0.0
    
    async def _calculate_conversion_value(self, conversion_data: Dict) -> float:
        """Calcula el valor de una conversión"""
        base_value = conversion_data.get('amount', 0)
        
        # Aplicar multiplicadores según el tipo de lead
        if conversion_data.get('lead_type') == 'enterprise':
            base_value *= 1.5
        elif conversion_data.get('lead_type') == 'premium':
            base_value *= 1.2
        
        return base_value
    
    async def _trigger_critical_metric_update(self, data: Dict):
        """Actualiza métricas críticas inmediatamente"""
        metric_type = data.get('type')
        
        if metric_type == 'lead_conversion':
            await self.calculate_conversion_metrics()
        elif metric_type == 'lead_qualified':
            await self.calculate_lead_quality_metrics()
        elif metric_type == 'interaction_completed':
            await self.calculate_engagement_metrics()
    
    async def _auto_refresh_metrics(self):
        """Auto-actualiza métricas según su configuración"""
        while True:
            try:
                current_time = datetime.utcnow()
                
                for metric_key, config in self.metrics_config.items():
                    # Verificar si necesita actualización
                    last_update_key = f"metrics:last_update:{metric_key}"
                    last_update = await self.redis.get(last_update_key)
                    
                    should_update = False
                    if not last_update:
                        should_update = True
                    else:
                        last_update_time = datetime.fromisoformat(last_update)
                        if (current_time - last_update_time).seconds >= config.refresh_interval:
                            should_update = True
                    
                    if should_update:
                        await self._update_metric(metric_key, config)
                        await self.redis.set(last_update_key, current_time.isoformat())
                
                # Esperar antes del próximo ciclo
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Error in auto refresh: {e}")
                await asyncio.sleep(60)
    
    async def _update_metric(self, metric_key: str, config: MetricConfig):
        """Actualiza una métrica específica"""
        print(f"📊 Updating metric: {metric_key}")
        
        try:
            if metric_key == 'active_leads':
                value = await self.calculate_active_leads()
            elif metric_key == 'conversion_rate':
                value = await self.calculate_conversion_rate()
            elif metric_key == 'response_time':
                value = await self.calculate_avg_response_time()
            elif metric_key == 'lead_velocity':
                value = await self.calculate_lead_velocity()
            elif metric_key == 'workflow_efficiency':
                value = await self.calculate_workflow_efficiency()
            else:
                value = None
            
            if value is not None:
                # Guardar en caché
                await self.redis.setex(
                    f"metrics:calculated:{metric_key}",
                    config.cache_ttl,
                    json.dumps({
                        'value': value,
                        'timestamp': datetime.utcnow().isoformat(),
                        'config': config.__dict__
                    })
                )
        except Exception as e:
            print(f"❌ Error updating metric {metric_key}: {e}")
    
    # MÉTRICAS REALES CON BASE DE DATOS
    async def calculate_active_leads(self) -> int:
        """Calcula cantidad de leads activos"""
        stmt = select(func.count(Lead.id)).where(
            and_(
                Lead.is_active == True,
                Lead.created_at >= datetime.utcnow() - timedelta(days=30)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def calculate_conversion_rate(self) -> float:
        """Calcula tasa de conversión de los últimos 30 días"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        # Total de leads
        total_stmt = select(func.count(Lead.id)).where(
            and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date
            )
        )
        total_result = await self.db.execute(total_stmt)
        total_leads = total_result.scalar() or 0
        
        # Leads convertidos
        converted_stmt = select(func.count(Lead.id)).where(
            and_(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date,
                Lead.status == LeadStatus.CONVERTED
            )
        )
        converted_result = await self.db.execute(converted_stmt)
        converted_leads = converted_result.scalar() or 0
        
        if total_leads > 0:
            return round((converted_leads / total_leads) * 100, 2)
        return 0.0
    
    async def calculate_avg_response_time(self) -> float:
        """Calcula tiempo promedio de respuesta en minutos"""
        stmt = select(func.avg(Interaction.response_time_ms)).where(
            and_(
                Interaction.created_at >= datetime.utcnow() - timedelta(days=7),
                Interaction.response_time_ms.isnot(None)
            )
        )
        result = await self.db.execute(stmt)
        avg_ms = result.scalar() or 0
        
        return round(avg_ms / 60000, 2)  # Convertir a minutos
    
    async def calculate_lead_velocity(self) -> float:
        """Calcula la velocidad de generación de leads"""
        current_month = datetime.utcnow().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        
        # Leads del mes actual
        current_stmt = select(func.count(Lead.id)).where(
            and_(
                Lead.created_at >= current_month,
                Lead.created_at < next_month
            )
        )
        current_result = await self.db.execute(current_stmt)
        current_leads = current_result.scalar() or 0
        
        # Leads del mes anterior
        last_stmt = select(func.count(Lead.id)).where(
            and_(
                Lead.created_at >= last_month,
                Lead.created_at < current_month
            )
        )
        last_result = await self.db.execute(last_stmt)
        last_leads = last_result.scalar() or 0
        
        if last_leads > 0:
            velocity = ((current_leads - last_leads) / last_leads) * 100
            return round(velocity, 2)
        return 100.0 if current_leads > 0 else 0.0
    
    async def calculate_workflow_efficiency(self) -> float:
        """Calcula eficiencia de workflows (completados vs totales)"""
        stmt = select(
            func.count(WorkflowExecution.id),
            func.sum(func.cast(WorkflowExecution.status == 'completed', Integer))
        ).where(
            WorkflowExecution.started_at >= datetime.utcnow() - timedelta(days=30)
        )
        
        result = await self.db.execute(stmt)
        total, completed = result.fetchone() or (0, 0)
        
        if total > 0:
            efficiency = (completed / total) * 100
            return round(efficiency, 2)
        return 0.0
    
    # MÉTRICAS COMPUESTAS PARA DASHBOARD
    async def get_executive_dashboard(self, days: int = 30) -> Dict[str, Any]:
        """Obtiene datos completos para dashboard ejecutivo"""
        cache_key = f"dashboard:executive:{days}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        dashboard_data = {
            'summary_metrics': {
                'active_leads': await self.calculate_active_leads(),
                'conversion_rate': await self.calculate_conversion_rate(),
                'avg_response_time': await self.calculate_avg_response_time(),
                'lead_velocity': await self.calculate_lead_velocity(),
                'workflow_efficiency': await self.calculate_workflow_efficiency()
            },
            'channel_performance': await self.get_channel_performance(days),
            'conversion_funnel': await self.get_conversion_funnel(days),
            'recent_activity': await self.get_recent_activity(10)
        }
        
        # Cachear por 5 minutos
        await self.redis.setex(cache_key, 300, json.dumps(dashboard_data))
        return dashboard_data
    
    async def get_channel_performance(self, days: int) -> List[Dict[str, Any]]:
        """Obtiene performance por canal"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(
            Lead.source,
            func.count(Lead.id).label('total_leads'),
            func.avg(Lead.score).label('avg_score'),
            func.sum(func.cast(Lead.is_qualified, Integer)).label('qualified_leads')
        ).where(
            Lead.created_at >= start_date
        ).group_by(Lead.source)
        
        result = await self.db.execute(stmt)
        channels_data = []
        
        for source, total, avg_score, qualified in result:
            conversion_rate = (qualified / total * 100) if total > 0 else 0
            channels_data.append({
                'channel': source or 'unknown',
                'leads_count': total,
                'avg_score': float(avg_score or 0),
                'conversion_rate': round(conversion_rate, 2),
                'qualified_leads': qualified
            })
        
        return sorted(channels_data, key=lambda x: x['leads_count'], reverse=True)
    
    async def get_conversion_funnel(self, days: int) -> Dict[str, Any]:
        """Obtiene datos del funnel de conversión"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Contar leads por etapa
        stmt = select(
            func.count(Lead.id),
            func.sum(func.cast(Lead.is_qualified, Integer)),
            func.sum(func.cast(Lead.status == LeadStatus.HOT, Integer)),
            func.sum(func.cast(Lead.status == LeadStatus.CONVERTED, Integer))
        ).where(Lead.created_at >= start_date)
        
        result = await self.db.execute(stmt)
        total, qualified, hot, converted = result.fetchone() or (0, 0, 0, 0)
        
        return {
            'stages': [
                {'name': 'Leads Totales', 'count': total, 'percentage': 100},
                {'name': 'Cualificados', 'count': qualified, 
                 'percentage': (qualified / total * 100) if total > 0 else 0},
                {'name': 'Calientes', 'count': hot,
                 'percentage': (hot / total * 100) if total > 0 else 0},
                {'name': 'Convertidos', 'count': converted,
                 'percentage': (converted / total * 100) if total > 0 else 0}
            ],
            'conversion_rates': {
                'total_to_qualified': (qualified / total * 100) if total > 0 else 0,
                'qualified_to_hot': (hot / qualified * 100) if qualified > 0 else 0,
                'hot_to_converted': (converted / hot * 100) if hot > 0 else 0,
                'overall': (converted / total * 100) if total > 0 else 0
            }
        }
    
    async def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene actividad reciente"""
        # Últimas interacciones
        stmt = select(Interaction).options(
            selectinload(Interaction.lead)
        ).order_by(Interaction.created_at.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        interactions = result.scalars().all()
        
        activity = []
        for interaction in interactions:
            activity.append({
                'type': 'interaction',
                'timestamp': interaction.created_at.isoformat(),
                'lead_name': interaction.lead.name if interaction.lead else 'Unknown',
                'message': interaction.user_message[:100] + '...' if interaction.user_message else 'No message',
                'platform': interaction.platform
            })
        
        return activity
    
    async def clear_cache(self, pattern: str = "metrics:*") -> int:
        """Limpia el cache de analytics"""
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0