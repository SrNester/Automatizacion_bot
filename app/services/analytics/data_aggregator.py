from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import pandas as pd

class DataAggregator:
    """Servicio de agregación y consolidación de datos"""
    
    def __init__(self, analytics_engine):
        self.engine = analytics_engine
        self.aggregation_rules = self._load_aggregation_rules()
    
    def _load_aggregation_rules(self) -> Dict:
        """Carga las reglas de agregación"""
        return {
            'revenue': {
                'sources': ['stripe', 'paypal', 'bank_transfer'],
                'aggregation': 'sum',
                'interval': 'daily'
            },
            'leads': {
                'sources': ['website', 'api', 'crm', 'bot'],
                'aggregation': 'count',
                'interval': 'hourly'
            },
            'conversions': {
                'sources': ['sales', 'marketing', 'bot'],
                'aggregation': 'count_and_sum',
                'interval': 'daily'
            },
            'performance': {
                'sources': ['system', 'api', 'bot'],
                'aggregation': 'average',
                'interval': 'minute'
            }
        }
    
    async def aggregate_data(self, data_type: str, period: Dict) -> Dict[str, Any]:
        """Agrega datos según el tipo y período especificado"""
        if data_type not in self.aggregation_rules:
            raise ValueError(f"Unknown data type: {data_type}")
        
        rule = self.aggregation_rules[data_type]
        
        # Recopilar datos de todas las fuentes
        raw_data = await self._collect_from_sources(rule['sources'], period)
        
        # Aplicar reglas de agregación
        aggregated = await self._apply_aggregation(raw_data, rule['aggregation'])
        
        # Aplicar intervalos de tiempo
        time_series = await self._create_time_series(aggregated, rule['interval'], period)
        
        return {
            'type': data_type,
            'period': period,
            'aggregated_value': aggregated,
            'time_series': time_series,
            'sources_breakdown': await self._breakdown_by_source(raw_data),
            'metadata': {
                'last_updated': datetime.utcnow().isoformat(),
                'sources_count': len(rule['sources']),
                'aggregation_method': rule['aggregation']
            }
        }
    
    async def _collect_from_sources(self, sources: List[str], period: Dict) -> List[Dict]:
        """Recopila datos de múltiples fuentes"""
        tasks = []
        for source in sources:
            tasks.append(self._fetch_source_data(source, period))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtrar errores y combinar resultados
        combined_data = []
        for result in results:
            if not isinstance(result, Exception):
                combined_data.extend(result)
        
        return combined_data
    
    async def _fetch_source_data(self, source: str, period: Dict) -> List[Dict]:
        """Obtiene datos de una fuente específica (simulado)"""
        # En producción: consultar API o DB real
        import random
        
        data = []
        current = period['start']
        while current <= period['end']:
            data.append({
                'source': source,
                'timestamp': current.isoformat(),
                'value': random.uniform(100, 1000),
                'count': random.randint(1, 50)
            })
            current += timedelta(hours=1)
        
        return data
    
    async def _apply_aggregation(self, data: List[Dict], method: str) -> Dict:
        """Aplica el método de agregación especificado"""
        if not data:
            return {'value': 0, 'count': 0}
        
        df = pd.DataFrame(data)
        
        if method == 'sum':
            return {
                'value': df['value'].sum(),
                'count': len(df)
            }
        elif method == 'count':
            return {
                'value': len(df),
                'count': len(df)
            }
        elif method == 'average':
            return {
                'value': df['value'].mean(),
                'count': len(df),
                'std': df['value'].std()
            }
        elif method == 'count_and_sum':
            return {
                'value': df['value'].sum(),
                'count': len(df),
                'average': df['value'].mean()
            }
        else:
            return {'value': 0, 'count': 0}
    
    async def _create_time_series(self, aggregated: Dict, interval: str, period: Dict) -> List[Dict]:
        """Crea una serie temporal con el intervalo especificado"""
        time_series = []
        
        # Determinar el delta basado en el intervalo
        if interval == 'minute':
            delta = timedelta(minutes=1)
        elif interval == 'hourly':
            delta = timedelta(hours=1)
        elif interval == 'daily':
            delta = timedelta(days=1)
        elif interval == 'weekly':
            delta = timedelta(weeks=1)
        else:
            delta = timedelta(days=1)
        
        current = period['start']
        while current <= period['end']:
            time_series.append({
                'timestamp': current.isoformat(),
                'value': aggregated.get('value', 0) / ((period['end'] - period['start']).total_seconds() / delta.total_seconds()),
                'interval': interval
            })
            current += delta
        
        return time_series
    
    async def _breakdown_by_source(self, data: List[Dict]) -> Dict:
        """Desglosa los datos por fuente"""
        breakdown = defaultdict(lambda: {'value': 0, 'count': 0})
        
        for item in data:
            source = item.get('source', 'unknown')
            breakdown[source]['value'] += item.get('value', 0)
            breakdown[source]['count'] += 1
        
        return dict(breakdown)
    
    async def aggregate_multi_dimensional(self, dimensions: List[str], metrics: List[str], period: Dict) -> pd.DataFrame:
        """Agrega datos en múltiples dimensiones"""
        # Recopilar datos para todas las métricas
        all_data = []
        for metric in metrics:
            if metric in self.aggregation_rules:
                data = await self.aggregate_data(metric, period)
                all_data.append(data)
        
        # Crear DataFrame multidimensional
        df_results = pd.DataFrame()
        
        for data in all_data:
            metric_name = data['type']
            for dimension in dimensions:
                if dimension == 'source':
                    for source, values in data['sources_breakdown'].items():
                        row = {
                            'dimension': dimension,
                            'dimension_value': source,
                            'metric': metric_name,
                            'value': values['value'],
                            'count': values['count']
                        }
                        df_results = pd.concat([df_results, pd.DataFrame([row])], ignore_index=True)
        
        return df_results
    
    async def calculate_growth_metrics(self, metric: str, periods: int = 12) -> Dict:
        """Calcula métricas de crecimiento histórico"""
        growth_data = []
        end_date = datetime.utcnow()
        
        for i in range(periods):
            period_end = end_date - timedelta(days=30 * i)
            period_start = period_end - timedelta(days=30)
            
            period_data = await self.aggregate_data(metric, {
                'start': period_start,
                'end': period_end
            })
            
            growth_data.append({
                'period': f"{period_end.strftime('%Y-%m')}",
                'value': period_data['aggregated_value']['value']
            })
        
        # Calcular métricas de crecimiento
        df = pd.DataFrame(growth_data)
        df['growth_rate'] = df['value'].pct_change() * 100
        
        return {
            'historical_data': growth_data,
            'average_growth_rate': df['growth_rate'].mean(),
            'compound_growth_rate': self._calculate_cagr(df['value'].iloc[-1], df['value'].iloc[0], periods),
            'volatility': df['growth_rate'].std(),
            'trend': 'growing' if df['growth_rate'].mean() > 0 else 'declining'
        }
    
    def _calculate_cagr(self, ending_value: float, beginning_value: float, periods: int) -> float:
        """Calcula Compound Annual Growth Rate"""
        if beginning_value <= 0:
            return 0
        return (((ending_value / beginning_value) ** (1/periods)) - 1) * 100