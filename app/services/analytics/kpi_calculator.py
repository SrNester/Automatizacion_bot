from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import statistics

class KPIType(Enum):
    """Tipos de KPIs soportados"""
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    CUSTOMER = "customer"
    PERFORMANCE = "performance"

class KPICalculator:
    """Calculadora de KPIs empresariales"""
    
    def __init__(self, analytics_engine):
        self.engine = analytics_engine
        self.kpi_definitions = self._load_kpi_definitions()
    
    def _load_kpi_definitions(self) -> Dict[str, Dict]:
        """Carga las definiciones de KPIs"""
        return {
            # Tier 1 - Executive KPIs
            'mrr': {
                'name': 'Monthly Recurring Revenue',
                'type': KPIType.FINANCIAL,
                'formula': 'sum_of_active_subscriptions',
                'unit': 'currency',
                'tier': 1
            },
            'arr': {
                'name': 'Annual Recurring Revenue',
                'type': KPIType.FINANCIAL,
                'formula': 'mrr * 12',
                'unit': 'currency',
                'tier': 1
            },
            'cac': {
                'name': 'Customer Acquisition Cost',
                'type': KPIType.FINANCIAL,
                'formula': 'marketing_spend / new_customers',
                'unit': 'currency',
                'tier': 1
            },
            'clv': {
                'name': 'Customer Lifetime Value',
                'type': KPIType.CUSTOMER,
                'formula': 'avg_order_value * purchase_frequency * customer_lifespan',
                'unit': 'currency',
                'tier': 1
            },
            'roi': {
                'name': 'Return on Investment',
                'type': KPIType.FINANCIAL,
                'formula': '(revenue - cost) / cost * 100',
                'unit': 'percentage',
                'tier': 1
            },
            
            # Tier 2 - Operational KPIs
            'conversion_rate': {
                'name': 'Conversion Rate',
                'type': KPIType.OPERATIONAL,
                'formula': 'conversions / visitors * 100',
                'unit': 'percentage',
                'tier': 2
            },
            'lead_velocity': {
                'name': 'Lead Velocity Rate',
                'type': KPIType.OPERATIONAL,
                'formula': '(current_leads - previous_leads) / previous_leads * 100',
                'unit': 'percentage',
                'tier': 2
            },
            'pipeline_velocity': {
                'name': 'Pipeline Velocity',
                'type': KPIType.OPERATIONAL,
                'formula': 'deals * win_rate * avg_deal_size / sales_cycle_length',
                'unit': 'currency_per_day',
                'tier': 2
            },
            'churn_rate': {
                'name': 'Customer Churn Rate',
                'type': KPIType.CUSTOMER,
                'formula': 'lost_customers / total_customers * 100',
                'unit': 'percentage',
                'tier': 2
            },
            'nps': {
                'name': 'Net Promoter Score',
                'type': KPIType.CUSTOMER,
                'formula': 'promoters_percentage - detractors_percentage',
                'unit': 'score',
                'tier': 2
            }
        }
    
    async def calculate_kpi(self, kpi_key: str, period: Optional[Dict] = None) -> Dict[str, Any]:
        """Calcula un KPI específico"""
        if kpi_key not in self.kpi_definitions:
            raise ValueError(f"KPI '{kpi_key}' not defined")
        
        definition = self.kpi_definitions[kpi_key]
        
        # Determinar período de cálculo
        if not period:
            period = self._get_default_period(kpi_key)
        
        # Calcular según el tipo
        if kpi_key == 'mrr':
            value = await self._calculate_mrr(period)
        elif kpi_key == 'arr':
            mrr = await self._calculate_mrr(period)
            value = mrr * 12
        elif kpi_key == 'cac':
            value = await self._calculate_cac(period)
        elif kpi_key == 'clv':
            value = await self._calculate_clv(period)
        elif kpi_key == 'roi':
            value = await self._calculate_roi(period)
        elif kpi_key == 'conversion_rate':
            value = await self._calculate_conversion_rate(period)
        elif kpi_key == 'lead_velocity':
            value = await self._calculate_lead_velocity(period)
        elif kpi_key == 'pipeline_velocity':
            value = await self._calculate_pipeline_velocity(period)
        elif kpi_key == 'churn_rate':
            value = await self._calculate_churn_rate(period)
        elif kpi_key == 'nps':
            value = await self._calculate_nps(period)
        else:
            value = 0
        
        # Calcular trending
        trend = await self._calculate_trend(kpi_key, value, period)
        
        # Calcular benchmark comparison
        benchmark = await self._get_benchmark(kpi_key)
        
        return {
            'kpi': kpi_key,
            'name': definition['name'],
            'value': value,
            'unit': definition['unit'],
            'tier': definition['tier'],
            'period': period,
            'trend': trend,
            'benchmark': benchmark,
            'status': self._evaluate_status(value, benchmark),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def calculate_all_kpis(self, tier: Optional[int] = None) -> List[Dict]:
        """Calcula todos los KPIs de un tier específico o todos"""
        results = []
        
        for kpi_key, definition in self.kpi_definitions.items():
            if tier is None or definition['tier'] == tier:
                try:
                    kpi_data = await self.calculate_kpi(kpi_key)
                    results.append(kpi_data)
                except Exception as e:
                    print(f"Error calculating KPI {kpi_key}: {e}")
        
        return results
    
    def _get_default_period(self, kpi_key: str) -> Dict:
        """Obtiene el período por defecto para un KPI"""
        now = datetime.utcnow()
        
        if kpi_key in ['mrr', 'arr', 'cac', 'lead_velocity']:
            # Mes actual
            return {
                'start': now.replace(day=1),
                'end': now
            }
        elif kpi_key in ['clv', 'roi']:
            # Último año
            return {
                'start': now - timedelta(days=365),
                'end': now
            }
        else:
            # Últimos 30 días
            return {
                'start': now - timedelta(days=30),
                'end': now
            }
    
    async def _calculate_trend(self, kpi_key: str, current_value: float, period: Dict) -> Dict:
        """Calcula el trend de un KPI"""
        # Obtener valor del período anterior
        previous_period = self._get_previous_period(period)
        previous_value = await self._get_historical_value(kpi_key, previous_period)
        
        if previous_value and previous_value != 0:
            change_percentage = ((current_value - previous_value) / previous_value) * 100
            direction = 'up' if change_percentage > 0 else 'down' if change_percentage < 0 else 'stable'
        else:
            change_percentage = 0
            direction = 'stable'
        
        return {
            'direction': direction,
            'change_percentage': round(change_percentage, 2),
            'previous_value': previous_value
        }
    
    def _get_previous_period(self, period: Dict) -> Dict:
        """Obtiene el período anterior para comparación"""
        duration = period['end'] - period['start']
        return {
            'start': period['start'] - duration,
            'end': period['start']
        }
    
    async def _get_historical_value(self, kpi_key: str, period: Dict) -> Optional[float]:
        """Obtiene valor histórico de un KPI (simulado)"""
        # En producción: consultar base de datos histórica
        return 1000.0  # Valor simulado
    
    async def _get_benchmark(self, kpi_key: str) -> Dict:
        """Obtiene benchmark de la industria para un KPI"""
        benchmarks = {
            'mrr': {'industry_avg': 50000, 'top_percentile': 150000},
            'cac': {'industry_avg': 200, 'top_percentile': 100},
            'clv': {'industry_avg': 1500, 'top_percentile': 3000},
            'conversion_rate': {'industry_avg': 2.5, 'top_percentile': 5.0},
            'churn_rate': {'industry_avg': 5.0, 'top_percentile': 2.0}
        }
        return benchmarks.get(kpi_key, {'industry_avg': 0, 'top_percentile': 0})
    
    def _evaluate_status(self, value: float, benchmark: Dict) -> str:
        """Evalúa el status de un KPI comparado con benchmark"""
        if not benchmark or benchmark.get('industry_avg', 0) == 0:
            return 'neutral'
        
        industry_avg = benchmark['industry_avg']
        
        if value >= benchmark.get('top_percentile', industry_avg * 1.5):
            return 'excellent'
        elif value >= industry_avg:
            return 'good'
        elif value >= industry_avg * 0.8:
            return 'warning'
        else:
            return 'critical'
    
    # Métodos de cálculo específicos (simulados)
    async def _calculate_mrr(self, period: Dict) -> float:
        return 75000.0
    
    async def _calculate_cac(self, period: Dict) -> float:
        return 185.0
    
    async def _calculate_clv(self, period: Dict) -> float:
        return 2250.0
    
    async def _calculate_roi(self, period: Dict) -> float:
        return 325.0
    
    async def _calculate_conversion_rate(self, period: Dict) -> float:
        return 3.2
    
    async def _calculate_lead_velocity(self, period: Dict) -> float:
        return 15.5
    
    async def _calculate_pipeline_velocity(self, period: Dict) -> float:
        return 5000.0
    
    async def _calculate_churn_rate(self, period: Dict) -> float:
        return 4.5
    
    async def _calculate_nps(self, period: Dict) -> float:
        return 42.0