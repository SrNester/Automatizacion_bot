import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, text, case
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from ..models.integration import Lead, LeadStatus, ExternalLead, SyncLog, IntegrationProvider
from ..models.interaction import Interaction, ConversationSummary, ConversationStatus
from ..core.database import get_db

logger = logging.getLogger(__name__)

class LeadService:
    """Servicio completo para gestión de leads con métodos robustos y optimizados"""
    
    def __init__(self, db: Session):
        self.db = db
        self.batch_size = 100  # Tamaño de lote para operaciones masivas
    
    @staticmethod
    def create_lead(db: Session, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo lead en la base de datos con validación robusta.
        """
        try:
            # Validaciones básicas
            if not lead_data:
                return {"success": False, "error": "Datos del lead requeridos"}
            
            # Validar email único si se proporciona
            if lead_data.get("email"):
                existing_lead = db.query(Lead).filter(
                    Lead.email == lead_data["email"].lower().strip()
                ).first()
                
                if existing_lead:
                    logger.warning(f"Lead con email {lead_data['email']} ya existe")
                    return {
                        "success": False, 
                        "error": f"Ya existe un lead con el email: {lead_data['email']}",
                        "existing_lead_id": existing_lead.id
                    }

            # Validar teléfono único si se proporciona
            if lead_data.get("phone"):
                existing_lead = db.query(Lead).filter(
                    Lead.phone == lead_data["phone"].strip()
                ).first()
                
                if existing_lead:
                    logger.warning(f"Lead con teléfono {lead_data['phone']} ya existe")
                    return {
                        "success": False,
                        "error": f"Ya existe un lead con el teléfono: {lead_data['phone']}",
                        "existing_lead_id": existing_lead.id
                    }

            # Preparar datos con valores por defecto
            now = datetime.utcnow()
            processed_data = {
                "email": lead_data.get("email", "").lower().strip() if lead_data.get("email") else None,
                "name": lead_data.get("name", "").strip(),
                "phone": lead_data.get("phone", "").strip(),
                "company": lead_data.get("company", "").strip(),
                "job_title": lead_data.get("job_title", "").strip(),
                "source": lead_data.get("source", "unknown"),
                "utm_campaign": lead_data.get("utm_campaign"),
                "interests": lead_data.get("interests"),
                "budget_range": lead_data.get("budget_range"),
                "timeline": lead_data.get("timeline"),
                "score": float(lead_data.get("score", 25.0)),
                "status": lead_data.get("status", LeadStatus.COLD.value),
                "is_qualified": lead_data.get("is_qualified", False),
                "is_active": True,
                "first_interaction": lead_data.get("first_interaction", now),
                "last_interaction": lead_data.get("last_interaction", now),
                "created_at": now,
                "updated_at": now
            }

            # Validar score en rango válido
            if not (0 <= processed_data["score"] <= 100):
                return {"success": False, "error": "El score debe estar entre 0 y 100"}

            new_lead = Lead(**processed_data)
            
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
            
            logger.info(f"Lead creado exitosamente: {new_lead.id} - {new_lead.email}")
            
            return {
                "success": True,
                "lead": new_lead,
                "lead_id": new_lead.id
            }
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error de integridad creando lead: {e}")
            return {"success": False, "error": "Error de duplicación de datos"}
        except Exception as e:
            db.rollback()
            logger.error(f"Error inesperado creando lead: {e}")
            return {"success": False, "error": f"Error creando lead: {str(e)}"}

    @staticmethod
    def get_lead(db: Session, lead_id: int, include_relations: bool = False) -> Optional[Lead]:
        """
        Obtiene un lead por su ID con opción de incluir relaciones.
        """
        try:
            query = db.query(Lead).filter(Lead.id == lead_id)
            
            if include_relations:
                query = query.options(
                    joinedload(Lead.interactions),
                    joinedload(Lead.external_leads),
                    joinedload(Lead.conversation_summaries)
                )
            
            lead = query.first()
            
            if not lead:
                logger.debug(f"Lead {lead_id} no encontrado")
                return None
                
            return lead
            
        except Exception as e:
            logger.error(f"Error obteniendo lead {lead_id}: {e}")
            return None

    @staticmethod
    def get_lead_by_email(db: Session, email: str, include_relations: bool = False) -> Optional[Lead]:
        """
        Obtiene un lead por su dirección de correo electrónico.
        """
        try:
            query = db.query(Lead).filter(
                Lead.email == email.lower().strip(),
                Lead.is_active == True
            )
            
            if include_relations:
                query = query.options(joinedload(Lead.interactions))
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo lead por email {email}: {e}")
            return None

    @staticmethod
    def get_lead_by_phone(db: Session, phone: str, include_relations: bool = False) -> Optional[Lead]:
        """
        Obtiene un lead por su número de teléfono.
        """
        try:
            query = db.query(Lead).filter(
                Lead.phone == phone.strip(),
                Lead.is_active == True
            )
            
            if include_relations:
                query = query.options(joinedload(Lead.interactions))
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo lead por teléfono {phone}: {e}")
            return None

    @staticmethod
    def find_lead_by_identifier(db: Session, identifier: str) -> Optional[Lead]:
        """
        Busca un lead por email, teléfono o ID de forma inteligente.
        """
        try:
            # Intentar como ID primero
            if identifier.isdigit():
                lead = LeadService.get_lead(db, int(identifier), include_relations=True)
                if lead:
                    return lead
            
            # Buscar por email
            if "@" in identifier:
                lead = LeadService.get_lead_by_email(db, identifier, include_relations=True)
                if lead:
                    return lead
            
            # Buscar por teléfono (remover caracteres no numéricos)
            phone_clean = ''.join(filter(str.isdigit, identifier))
            if len(phone_clean) >= 8:  # Número de teléfono válido mínimo
                lead = LeadService.get_lead_by_phone(db, phone_clean, include_relations=True)
                if lead:
                    return lead
            
            return None
            
        except Exception as e:
            logger.error(f"Error buscando lead por identificador {identifier}: {e}")
            return None

    @staticmethod
    def update_lead(db: Session, lead_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza un lead existente con validación robusta.
        """
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            # Campos que se pueden actualizar con validación
            updatable_fields = {
                'name': str,
                'phone': str,
                'company': str,
                'job_title': str,
                'source': str,
                'utm_campaign': str,
                'interests': str,
                'budget_range': str,
                'timeline': str,
                'is_qualified': bool,
                'is_active': bool,
                'score': float,
                'status': str
            }
            
            changes = []
            for field, field_type in updatable_fields.items():
                if field in update_data:
                    try:
                        # Convertir y validar tipo
                        if field_type == bool:
                            new_value = bool(update_data[field])
                        elif field_type == float:
                            new_value = float(update_data[field])
                            if field == 'score' and not (0 <= new_value <= 100):
                                return {"success": False, "error": "Score debe estar entre 0 y 100"}
                        else:
                            new_value = str(update_data[field]) if update_data[field] is not None else None
                        
                        old_value = getattr(lead, field)
                        if old_value != new_value:
                            setattr(lead, field, new_value)
                            changes.append({
                                "field": field,
                                "old_value": old_value,
                                "new_value": new_value
                            })
                            
                    except (ValueError, TypeError) as e:
                        return {"success": False, "error": f"Valor inválido para campo {field}: {str(e)}"}
            
            # Validaciones de negocio
            if 'email' in update_data and update_data['email'] != lead.email:
                # Verificar que el nuevo email no exista
                existing = db.query(Lead).filter(
                    Lead.email == update_data['email'].lower().strip(),
                    Lead.id != lead_id
                ).first()
                if existing:
                    return {"success": False, "error": "El nuevo email ya está en uso por otro lead"}
                lead.email = update_data['email'].lower().strip()
                changes.append({
                    "field": "email",
                    "old_value": lead.email,
                    "new_value": update_data['email']
                })
            
            lead.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(lead)
            
            logger.info(f"Lead {lead_id} actualizado: {len(changes)} cambios")
            
            return {
                "success": True,
                "lead": lead,
                "changes": changes,
                "updated_at": lead.updated_at.isoformat()
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error de base de datos actualizando lead {lead_id}: {e}")
            return {"success": False, "error": f"Error de base de datos: {str(e)}"}
        except Exception as e:
            db.rollback()
            logger.error(f"Error inesperado actualizando lead {lead_id}: {e}")
            return {"success": False, "error": f"Error inesperado: {str(e)}"}

    @staticmethod
    def delete_lead(db: Session, lead_id: int, hard_delete: bool = False) -> Dict[str, Any]:
        """
        Elimina un lead (soft delete por defecto, hard delete opcional).
        """
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            if hard_delete:
                # Eliminación permanente (solo para testing o limpieza)
                db.delete(lead)
                action = "hard_deleted"
                logger.warning(f"Lead {lead_id} eliminado permanentemente")
            else:
                # Soft delete (marcar como inactivo)
                lead.is_active = False
                lead.updated_at = datetime.utcnow()
                action = "soft_deleted"
                logger.info(f"Lead {lead_id} marcado como inactivo")
            
            db.commit()
            
            return {
                "success": True,
                "lead_id": lead_id,
                "action": action,
                "deleted_at": datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error eliminando lead {lead_id}: {e}")
            return {"success": False, "error": f"Error de base de datos: {str(e)}"}

    @staticmethod
    def update_lead_score_and_status(db: Session, lead_id: int, new_score: float, 
                                   update_reason: str = "automated_scoring") -> Dict[str, Any]:
        """
        Actualiza el score y el status de un lead con tracking de cambios.
        """
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            # Validar score
            if not (0 <= new_score <= 100):
                return {"success": False, "error": "El score debe estar entre 0 y 100"}
            
            old_score = lead.score
            old_status = lead.status
            
            # Actualizar score
            lead.score = new_score
            
            # Determinar nuevo status basado en score
            if new_score >= 75:
                new_status = LeadStatus.HOT.value
            elif new_score >= 50:
                new_status = LeadStatus.WARM.value
            elif new_score >= 25:
                new_status = LeadStatus.COLD.value
            else:
                new_status = LeadStatus.COLD.value
            
            # Si el score es muy alto, marcar como cualificado
            if new_score >= 80 and not lead.is_qualified:
                lead.is_qualified = True
                qualification_change = True
            else:
                qualification_change = False
            
            lead.status = new_status
            lead.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(lead)
            
            # Registrar cambio de score
            score_change = {
                "lead_id": lead_id,
                "old_score": old_score,
                "new_score": new_score,
                "old_status": old_status,
                "new_status": new_status,
                "change_amount": new_score - old_score,
                "update_reason": update_reason,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Score actualizado para lead {lead_id}: {old_score} → {new_score}")
            
            return {
                "success": True,
                "lead": lead,
                "score_change": score_change,
                "qualification_changed": qualification_change
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error actualizando score del lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def qualify_lead(db: Session, lead_id: int, qualification_notes: str = "", 
                   qualifier: str = "system") -> Dict[str, Any]:
        """
        Califica un lead como cualificado con registro de auditoría.
        """
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": "Lead no encontrado"}
            
            if lead.is_qualified:
                return {"success": False, "error": "El lead ya está cualificado"}
            
            # Actualizar lead
            lead.is_qualified = True
            lead.status = LeadStatus.HOT.value
            lead.score = max(lead.score, 80.0)  # Mínimo 80 para cualificado
            lead.updated_at = datetime.utcnow()
            
            # Crear registro de cualificación
            qualification_record = {
                "lead_id": lead_id,
                "qualified_by": qualifier,
                "qualification_notes": qualification_notes,
                "qualified_at": datetime.utcnow().isoformat(),
                "previous_score": lead.score,
                "new_score": lead.score
            }
            
            db.commit()
            db.refresh(lead)
            
            logger.info(f"Lead {lead_id} cualificado por {qualifier}")
            
            return {
                "success": True,
                "lead": lead,
                "qualification_record": qualification_record
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error cualificando lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_leads_paginated(db: Session, page: int = 1, per_page: int = 50, 
                          filters: Dict[str, Any] = None, sort_by: str = "updated_at",
                          sort_desc: bool = True) -> Dict[str, Any]:
        """
        Obtiene leads paginados con filtros y ordenamiento.
        """
        try:
            query = db.query(Lead).filter(Lead.is_active == True)
            
            # Aplicar filtros
            if filters:
                query = LeadService._apply_filters(query, filters)
            
            # Aplicar ordenamiento
            sort_field = getattr(Lead, sort_by, Lead.updated_at)
            if sort_desc:
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
            
            # Paginación
            total_leads = query.count()
            total_pages = (total_leads + per_page - 1) // per_page
            page = max(1, min(page, total_pages))
            offset = (page - 1) * per_page
            
            leads = query.offset(offset).limit(per_page).all()
            
            return {
                "success": True,
                "leads": leads,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_leads": total_leads,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                },
                "filters": filters or {},
                "sort": {"by": sort_by, "desc": sort_desc}
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo leads paginados: {e}")
            return {"success": False, "error": str(e), "leads": [], "pagination": {}}

    @staticmethod
    def _apply_filters(query, filters: Dict[str, Any]):
        """Aplica filtros a la query de leads"""
        
        if filters.get("status"):
            query = query.filter(Lead.status == filters["status"])
        
        if filters.get("min_score") is not None:
            query = query.filter(Lead.score >= float(filters["min_score"]))
        
        if filters.get("max_score") is not None:
            query = query.filter(Lead.score <= float(filters["max_score"]))
        
        if filters.get("is_qualified") is not None:
            query = query.filter(Lead.is_qualified == bool(filters["is_qualified"]))
        
        if filters.get("source"):
            query = query.filter(Lead.source == filters["source"])
        
        if filters.get("search_term"):
            search_term = f"%{filters['search_term']}%"
            query = query.filter(
                or_(
                    Lead.name.ilike(search_term),
                    Lead.email.ilike(search_term),
                    Lead.company.ilike(search_term),
                    Lead.phone.ilike(search_term)
                )
            )
        
        if filters.get("created_after"):
            try:
                created_after = datetime.fromisoformat(filters["created_after"].replace('Z', '+00:00'))
                query = query.filter(Lead.created_at >= created_after)
            except ValueError:
                pass
        
        if filters.get("created_before"):
            try:
                created_before = datetime.fromisoformat(filters["created_before"].replace('Z', '+00:00'))
                query = query.filter(Lead.created_at <= created_before)
            except ValueError:
                pass
        
        return query

    @staticmethod
    def get_leads_by_status(db: Session, status: str, active_only: bool = True) -> Dict[str, Any]:
        """
        Obtiene leads por estado con métricas.
        """
        try:
            query = db.query(Lead).filter(Lead.status == status)
            if active_only:
                query = query.filter(Lead.is_active == True)
            
            leads = query.order_by(Lead.updated_at.desc()).all()
            count = len(leads)
            avg_score = db.query(func.avg(Lead.score)).filter(
                Lead.status == status,
                Lead.is_active == True
            ).scalar() or 0
            
            return {
                "success": True,
                "status": status,
                "leads": leads,
                "count": count,
                "average_score": round(float(avg_score), 2),
                "qualified_count": sum(1 for lead in leads if lead.is_qualified)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo leads por status {status}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def calculate_conversion_rate(db: Session, days: int = 30, segment: str = None) -> Dict[str, Any]:
        """
        Calcula la tasa de conversión para un período con análisis segmentado.
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            base_query = db.query(Lead).filter(
                Lead.created_at >= since_date,
                Lead.is_active == True
            )
            
            if segment:
                base_query = base_query.filter(Lead.source == segment)
            
            total_leads = base_query.count()
            
            converted_leads = base_query.filter(
                Lead.status == LeadStatus.CONVERTED.value
            ).count()
            
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0
            
            # Métricas adicionales
            qualified_leads = base_query.filter(Lead.is_qualified == True).count()
            hot_leads = base_query.filter(Lead.status == LeadStatus.HOT.value).count()
            
            return {
                "success": True,
                "period_days": days,
                "segment": segment,
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "qualified_leads": qualified_leads,
                "hot_leads": hot_leads,
                "conversion_rate": round(conversion_rate, 2),
                "qualification_rate": round((qualified_leads / total_leads * 100) if total_leads > 0 else 0, 2),
                "hot_lead_rate": round((hot_leads / total_leads * 100) if total_leads > 0 else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculando tasa de conversión: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_lead_sources_analytics(db: Session, days: int = 30, limit: int = 10) -> Dict[str, Any]:
        """
        Obtiene analytics detallados de fuentes de leads.
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            sources_data = db.query(
                Lead.source,
                func.count(Lead.id).label('total_leads'),
                func.avg(Lead.score).label('avg_score'),
                func.sum(case([(Lead.status == LeadStatus.CONVERTED.value, 1)], else_=0)).label('converted'),
                func.sum(case([(Lead.is_qualified == True, 1)], else_=0)).label('qualified')
            ).filter(
                Lead.created_at >= since_date,
                Lead.is_active == True,
                Lead.source.isnot(None)
            ).group_by(Lead.source).order_by(func.count(Lead.id).desc()).limit(limit).all()
            
            analytics = []
            for source in sources_data:
                conversion_rate = (source.converted / source.total_leads * 100) if source.total_leads > 0 else 0
                qualification_rate = (source.qualified / source.total_leads * 100) if source.total_leads > 0 else 0
                
                analytics.append({
                    "source": source.source,
                    "total_leads": source.total_leads,
                    "average_score": round(float(source.avg_score or 0), 2),
                    "converted_leads": source.converted,
                    "qualified_leads": source.qualified,
                    "conversion_rate": round(conversion_rate, 2),
                    "qualification_rate": round(qualification_rate, 2),
                    "efficiency_score": round((conversion_rate + qualification_rate) / 2, 2)
                })
            
            return {
                "success": True,
                "period_days": days,
                "sources_analytics": analytics,
                "total_sources": len(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo analytics de fuentes: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_leads_without_recent_interaction(db: Session, days: int = 7, 
                                           min_score: float = 0) -> Dict[str, Any]:
        """
        Obtiene leads sin interacciones recientes para reactivación.
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Subquery para leads con interacciones recientes
            recent_interactions = db.query(Interaction.lead_id).filter(
                Interaction.created_at >= cutoff_date
            ).distinct()
            
            query = db.query(Lead).filter(
                Lead.is_active == True,
                Lead.score >= min_score,
                Lead.id.not_in(recent_interactions)
            )
            
            leads = query.order_by(Lead.score.desc(), Lead.last_interaction.desc()).all()
            
            return {
                "success": True,
                "leads": leads,
                "count": len(leads),
                "days_without_interaction": days,
                "min_score": min_score,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo leads sin interacción reciente: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_conversation_history(db: Session, lead_id: int, limit: int = 20, 
                               include_analysis: bool = False) -> Dict[str, Any]:
        """
        Obtiene el historial de conversaciones para un lead con análisis opcional.
        """
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            interactions = db.query(Interaction).filter(
                Interaction.lead_id == lead_id
            ).order_by(Interaction.created_at.desc()).limit(limit).all()
            
            history = []
            for interaction in reversed(interactions):  # Orden cronológico
                entry = {
                    "id": interaction.id,
                    "timestamp": interaction.created_at.isoformat(),
                    "platform": interaction.platform or "unknown",
                    "message_type": interaction.user_message_type or "text"
                }
                
                if interaction.user_message:
                    entry.update({
                        "role": "user",
                        "content": interaction.user_message,
                        "intent": interaction.intent_detected,
                        "confidence": interaction.confidence_score,
                        "sentiment": interaction.sentiment_score
                    })
                
                if interaction.bot_response:
                    # Solo agregar entrada de bot si hay respuesta
                    if interaction.user_message:
                        history.append(entry)
                        entry = entry.copy()  # Nueva entrada para la respuesta
                    
                    entry.update({
                        "role": "assistant",
                        "content": interaction.bot_response,
                        "response_time_ms": interaction.response_time_ms
                    })
                
                history.append(entry)
            
            result = {
                "success": True,
                "lead_id": lead_id,
                "conversation_history": history,
                "total_interactions": len(interactions),
                "last_interaction": lead.last_interaction.isoformat() if lead.last_interaction else None
            }
            
            if include_analysis:
                result["analysis"] = LeadService._analyze_conversation_history(history, lead)
            
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo historial de conversación para lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _analyze_conversation_history(history: List[Dict], lead: Lead) -> Dict[str, Any]:
        """Analiza el historial de conversaciones"""
        
        if not history:
            return {}
        
        user_messages = [entry for entry in history if entry.get("role") == "user"]
        bot_responses = [entry for entry in history if entry.get("role") == "assistant"]
        
        # Métricas básicas
        analysis = {
            "total_user_messages": len(user_messages),
            "total_bot_responses": len(bot_responses),
            "conversation_ratio": len(bot_responses) / len(user_messages) if user_messages else 0,
            "average_response_time": None,
            "detected_intents": [],
            "sentiment_trend": "neutral"
        }
        
        # Tiempos de respuesta
        response_times = [entry.get("response_time_ms", 0) for entry in bot_responses if entry.get("response_time_ms")]
        if response_times:
            analysis["average_response_time"] = sum(response_times) / len(response_times)
        
        # Intenciones detectadas
        intents = [entry.get("intent") for entry in user_messages if entry.get("intent")]
        analysis["detected_intents"] = list(set(intents))
        
        # Sentiment promedio
        sentiments = [entry.get("sentiment", 0) for entry in user_messages if entry.get("sentiment") is not None]
        if sentiments:
            avg_sentiment = sum(sentiments) / len(sentiments)
            analysis["average_sentiment"] = round(avg_sentiment, 3)
            analysis["sentiment_trend"] = "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
        
        return analysis

    @staticmethod
    def save_interaction(db: Session, lead_id: int, user_message: str = None, 
                        bot_response: str = None, platform: str = "whatsapp",
                        message_type: str = "text", intent_detected: str = None,
                        confidence_score: float = None, sentiment_score: float = None,
                        buying_signals: bool = False) -> Dict[str, Any]:
        """
        Guarda una interacción entre el usuario y el bot con validación robusta.
        """
        try:
            # Validar lead existente
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {lead_id} no encontrado"}
            
            # Validar que haya al menos un mensaje
            if not user_message and not bot_response:
                return {"success": False, "error": "Se requiere al menos un mensaje de usuario o bot"}
            
            interaction = Interaction(
                lead_id=lead_id,
                user_message=user_message,
                bot_response=bot_response,
                platform=platform,
                user_message_type=message_type,
                intent_detected=intent_detected,
                confidence_score=confidence_score,
                sentiment_score=sentiment_score,
                buying_signals_detected=buying_signals,
                created_at=datetime.utcnow()
            )
            
            db.add(interaction)
            
            # Actualizar last_interaction del lead
            lead.last_interaction = datetime.utcnow()
            lead.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(interaction)
            
            logger.info(f"Interacción guardada para lead {lead_id}: {len(user_message or '')} chars user, {len(bot_response or '')} chars bot")
            
            return {
                "success": True,
                "interaction": interaction,
                "interaction_id": interaction.id,
                "lead_updated": True
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error guardando interacción para lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def bulk_update_lead_status(db: Session, lead_ids: List[int], new_status: str, 
                              update_reason: str = "bulk_update") -> Dict[str, Any]:
        """
        Actualiza el status de múltiples leads con manejo de errores.
        """
        try:
            if not lead_ids:
                return {"success": False, "error": "Lista de lead IDs vacía"}
            
            # Validar status
            valid_statuses = [status.value for status in LeadStatus]
            if new_status not in valid_statuses:
                return {"success": False, "error": f"Status inválido. Válidos: {valid_statuses}"}
            
            # Actualizar en lote
            updated_count = db.query(Lead).filter(
                Lead.id.in_(lead_ids),
                Lead.is_active == True
            ).update({
                "status": new_status,
                "updated_at": datetime.utcnow()
            }, synchronize_session=False)
            
            db.commit()
            
            logger.info(f"Status actualizado para {updated_count} leads: {new_status}")
            
            return {
                "success": True,
                "updated_count": updated_count,
                "new_status": new_status,
                "update_reason": update_reason,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error en actualización masiva de status: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_lead_metrics(db: Session, days: int = 30, segment: str = None) -> Dict[str, Any]:
        """
        Obtiene métricas completas de leads con segmentación.
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            base_query = db.query(Lead).filter(
                Lead.created_at >= since_date,
                Lead.is_active == True
            )
            
            if segment:
                base_query = base_query.filter(Lead.source == segment)
            
            # Métricas básicas
            total_leads = base_query.count()
            
            # Distribución por status
            status_distribution = db.query(
                Lead.status,
                func.count(Lead.id).label('count')
            ).filter(
                Lead.created_at >= since_date,
                Lead.is_active == True
            )
            
            if segment:
                status_distribution = status_distribution.filter(Lead.source == segment)
            
            status_distribution = status_distribution.group_by(Lead.status).all()
            
            # Métricas avanzadas
            converted_leads = base_query.filter(Lead.status == LeadStatus.CONVERTED.value).count()
            qualified_leads = base_query.filter(Lead.is_qualified == True).count()
            hot_leads = base_query.filter(Lead.status == LeadStatus.HOT.value).count()
            
            avg_score = db.query(func.avg(Lead.score)).filter(
                Lead.created_at >= since_date,
                Lead.is_active == True
            )
            
            if segment:
                avg_score = avg_score.filter(Lead.source == segment)
            
            avg_score = avg_score.scalar() or 0
            
            # Tendencias (últimos 7 días vs período completo)
            recent_date = datetime.utcnow() - timedelta(days=7)
            recent_leads = base_query.filter(Lead.created_at >= recent_date).count()
            
            return {
                "success": True,
                "period_days": days,
                "segment": segment,
                "total_leads": total_leads,
                "recent_leads_7d": recent_leads,
                "leads_by_status": {status: count for status, count in status_distribution},
                "converted_leads": converted_leads,
                "qualified_leads": qualified_leads,
                "hot_leads": hot_leads,
                "average_score": round(float(avg_score), 2),
                "conversion_rate": round((converted_leads / total_leads * 100) if total_leads > 0 else 0, 2),
                "qualification_rate": round((qualified_leads / total_leads * 100) if total_leads > 0 else 0, 2),
                "hot_lead_rate": round((hot_leads / total_leads * 100) if total_leads > 0 else 0, 2),
                "growth_rate": round(((recent_leads / (total_leads - recent_leads)) * 100) if (total_leads - recent_leads) > 0 else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas de leads: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def export_leads(db: Session, lead_ids: List[int] = None, 
                   format: str = "json") -> Dict[str, Any]:
        """
        Exporta datos de leads para reporting en múltiples formatos.
        """
        try:
            query = db.query(Lead).filter(Lead.is_active == True)
            if lead_ids:
                query = query.filter(Lead.id.in_(lead_ids))
            
            leads = query.all()
            
            if format == "json":
                export_data = []
                for lead in leads:
                    lead_data = {
                        "id": lead.id,
                        "email": lead.email,
                        "name": lead.name,
                        "phone": lead.phone,
                        "company": lead.company,
                        "job_title": lead.job_title,
                        "source": lead.source,
                        "score": lead.score,
                        "status": lead.status,
                        "is_qualified": lead.is_qualified,
                        "budget_range": lead.budget_range,
                        "timeline": lead.timeline,
                        "first_interaction": lead.first_interaction.isoformat() if lead.first_interaction else None,
                        "last_interaction": lead.last_interaction.isoformat() if lead.last_interaction else None,
                        "created_at": lead.created_at.isoformat(),
                        "updated_at": lead.updated_at.isoformat()
                    }
                    export_data.append(lead_data)
                
                return {
                    "success": True,
                    "format": format,
                    "leads_count": len(export_data),
                    "exported_at": datetime.utcnow().isoformat(),
                    "data": export_data
                }
            
            else:
                return {"success": False, "error": f"Formato no soportado: {format}"}
                
        except Exception as e:
            logger.error(f"Error exportando leads: {e}")
            return {"success": False, "error": str(e)}

# Funciones de conveniencia mejoradas
def create_lead(db: Session, lead_data: Dict[str, Any]) -> Dict[str, Any]:
    return LeadService.create_lead(db, lead_data)

def get_lead(db: Session, lead_id: int, include_relations: bool = False) -> Optional[Lead]:
    return LeadService.get_lead(db, lead_id, include_relations)

def get_lead_by_email(db: Session, email: str) -> Optional[Lead]:
    return LeadService.get_lead_by_email(db, email)

def update_lead_score_and_status(db: Session, lead_id: int, new_score: float) -> Dict[str, Any]:
    return LeadService.update_lead_score_and_status(db, lead_id, new_score)

def get_leads_paginated(db: Session, page: int = 1, per_page: int = 50, **kwargs) -> Dict[str, Any]:
    return LeadService.get_leads_paginated(db, page, per_page, **kwargs)

def get_lead_metrics(db: Session, days: int = 30) -> Dict[str, Any]:
    return LeadService.get_lead_metrics(db, days)

def save_interaction(db: Session, lead_id: int, user_message: str, bot_response: str, **kwargs) -> Dict[str, Any]:
    return LeadService.save_interaction(db, lead_id, user_message, bot_response, **kwargs)

def get_leads_by_date_range(db: Session, start_date: datetime, end_date: datetime):
    """Obtiene leads por rango de fecha"""
    # Implementar según tu modelo
    return []

def get_lead_growth_metrics(db: Session, start_date: datetime, end_date: datetime):
    """Obtiene métricas de crecimiento de leads"""
    return {
        "total_growth": 0,
        "growth_rate": 0,
        "weekly_growth": []
    }

def get_interaction_metrics(db: Session, start_date: datetime, end_date: datetime):
    """Obtiene métricas de interacciones"""
    return {
        "total_interactions": 0,
        "avg_interactions_per_lead": 0,
        "most_common_interaction_type": "message"
    }

def get_leads_by_status(db: Session):
    """Obtiene leads agrupados por status"""
    return []