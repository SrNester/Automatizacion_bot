import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import numpy as np
from collections import defaultdict

@dataclass
class MetricConfig:
    """Configuración para métricas del sistema"""
    name: str
    calculation_type: str  # 'sum', 'average', 'count', 'custom'
    refresh_interval: int  # segundos
    cache_ttl: int  # segundos
    aggregation_window: str  # 'hour', 'day', 'week', 'month'

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
            'mrr': MetricConfig(
                name='Monthly Recurring Revenue',
                calculation_type='sum',
                refresh_interval=3600,
                cache_ttl=7200,
                aggregation_window='month'
            ),
            'cac': MetricConfig(
                name='Customer Acquisition Cost',
                calculation_type='custom',
                refresh_interval=3600,
                cache_ttl=7200,
                aggregation_window='month'
            ),
            'clv': MetricConfig(
                name='Customer Lifetime Value',
                calculation_type='custom',
                refresh_interval=86400,
                cache_ttl=172800,
                aggregation_window='all'
            ),
            'conversion_rate': MetricConfig(
                name='Lead Conversion Rate',
                calculation_type='average',
                refresh_interval=1800,
                cache_ttl=3600,
                aggregation_window='week'
            ),
            'lead_velocity': MetricConfig(
                name='Lead Velocity Rate',
                calculation_type='custom',
                refresh_interval=3600,
                cache_ttl=7200,
                aggregation_window='month'
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
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in pipeline processing: {e}")
    
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
        timestamp = datetime.utcnow().isoformat()
        
        # Actualizar contadores en Redis
        pipe = self.redis.pipeline()
        
        for event in events:
            # Incrementar contadores generales
            pipe.hincrby(f"metrics:counters:{event_type}", "total", 1)
            pipe.hincrby(f"metrics:counters:{event_type}:daily:{datetime.utcnow().date()}", "count", 1)
            
            # Guardar evento para procesamiento posterior
            pipe.zadd(
                f"metrics:events:{event_type}",
                {json.dumps(event): datetime.utcnow().timestamp()}
            )
        
        await pipe.execute()
    
    async def ingest_data(self, data: Dict[str, Any]):
        """Ingesta de datos al pipeline de analytics"""
        # Validar y enriquecer datos
        enriched_data = await self._enrich_data(data)
        
        # Añadir al pipeline de procesamiento
        await self.pipeline_queue.put([enriched_data])
        
        # Trigger para métricas críticas en tiempo real
        if data.get('type') in ['conversion', 'purchase', 'churn']:
            await self._trigger_critical_metric_update(data)
    
    async def _enrich_data(self, data: Dict) -> Dict:
        """Enriquece los datos con información adicional"""
        enriched = data.copy()
        enriched['timestamp'] = datetime.utcnow().isoformat()
        enriched['processing_id'] = f"{data.get('type', 'unknown')}_{datetime.utcnow().timestamp()}"
        
        # Añadir metadatos según el tipo
        if data.get('type') == 'lead':
            enriched['lead_score'] = await self._calculate_lead_score(data)
        elif data.get('type') == 'conversion':
            enriched['conversion_value'] = await self._calculate_conversion_value(data)
        
        return enriched
    
    async def _calculate_lead_score(self, lead_data: Dict) -> float:
        """Calcula el score de un lead (versión simplificada)"""
        score = 0.0
        
        # Factores de scoring básicos
        if lead_data.get('email'):
            score += 10
        if lead_data.get('company_size', 0) > 100:
            score += 20
        if lead_data.get('budget', 0) > 10000:
            score += 30
        if lead_data.get('engagement_score', 0) > 50:
            score += 25
        
        return min(score, 100)
    
    async def _calculate_conversion_value(self, conversion_data: Dict) -> float:
        """Calcula el valor de una conversión"""
        base_value = conversion_data.get('amount', 0)
        
        # Aplicar multiplicadores según el tipo de cliente
        if conversion_data.get('customer_type') == 'enterprise':
            base_value *= 1.5
        elif conversion_data.get('customer_type') == 'premium':
            base_value *= 1.2
        
        return base_value
    
    async def _trigger_critical_metric_update(self, data: Dict):
        """Actualiza métricas críticas inmediatamente"""
        metric_type = data.get('type')
        
        if metric_type == 'conversion':
            await self.calculate_conversion_metrics()
        elif metric_type == 'purchase':
            await self.calculate_revenue_metrics()
        elif metric_type == 'churn':
            await self.calculate_retention_metrics()
    
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
                        last_update_time = datetime.fromisoformat(last_update.decode())
                        if (current_time - last_update_time).seconds >= config.refresh_interval:
                            should_update = True
                    
                    if should_update:
                        await self._update_metric(metric_key, config)
                        await self.redis.set(last_update_key, current_time.isoformat())
                
                # Esperar antes del próximo ciclo
                await asyncio.sleep(60)  # Verificar cada minuto
                
            except Exception as e:
                print(f"Error in auto refresh: {e}")
                await asyncio.sleep(60)
    
    async def _update_metric(self, metric_key: str, config: MetricConfig):
        """Actualiza una métrica específica"""
        print(f"📊 Updating metric: {metric_key}")
        
        if metric_key == 'mrr':
            value = await self.calculate_mrr()
        elif metric_key == 'cac':
            value = await self.calculate_cac()
        elif metric_key == 'clv':
            value = await self.calculate_clv()
        elif metric_key == 'conversion_rate':
            value = await self.calculate_conversion_metrics()
        elif metric_key == 'lead_velocity':
            value = await self.calculate_lead_velocity()
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
    
    async def calculate_mrr(self) -> float:
        """Calcula el Monthly Recurring Revenue"""
        # Obtener todas las suscripciones activas
        current_month = datetime.utcnow().replace(day=1)
        
        # Simulación - En producción esto vendría de la DB
        active_subscriptions = await self._get_active_subscriptions(current_month)
        
        mrr = sum(sub.get('monthly_value', 0) for sub in active_subscriptions)
        
        # Guardar histórico
        await self.redis.zadd(
            "metrics:mrr:history",
            {json.dumps({'value': mrr, 'date': current_month.isoformat()}): current_month.timestamp()}
        )
        
        return mrr
    
    async def calculate_cac(self) -> float:
        """Calcula el Customer Acquisition Cost"""
        # Obtener costos de marketing del último mes
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        marketing_spend = await self._get_marketing_spend(start_date, end_date)
        new_customers = await self._get_new_customers_count(start_date, end_date)
        
        if new_customers > 0:
            cac = marketing_spend / new_customers
        else:
            cac = 0
        
        return round(cac, 2)
    
    async def calculate_clv(self) -> float:
        """Calcula el Customer Lifetime Value"""
        # Fórmula simplificada: (Average Order Value) × (Purchase Frequency) × (Customer Lifespan)
        avg_order_value = await self._get_average_order_value()
        purchase_frequency = await self._get_purchase_frequency()
        avg_customer_lifespan = await self._get_average_customer_lifespan()
        
        clv = avg_order_value * purchase_frequency * avg_customer_lifespan
        
        return round(clv, 2)
    
    async def calculate_conversion_metrics(self) -> Dict[str, float]:
        """Calcula métricas de conversión"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        total_leads = await self._get_leads_count(start_date, end_date)
        converted_leads = await self._get_converted_leads_count(start_date, end_date)
        
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Calcular por fuente
        conversion_by_source = await self._get_conversion_by_source(start_date, end_date)
        
        return {
            'overall_rate': round(conversion_rate, 2),
            'by_source': conversion_by_source,
            'total_leads': total_leads,
            'converted': converted_leads
        }
    
    async def calculate_lead_velocity(self) -> float:
        """Calcula la velocidad de generación de leads"""
        current_month_leads = await self._get_leads_count(
            datetime.utcnow().replace(day=1),
            datetime.utcnow()
        )
        
        last_month_start = (datetime.utcnow().replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = datetime.utcnow().replace(day=1) - timedelta(days=1)
        last_month_leads = await self._get_leads_count(last_month_start, last_month_end)
        
        if last_month_leads > 0:
            velocity = ((current_month_leads - last_month_leads) / last_month_leads) * 100
        else:
            velocity = 100 if current_month_leads > 0 else 0
        
        return round(velocity, 2)
    
    async def calculate_revenue_metrics(self) -> Dict[str, Any]:
        """Calcula métricas de revenue"""
        metrics = {
            'mrr': await self.calculate_mrr(),
            'arr': await self.calculate_mrr() * 12,  # Annual Recurring Revenue
            'growth_rate': await self._calculate_revenue_growth_rate(),
            'churn_rate': await self._calculate_churn_rate(),
            'net_revenue_retention': await self._calculate_nrr()
        }
        return metrics
    
    async def calculate_retention_metrics(self) -> Dict[str, float]:
        """Calcula métricas de retención"""
        retention_rate = await self._calculate_retention_rate()
        churn_rate = await self._calculate_churn_rate()
        
        return {
            'retention_rate': retention_rate,
            'churn_rate': churn_rate,
            'ltv_to_cac': await self.calculate_clv() / await self.calculate_cac() if await self.calculate_cac() > 0 else 0
        }
    
    # Métodos auxiliares (simulados - en producción consultarían la DB real)
    async def _get_active_subscriptions(self, date: datetime) -> List[Dict]:
        """Obtiene suscripciones activas (simulado)"""
        # En producción: query a la base de datos
        return [
            {'id': 1, 'monthly_value': 99.99},
            {'id': 2, 'monthly_value': 199.99},
            {'id': 3, 'monthly_value': 299.99},
        ]
    
    async def _get_marketing_spend(self, start_date: datetime, end_date: datetime) -> float:
        """Obtiene el gasto en marketing (simulado)"""
        return 5000.0  # $5000 USD
    
    async def _get_new_customers_count(self, start_date: datetime, end_date: datetime) -> int:
        """Obtiene cantidad de nuevos clientes (simulado)"""
        return 25
    
    async def _get_average_order_value(self) -> float:
        """Obtiene valor promedio de orden (simulado)"""
        return 150.0
    
    async def _get_purchase_frequency(self) -> float:
        """Obtiene frecuencia de compra (simulado)"""
        return 2.5  # 2.5 compras por año
    
    async def _get_average_customer_lifespan(self) -> float:
        """Obtiene vida útil promedio del cliente en años (simulado)"""
        return 3.0  # 3 años
    
    async def _get_leads_count(self, start_date: datetime, end_date: datetime) -> int:
        """Obtiene cantidad de leads (simulado)"""
        return 150
    
    async def _get_converted_leads_count(self, start_date: datetime, end_date: datetime) -> int:
        """Obtiene cantidad de leads convertidos (simulado)"""
        return 22
    
    async def _get_conversion_by_source(self, start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """Obtiene conversión por fuente (simulado)"""
        return {
            'organic': 15.5,
            'paid_search': 22.3,
            'social': 8.7,
            'email': 28.9,
            'referral': 18.2
        }
    
    async def _calculate_revenue_growth_rate(self) -> float:
        """Calcula tasa de crecimiento de revenue (simulado)"""
        return 12.5  # 12.5% growth
    
    async def _calculate_churn_rate(self) -> float:
        """Calcula tasa de churn (simulado)"""
        return 5.2  # 5.2% churn
    
    async def _calculate_nrr(self) -> float:
        """Calcula Net Revenue Retention (simulado)"""
        return 110.0  # 110% NRR
    
    async def _calculate_retention_rate(self) -> float:
        """Calcula tasa de retención (simulado)"""
        return 94.8  # 94.8% retention