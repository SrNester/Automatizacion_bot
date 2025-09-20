from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import json

from ..models.workflow import LeadSegment, LeadSegmentMembership
from ..models.lead import Lead
from ..models.interaction import Interaction, ConversationSummary
from ..core.database import get_db

class LeadSegmentationService:
    """Servicio para segmentación automática e inteligente de leads"""
    
    def __init__(self):
        self.predefined_segments = self._get_predefined_segments()
    
    def _get_predefined_segments(self) -> Dict[str, Dict]:
        """Define segmentos predeterminados comunes"""
        
        return {
            "hot_leads": {
                "name": "Hot Leads",
                "description": "Leads con alta probabilidad de conversión",
                "color": "#FF4444",
                "rules": [
                    {"field": "score", "operator": "gte", "value": 75},
                    {"field": "status", "operator": "in", "value": ["qualified", "opportunity"]}
                ],
                "priority": 1
            },
            "warm_leads": {
                "name": "Warm Leads", 
                "description": "Leads con interés moderado",
                "color": "#FFA500",
                "rules": [
                    {"field": "score", "operator": "gte", "value": 40},
                    {"field": "score", "operator": "lt", "value": 75}
                ],
                "priority": 2
            },
            "cold_leads": {
                "name": "Cold Leads",
                "description": "Leads con bajo engagement",
                "color": "#87CEEB", 
                "rules": [
                    {"field": "score", "operator": "lt", "value": 40}
                ],
                "priority": 3
            },
            "chatbot_engaged": {
                "name": "Chatbot Engaged",
                "description": "Leads que han interactuado con el chatbot",
                "color": "#32CD32",
                "rules": [
                    {"field": "source", "operator": "eq", "value": "chatbot"},
                    {"field": "last_interaction", "operator": "gte", "value": "7_days_ago"}
                ],
                "priority": 2
            },
            "high_value_company": {
                "name": "High Value Company",
                "description": "Leads de empresas grandes/conocidas",
                "color": "#8A2BE2",
                "rules": [
                    {"field": "company_size", "operator": "gte", "value": 100},
                    {"field": "company", "operator": "not_eq", "value": ""}
                ],
                "priority": 1
            },
            "demo_requested": {
                "name": "Demo Requested",
                "description": "Leads que solicitaron demo",
                "color": "#FFD700",
                "rules": [
                    {"field": "tags", "operator": "contains", "value": "demo_requested"}
                ],
                "priority": 1
            },
            "email_engaged": {
                "name": "Email Engaged",
                "description": "Leads que abren/clickean emails regularmente",
                "color": "#20B2AA",
                "rules": [
                    {"field": "email_opens_last_30d", "operator": "gte", "value": 3},
                    {"field": "email_clicks_last_30d", "operator": "gte", "value": 1}
                ],
                "priority": 2
            },
            "long_term_nurture": {
                "name": "Long Term Nurture",
                "description": "Leads para nurturing a largo plazo",
                "color": "#778899",
                "rules": [
                    {"field": "score", "operator": "gte", "value": 20},
                    {"field": "score", "operator": "lt", "value": 40},
                    {"field": "created_at", "operator": "lt", "value": "30_days_ago"}
                ],
                "priority": 3
            },
            "unresponsive": {
                "name": "Unresponsive",
                "description": "Leads sin actividad reciente",
                "color": "#696969",
                "rules": [
                    {"field": "last_activity", "operator": "lt", "value": "60_days_ago"},
                    {"field": "email_opens_last_60d", "operator": "eq", "value": 0}
                ],
                "priority": 4
            }
        }
    
    async def create_segment(self,
                           name: str,
                           description: str,
                           rules: List[Dict],
                           is_dynamic: bool = True,
                           color: str = "#4169E1",
                           created_by: str = "system",
                           db: Session = None) -> LeadSegment:
        """Crea un nuevo segmento"""
        
        if not db:
            db = next(get_db())
        
        segment = LeadSegment(
            name=name,
            description=description,
            rules=rules,
            is_dynamic=is_dynamic,
            color=color,
            created_by=created_by,
            is_active=True
        )
        
        db.add(segment)
        db.commit()
        db.refresh(segment)
        
        # Si es dinámico, calcular leads inmediatamente
        if is_dynamic:
            await self.recalculate_segment(segment.id, db)
        
        return segment
    
    async def setup_predefined_segments(self, db: Session = None) -> List[int]:
        """Configura segmentos predeterminados si no existen"""
        
        if not db:
            db = next(get_db())
        
        created_segments = []
        
        for segment_key, segment_data in self.predefined_segments.items():
            # Verificar si ya existe
            existing = db.query(LeadSegment)\
                .filter(LeadSegment.name == segment_data["name"])\
                .first()
            
            if not existing:
                segment = await self.create_segment(
                    name=segment_data["name"],
                    description=segment_data["description"],
                    rules=segment_data["rules"],
                    color=segment_data["color"],
                    created_by="predefined",
                    db=db
                )
                created_segments.append(segment.id)
                print(f"✅ Segmento creado: {segment_data['name']}")
        
        return created_segments
    
    async def recalculate_segment(self, segment_id: int, db: Session = None) -> Dict[str, int]:
        """Recalcula los leads que pertenecen a un segmento"""
        
        if not db:
            db = next(get_db())
        
        segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
        if not segment:
            return {"error": "Segmento no encontrado"}
        
        # Obtener leads que cumplen las reglas del segmento
        matching_leads = await self._get_leads_matching_rules(segment.rules, db)
        
        # Obtener membresías actuales
        current_memberships = db.query(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .all()
        
        current_lead_ids = {m.lead_id for m in current_memberships}
        matching_lead_ids = {lead.id for lead in matching_leads}
        
        # Leads que se deben agregar
        to_add = matching_lead_ids - current_lead_ids
        
        # Leads que se deben remover
        to_remove = current_lead_ids - matching_lead_ids
        
        # Agregar nuevos leads
        for lead_id in to_add:
            membership = LeadSegmentMembership(
                lead_id=lead_id,
                segment_id=segment_id,
                added_by="system",
                reason="automatic_segmentation",
                is_active=True
            )
            db.add(membership)
        
        # Remover leads que ya no califican
        for membership in current_memberships:
            if membership.lead_id in to_remove:
                membership.is_active = False
                membership.left_at = datetime.utcnow()
        
        # Actualizar contador del segmento
        segment.current_lead_count = len(matching_lead_ids)
        segment.last_calculated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "added": len(to_add),
            "removed": len(to_remove),
            "total": segment.current_lead_count
        }
    
    async def _get_leads_matching_rules(self, rules: List[Dict], db: Session) -> List[Lead]:
        """Obtiene leads que cumplen con las reglas especificadas"""
        
        query = db.query(Lead)
        
        # Aplicar cada regla (AND logic)
        for rule in rules:
            query = self._apply_rule_to_query(query, rule, db)
        
        return query.all()
    
    def _apply_rule_to_query(self, query, rule: Dict, db: Session):
        """Aplica una regla individual al query"""
        
        field = rule.get("field")
        operator = rule.get("operator")
        value = rule.get("value")
        
        # Procesar valores especiales como fechas relativas
        processed_value = self._process_rule_value(value)
        
        # Campos directos del lead
        if hasattr(Lead, field):
            lead_field = getattr(Lead, field)
            
            if operator == "eq":
                query = query.filter(lead_field == processed_value)
            elif operator == "not_eq":
                query = query.filter(lead_field != processed_value)
            elif operator == "gt":
                query = query.filter(lead_field > processed_value)
            elif operator == "lt":
                query = query.filter(lead_field < processed_value)
            elif operator == "gte":
                query = query.filter(lead_field >= processed_value)
            elif operator == "lte":
                query = query.filter(lead_field <= processed_value)
            elif operator == "in":
                query = query.filter(lead_field.in_(processed_value))
            elif operator == "contains":
                if field == "tags":
                    # Para JSON arrays
                    query = query.filter(lead_field.contains([processed_value]))
                else:
                    # Para strings
                    query = query.filter(lead_field.like(f"%{processed_value}%"))
        
        # Campos calculados que requieren joins o subqueries
        elif field == "last_interaction":
            if operator == "gte":
                cutoff_date = self._parse_relative_date(processed_value)
                query = query.join(Interaction)\
                    .filter(Interaction.created_at >= cutoff_date)
        
        elif field == "email_opens_last_30d":
            # Subquery para contar opens de email en últimos 30 días
            from ..models.workflow import EmailSend
            
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            opens_subquery = db.query(func.count(EmailSend.id))\
                .filter(EmailSend.lead_id == Lead.id)\
                .filter(EmailSend.opened_at >= thirty_days_ago)\
                .correlate(Lead)\
                .scalar_subquery()
            
            if operator == "gte":
                query = query.filter(opens_subquery >= processed_value)
            elif operator == "eq":
                query = query.filter(opens_subquery == processed_value)
        
        elif field == "email_clicks_last_30d":
            from ..models.workflow import EmailSend
            
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            clicks_subquery = db.query(func.count(EmailSend.id))\
                .filter(EmailSend.lead_id == Lead.id)\
                .filter(EmailSend.first_clicked_at >= thirty_days_ago)\
                .correlate(Lead)\
                .scalar_subquery()
            
            if operator == "gte":
                query = query.filter(clicks_subquery >= processed_value)
            elif operator == "eq":
                query = query.filter(clicks_subquery == processed_value)
        
        elif field == "email_opens_last_60d":
            from ..models.workflow import EmailSend
            
            sixty_days_ago = datetime.utcnow() - timedelta(days=60)
            opens_subquery = db.query(func.count(EmailSend.id))\
                .filter(EmailSend.lead_id == Lead.id)\
                .filter(EmailSend.opened_at >= sixty_days_ago)\
                .correlate(Lead)\
                .scalar_subquery()
            
            query = query.filter(opens_subquery == processed_value)
        
        elif field == "last_activity":
            # Última actividad considerando interacciones y emails
            if operator == "lt":
                cutoff_date = self._parse_relative_date(processed_value)
                
                # Subquery para última interacción
                last_interaction = db.query(func.max(Interaction.created_at))\
                    .filter(Interaction.lead_id == Lead.id)\
                    .correlate(Lead)\
                    .scalar_subquery()
                
                # Subquery para último email abierto
                from ..models.workflow import EmailSend
                last_email_open = db.query(func.max(EmailSend.opened_at))\
                    .filter(EmailSend.lead_id == Lead.id)\
                    .correlate(Lead)\
                    .scalar_subquery()
                
                # La actividad más reciente debe ser anterior al cutoff
                query = query.filter(
                    and_(
                        or_(last_interaction == None, last_interaction < cutoff_date),
                        or_(last_email_open == None, last_email_open < cutoff_date)
                    )
                )
        
        elif field == "company_size":
            # Campo que podría no existir directamente, usar metadata
            if operator == "gte":
                query = query.filter(Lead.metadata.contains({"company_size": {"$gte": processed_value}}))
        
        return query
    
    def _process_rule_value(self, value: Any) -> Any:
        """Procesa valores especiales como fechas relativas"""
        
        if isinstance(value, str):
            if value.endswith("_days_ago"):
                days = int(value.split("_")[0])
                return datetime.utcnow() - timedelta(days=days)
            elif value.endswith("_hours_ago"):
                hours = int(value.split("_")[0])
                return datetime.utcnow() - timedelta(hours=hours)
        
        return value
    
    def _parse_relative_date(self, value_str: str) -> datetime:
        """Parsea strings de fechas relativas"""
        
        if isinstance(value_str, datetime):
            return value_str
        
        if value_str.endswith("_days_ago"):
            days = int(value_str.split("_")[0])
            return datetime.utcnow() - timedelta(days=days)
        elif value_str.endswith("_hours_ago"):
            hours = int(value_str.split("_")[0])
            return datetime.utcnow() - timedelta(hours=hours)
        else:
            # Intentar parsear como fecha ISO
            try:
                return datetime.fromisoformat(value_str.replace('Z', '+00:00'))
            except:
                return datetime.utcnow()
    
    async def auto_segment_lead(self, lead_id: int, db: Session = None) -> List[str]:
        """Asigna automáticamente un lead a segmentos apropiados"""
        
        if not db:
            db = next(get_db())
        
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return []
        
        # Obtener todos los segmentos activos dinámicos
        active_segments = db.query(LeadSegment)\
            .filter(LeadSegment.is_active == True)\
            .filter(LeadSegment.is_dynamic == True)\
            .order_by(LeadSegment.priority)\
            .all()
        
        assigned_segments = []
        
        for segment in active_segments:
            # Verificar si el lead ya está en este segmento
            existing_membership = db.query(LeadSegmentMembership)\
                .filter(LeadSegmentMembership.lead_id == lead_id)\
                .filter(LeadSegmentMembership.segment_id == segment.id)\
                .filter(LeadSegmentMembership.is_active == True)\
                .first()
            
            if existing_membership:
                continue
            
            # Evaluar si el lead cumple las reglas
            if await self._lead_matches_rules(lead, segment.rules, db):
                # Agregar al segmento
                membership = LeadSegmentMembership(
                    lead_id=lead_id,
                    segment_id=segment.id,
                    added_by="auto_segmentation",
                    reason="automatic_assignment",
                    is_active=True
                )
                
                db.add(membership)
                assigned_segments.append(segment.name)
                
                # Actualizar contador del segmento
                segment.current_lead_count += 1
        
        db.commit()
        
        # Actualizar segment principal del lead (el de mayor prioridad)
        if assigned_segments:
            primary_segment = db.query(LeadSegment)\
                .join(LeadSegmentMembership)\
                .filter(LeadSegmentMembership.lead_id == lead_id)\
                .filter(LeadSegmentMembership.is_active == True)\
                .order_by(LeadSegment.priority)\
                .first()
            
            if primary_segment:
                lead.segment = primary_segment.name
                db.commit()
        
        return assigned_segments
    
    async def _lead_matches_rules(self, lead: Lead, rules: List[Dict], db: Session) -> bool:
        """Verifica si un lead específico cumple con las reglas"""
        
        for rule in rules:
            if not await self._evaluate_rule_for_lead(lead, rule, db):
                return False  # AND logic: todas las reglas deben cumplirse
        
        return True
    
    async def _evaluate_rule_for_lead(self, lead: Lead, rule: Dict, db: Session) -> bool:
        """Evalúa una regla individual para un lead específico"""
        
        field = rule.get("field")
        operator = rule.get("operator")
        expected_value = self._process_rule_value(rule.get("value"))
        
        # Obtener valor actual del campo
        if hasattr(lead, field):
            actual_value = getattr(lead, field)
        else:
            # Campos calculados
            if field == "last_interaction":
                latest_interaction = db.query(Interaction)\
                    .filter(Interaction.lead_id == lead.id)\
                    .order_by(Interaction.created_at.desc())\
                    .first()
                actual_value = latest_interaction.created_at if latest_interaction else None
            
            elif field == "email_opens_last_30d":
                from ..models.workflow import EmailSend
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                actual_value = db.query(EmailSend)\
                    .filter(EmailSend.lead_id == lead.id)\
                    .filter(EmailSend.opened_at >= thirty_days_ago)\
                    .count()
            
            elif field == "email_clicks_last_30d":
                from ..models.workflow import EmailSend
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                actual_value = db.query(EmailSend)\
                    .filter(EmailSend.lead_id == lead.id)\
                    .filter(EmailSend.first_clicked_at >= thirty_days_ago)\
                    .count()
            
            elif field == "email_opens_last_60d":
                from ..models.workflow import EmailSend
                sixty_days_ago = datetime.utcnow() - timedelta(days=60)
                actual_value = db.query(EmailSend)\
                    .filter(EmailSend.lead_id == lead.id)\
                    .filter(EmailSend.opened_at >= sixty_days_ago)\
                    .count()
            
            elif field == "company_size":
                actual_value = lead.metadata.get("company_size") if lead.metadata else None
            
            else:
                actual_value = None
        
        # Comparar valores
        return self._compare_values(actual_value, operator, expected_value)
    
    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compara valores según el operador"""
        
        if operator == "eq":
            return actual == expected
        elif operator == "not_eq":
            return actual != expected
        elif operator == "gt":
            return actual is not None and actual > expected
        elif operator == "lt":
            return actual is not None and actual < expected
        elif operator == "gte":
            return actual is not None and actual >= expected
        elif operator == "lte":
            return actual is not None and actual <= expected
        elif operator == "in":
            return actual in expected if isinstance(expected, list) else False
        elif operator == "contains":
            if isinstance(actual, list):
                return expected in actual
            elif isinstance(actual, str):
                return str(expected) in actual
            return False
        else:
            return False
    
    async def get_segment_analytics(self, segment_id: int, days: int = 30, db: Session = None) -> Dict[str, Any]:
        """Obtiene analytics detallados de un segmento"""
        
        if not db:
            db = next(get_db())
        
        segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
        if not segment:
            return {"error": "Segmento no encontrado"}
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Leads actuales en el segmento
        current_leads = db.query(Lead)\
            .join(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .all()
        
        # Histórico de membresías
        all_memberships = db.query(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.joined_at > since_date)\
            .all()
        
        # Métricas básicas
        total_current = len(current_leads)
        total_joined = len(all_memberships)
        total_left = len([m for m in all_memberships if m.left_at is not None])
        retention_rate = (total_current / total_joined) if total_joined > 0 else 0
        
        # Score promedio
        avg_score = sum(lead.score for lead in current_leads) / total_current if total_current > 0 else 0
        
        # Distribución por fuente
        source_distribution = {}
        for lead in current_leads:
            source = lead.source or "unknown"
            source_distribution[source] = source_distribution.get(source, 0) + 1
        
        # Distribución por score ranges
        score_distribution = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
        for lead in current_leads:
            if lead.score <= 25:
                score_distribution["0-25"] += 1
            elif lead.score <= 50:
                score_distribution["26-50"] += 1
            elif lead.score <= 75:
                score_distribution["51-75"] += 1
            else:
                score_distribution["76-100"] += 1
        
        # Performance de email en este segmento
        from ..models.workflow import EmailSend
        
        email_sends = db.query(EmailSend)\
            .join(Lead)\
            .join(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .filter(EmailSend.created_at > since_date)\
            .all()
        
        emails_sent = len(email_sends)
        emails_opened = len([e for e in email_sends if e.opened_at])
        emails_clicked = len([e for e in email_sends if e.first_clicked_at])
        
        email_open_rate = emails_opened / emails_sent if emails_sent > 0 else 0
        email_click_rate = emails_clicked / emails_sent if emails_sent > 0 else 0
        
        # Tendencia de crecimiento
        growth_data = await self._calculate_segment_growth(segment_id, days, db)
        
        return {
            "segment_id": segment_id,
            "segment_name": segment.name,
            "period_days": days,
            "current_metrics": {
                "total_leads": total_current,
                "avg_score": avg_score,
                "retention_rate": retention_rate
            },
            "historical_metrics": {
                "total_joined": total_joined,
                "total_left": total_left,
                "churn_rate": total_left / total_joined if total_joined > 0 else 0
            },
            "distributions": {
                "by_source": source_distribution,
                "by_score_range": score_distribution
            },
            "email_performance": {
                "emails_sent": emails_sent,
                "open_rate": email_open_rate,
                "click_rate": email_click_rate
            },
            "growth_trend": growth_data
        }
    
    async def _calculate_segment_growth(self, segment_id: int, days: int, db: Session) -> Dict[str, List]:
        """Calcula tendencia de crecimiento del segmento"""
        
        from collections import defaultdict
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Obtener todas las membresías en el período
        memberships = db.query(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.joined_at > since_date)\
            .all()
        
        daily_joins = defaultdict(int)
        daily_leaves = defaultdict(int)
        
        for membership in memberships:
            join_date = membership.joined_at.strftime("%Y-%m-%d")
            daily_joins[join_date] += 1
            
            if membership.left_at and membership.left_at > since_date:
                leave_date = membership.left_at.strftime("%Y-%m-%d")
                daily_leaves[leave_date] += 1
        
        # Generar serie de fechas completa
        dates = []
        current_date = since_date.date()
        end_date = datetime.utcnow().date()
        
        while current_date <= end_date:
            dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        
        # Calcular net growth diario
        joins = [daily_joins.get(date, 0) for date in dates]
        leaves = [daily_leaves.get(date, 0) for date in dates]
        net_growth = [j - l for j, l in zip(joins, leaves)]
        
        # Calcular tamaño acumulativo del segmento
        cumulative_size = []
        current_size = 0
        
        for growth in net_growth:
            current_size += growth
            cumulative_size.append(max(0, current_size))  # No puede ser negativo
        
        return {
            "dates": dates,
            "daily_joins": joins,
            "daily_leaves": leaves,
            "net_growth": net_growth,
            "cumulative_size": cumulative_size
        }
    
    async def recalculate_all_segments(self, db: Session = None) -> Dict[str, int]:
        """Recalcula todos los segmentos dinámicos"""
        
        if not db:
            db = next(get_db())
        
        dynamic_segments = db.query(LeadSegment)\
            .filter(LeadSegment.is_dynamic == True)\
            .filter(LeadSegment.is_active == True)\
            .all()
        
        results = {
            "total_segments": len(dynamic_segments),
            "total_changes": 0,
            "segment_results": {}
        }
        
        for segment in dynamic_segments:
            segment_result = await self.recalculate_segment(segment.id, db)
            
            results["total_changes"] += segment_result.get("added", 0) + segment_result.get("removed", 0)
            results["segment_results"][segment.name] = segment_result
            
            print(f"✅ Segmento '{segment.name}': +{segment_result.get('added', 0)} -{segment_result.get('removed', 0)} leads")
        
        return results
    
    async def get_lead_segments(self, lead_id: int, db: Session = None) -> List[Dict[str, Any]]:
        """Obtiene todos los segmentos de un lead"""
        
        if not db:
            db = next(get_db())
        
        segments = db.query(LeadSegment)\
            .join(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.lead_id == lead_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .all()
        
        segment_data = []
        
        for segment in segments:
            membership = db.query(LeadSegmentMembership)\
                .filter(LeadSegmentMembership.lead_id == lead_id)\
                .filter(LeadSegmentMembership.segment_id == segment.id)\
                .filter(LeadSegmentMembership.is_active == True)\
                .first()
            
            segment_data.append({
                "id": segment.id,
                "name": segment.name,
                "description": segment.description,
                "color": segment.color,
                "priority": segment.priority,
                "joined_at": membership.joined_at.isoformat() if membership else None,
                "added_by": membership.added_by if membership else None
            })
        
        return segment_data
    
    async def remove_lead_from_segment(self, lead_id: int, segment_id: int, reason: str = "manual", db: Session = None) -> bool:
        """Remueve manualmente un lead de un segmento"""
        
        if not db:
            db = next(get_db())
        
        membership = db.query(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.lead_id == lead_id)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .first()
        
        if membership:
            membership.is_active = False
            membership.left_at = datetime.utcnow()
            
            # Actualizar contador del segmento
            segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
            if segment:
                segment.current_lead_count -= 1
            
            db.commit()
            return True
        
        return False
    
    async def add_lead_to_segment(self, lead_id: int, segment_id: int, added_by: str = "manual", reason: str = "manual_assignment", db: Session = None) -> bool:
        """Agrega manualmente un lead a un segmento"""
        
        if not db:
            db = next(get_db())
        
        # Verificar si ya está en el segmento
        existing = db.query(LeadSegmentMembership)\
            .filter(LeadSegmentMembership.lead_id == lead_id)\
            .filter(LeadSegmentMembership.segment_id == segment_id)\
            .filter(LeadSegmentMembership.is_active == True)\
            .first()
        
        if existing:
            return False  # Ya está en el segmento
        
        # Crear nueva membresía
        membership = LeadSegmentMembership(
            lead_id=lead_id,
            segment_id=segment_id,
            added_by=added_by,
            reason=reason,
            is_active=True
        )
        
        db.add(membership)
        
        # Actualizar contador del segmento
        segment = db.query(LeadSegment).filter(LeadSegment.id == segment_id).first()
        if segment:
            segment.current_lead_count += 1
        
        db.commit()
        return True