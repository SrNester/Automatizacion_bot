from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import asyncio

# Celery
from celery import Celery

# Base de datos
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

# Nuestros servicios
from ..services.lead_scoring import LeadScoringService
from ..services.lead_segmentation import LeadSegmentationService
from ..services.workflow_engine import WorkflowEngine, TriggerType
from ..core.database import get_db
from ..core.config import settings
from ..models.integration import Lead, LeadActivity
from ..models.workflow import LeadSegment

# Logger
logger = logging.getLogger("lead_processing")

@dataclass
class ProcessingResult:
    success: bool
    message: str
    processed_count: int = 0
    scored_count: int = 0
    enriched_count: int = 0
    segmented_count: int = 0
    error_count: int = 0
    details: Optional[Dict] = None

class LeadProcessingService:
    """
    Servicio completo de procesamiento de leads
    Maneja scoring, enriquecimiento, segmentación y limpieza
    """
    
    def __init__(self):
        self.scoring_service = LeadScoringService()
        self.segmentation_service = LeadSegmentationService()
        self.workflow_engine = WorkflowEngine()
        
        # Configuración de procesamiento
        self.processing_config = {
            'batch_size': 100,
            'max_retries': 3,
            'enrichment_timeout': 30,  # segundos
            'cleanup_days': 90  # días para limpiar leads inactivos
        }
        
        logger.info("LeadProcessingService inicializado")
    
    async def batch_score_leads(self, db: Session, batch_size: int = None) -> ProcessingResult:
        """
        Procesa scoring por lote de leads
        """
        
        batch_size = batch_size or self.processing_config['batch_size']
        logger.info(f"Iniciando scoring por lote para {batch_size} leads")
        
        try:
            # Obtener leads que necesitan scoring (sin score o modificados recientemente)
            leads = db.query(Lead).filter(
                or_(
                    Lead.score.is_(None),
                    Lead.updated_at > Lead.last_scored_at,
                    Lead.last_scored_at.is_(None)
                )
            ).limit(batch_size).all()
            
            if not leads:
                return ProcessingResult(
                    success=True,
                    message="No hay leads pendientes de scoring",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "scored": 0,
                "errors": 0,
                "score_changes": []
            }
            
            for lead in leads:
                try:
                    old_score = lead.score
                    
                    # Calcular nuevo score
                    new_score = await self.scoring_service.calculate_lead_score(lead, db)
                    
                    # Actualizar lead
                    lead.score = new_score
                    lead.last_scored_at = datetime.utcnow()
                    lead.score_updated_at = datetime.utcnow()
                    
                    results["scored"] += 1
                    
                    # Registrar cambio significativo de score
                    if old_score is not None and abs(new_score - old_score) >= 10:
                        results["score_changes"].append({
                            'lead_id': lead.id,
                            'old_score': old_score,
                            'new_score': new_score,
                            'change': new_score - old_score
                        })
                        
                        # Disparar workflow si hay cambio significativo
                        if abs(new_score - old_score) >= 20:
                            await self.workflow_engine.trigger_workflow(
                                TriggerType.SCORE_CHANGE,
                                lead.id,
                                {
                                    'old_score': old_score,
                                    'new_score': new_score,
                                    'change_amount': new_score - old_score
                                },
                                db
                            )
                    
                    results["processed"] += 1
                    logger.debug(f"Lead {lead.id} score actualizado: {old_score} -> {new_score}")
                    
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Error scoring lead {lead.id}: {str(e)}")
            
            db.commit()
            
            # Recalcular segmentación para leads con cambios significativos
            if results["score_changes"]:
                await self._recalculate_segmentation_for_leads(
                    [change['lead_id'] for change in results["score_changes"]], 
                    db
                )
            
            return ProcessingResult(
                success=results["errors"] == 0,
                message=f"Scoring por lote completado: {results['processed']} procesados, {results['scored']} scores actualizados, {results['errors']} errores",
                processed_count=results["processed"],
                scored_count=results["scored"],
                error_count=results["errors"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en scoring por lote: {str(e)}")
            return ProcessingResult(
                success=False,
                message=f"Error en scoring por lote: {str(e)}",
                error_count=batch_size
            )
    
    async def process_specific_leads(self, lead_ids: List[int], db: Session) -> ProcessingResult:
        """
        Procesa leads específicos (scoring + segmentación)
        """
        
        logger.info(f"Procesando {len(lead_ids)} leads específicos")
        
        try:
            leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
            
            if not leads:
                return ProcessingResult(
                    success=True,
                    message="No se encontraron leads para procesar",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "scored": 0,
                "segmented": 0,
                "errors": 0
            }
            
            for lead in leads:
                try:
                    # 1. Scoring
                    old_score = lead.score
                    new_score = await self.scoring_service.calculate_lead_score(lead, db)
                    lead.score = new_score
                    lead.last_scored_at = datetime.utcnow()
                    
                    results["scored"] += 1
                    
                    # 2. Segmentación
                    segments = await self.segmentation_service.calculate_lead_segments(lead, db)
                    if segments:
                        await self.segmentation_service.update_lead_segments(lead.id, segments, db)
                        results["segmented"] += 1
                    
                    results["processed"] += 1
                    
                    logger.debug(f"Lead {lead.id} procesado - Score: {new_score}, Segmentos: {len(segments)}")
                    
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Error procesando lead {lead.id}: {str(e)}")
            
            db.commit()
            
            return ProcessingResult(
                success=results["errors"] == 0,
                message=f"Procesamiento específico completado: {results['processed']} procesados, {results['scored']} scores, {results['segmented']} segmentados",
                processed_count=results["processed"],
                scored_count=results["scored"],
                segmented_count=results["segmented"],
                error_count=results["errors"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en procesamiento específico: {str(e)}")
            return ProcessingResult(
                success=False,
                message=f"Error en procesamiento específico: {str(e)}",
                error_count=len(lead_ids)
            )
    
    async def enrich_leads_data(self, db: Session, batch_size: int = None) -> ProcessingResult:
        """
        Enriquece datos de leads con información adicional
        """
        
        batch_size = batch_size or self.processing_config['batch_size']
        logger.info(f"Iniciando enriquecimiento de datos para {batch_size} leads")
        
        try:
            # Leads que necesitan enriquecimiento (datos básicos faltantes)
            leads = db.query(Lead).filter(
                or_(
                    Lead.company.is_(None),
                    Lead.phone.is_(None),
                    Lead.country.is_(None),
                    and_(
                        Lead.last_enriched_at.is_(None),
                        Lead.created_at < datetime.utcnow() - timedelta(days=7)
                    )
                )
            ).limit(batch_size).all()
            
            if not leads:
                return ProcessingResult(
                    success=True,
                    message="No hay leads pendientes de enriquecimiento",
                    processed_count=0
                )
            
            results = {
                "processed": 0,
                "enriched": 0,
                "errors": 0,
                "enrichment_details": []
            }
            
            for lead in leads:
                try:
                    enrichment_data = await self._enrich_lead_data(lead, db)
                    
                    if enrichment_data:
                        # Aplicar datos enriquecidos
                        updated_fields = []
                        for field, value in enrichment_data.items():
                            if value and not getattr(lead, field):
                                setattr(lead, field, value)
                                updated_fields.append(field)
                        
                        if updated_fields:
                            lead.last_enriched_at = datetime.utcnow()
                            results["enriched"] += 1
                            results["enrichment_details"].append({
                                'lead_id': lead.id,
                                'updated_fields': updated_fields
                            })
                            logger.debug(f"Lead {lead.id} enriquecido - Campos: {updated_fields}")
                    
                    results["processed"] += 1
                    
                except asyncio.TimeoutError:
                    results["errors"] += 1
                    logger.warning(f"Timeout en enriquecimiento del lead {lead.id}")
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Error enriqueciendo lead {lead.id}: {str(e)}")
            
            db.commit()
            
            return ProcessingResult(
                success=results["errors"] == 0,
                message=f"Enriquecimiento completado: {results['processed']} procesados, {results['enriched']} enriquecidos, {results['errors']} errores",
                processed_count=results["processed"],
                enriched_count=results["enriched"],
                error_count=results["errors"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en enriquecimiento por lote: {str(e)}")
            return ProcessingResult(
                success=False,
                message=f"Error en enriquecimiento por lote: {str(e)}",
                error_count=batch_size
            )
    
    async def cleanup_invalid_leads(self, db: Session) -> ProcessingResult:
        """
        Limpia leads inválidos o inactivos
        """
        
        logger.info("Iniciando limpieza de leads inválidos")
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.processing_config['cleanup_days'])
            
            # 1. Leads con email inválido
            invalid_email_leads = db.query(Lead).filter(
                and_(
                    Lead.email.isnot(None),
                    ~Lead.email.op('~')('^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
                    Lead.created_at < cutoff_date
                )
            ).all()
            
            # 2. Leads inactivos sin actividades
            inactive_leads = db.query(Lead).filter(
                and_(
                    ~Lead.id.in_(
                        db.query(LeadActivity.lead_id).distinct()
                    ),
                    Lead.created_at < cutoff_date,
                    Lead.score < 20  # Leads de baja calidad
                )
            ).all()
            
            # 3. Leads duplicados (mismo email)
            duplicate_leads = []
            duplicate_emails = db.query(Lead.email, func.count(Lead.id).label('count'))\
                .filter(Lead.email.isnot(None))\
                .group_by(Lead.email)\
                .having(func.count(Lead.id) > 1)\
                .all()
            
            for email, count in duplicate_emails:
                # Mantener el lead más reciente, eliminar los demás
                leads_to_keep = db.query(Lead)\
                    .filter(Lead.email == email)\
                    .order_by(desc(Lead.created_at))\
                    .first()
                
                if leads_to_keep:
                    duplicates = db.query(Lead)\
                        .filter(
                            Lead.email == email,
                            Lead.id != leads_to_keep.id
                        )\
                        .all()
                    duplicate_leads.extend(duplicates)
            
            leads_to_delete = invalid_email_leads + inactive_leads + duplicate_leads
            lead_ids_to_delete = [lead.id for lead in leads_to_delete]
            
            if not leads_to_delete:
                return ProcessingResult(
                    success=True,
                    message="No hay leads inválidos para limpiar",
                    processed_count=0
                )
            
            # Eliminar leads (soft delete o hard delete según configuración)
            deleted_count = 0
            for lead in leads_to_delete:
                try:
                    # Soft delete: marcar como inactivo
                    lead.is_active = False
                    lead.deleted_at = datetime.utcnow()
                    deleted_count += 1
                    logger.debug(f"Lead {lead.id} marcado como inactivo")
                except Exception as e:
                    logger.error(f"Error eliminando lead {lead.id}: {str(e)}")
            
            db.commit()
            
            return ProcessingResult(
                success=True,
                message=f"Limpieza completada: {deleted_count} leads marcados como inactivos",
                processed_count=len(leads_to_delete),
                details={
                    'invalid_email': len(invalid_email_leads),
                    'inactive': len(inactive_leads),
                    'duplicates': len(duplicate_leads),
                    'deleted_ids': lead_ids_to_delete
                }
            )
            
        except Exception as e:
            logger.error(f"Error en limpieza de leads: {str(e)}")
            return ProcessingResult(
                success=False,
                message=f"Error en limpieza de leads: {str(e)}",
                error_count=1
            )
    
    async def recalculate_all_scores(self, db: Session) -> ProcessingResult:
        """
        Recalcula scores para todos los leads (operación pesada)
        """
        
        logger.info("Iniciando recálculo completo de scores")
        
        try:
            total_leads = db.query(Lead).filter(Lead.is_active == True).count()
            batch_size = 500  # Procesar en lotes más pequeños
            
            results = {
                "total_leads": total_leads,
                "processed": 0,
                "scored": 0,
                "errors": 0
            }
            
            # Procesar en lotes
            for offset in range(0, total_leads, batch_size):
                leads = db.query(Lead)\
                    .filter(Lead.is_active == True)\
                    .offset(offset)\
                    .limit(batch_size)\
                    .all()
                
                for lead in leads:
                    try:
                        new_score = await self.scoring_service.calculate_lead_score(lead, db)
                        lead.score = new_score
                        lead.last_scored_at = datetime.utcnow()
                        lead.score_updated_at = datetime.utcnow()
                        
                        results["scored"] += 1
                        results["processed"] += 1
                        
                    except Exception as e:
                        results["errors"] += 1
                        logger.error(f"Error recalculando score lead {lead.id}: {str(e)}")
                
                db.commit()
                logger.info(f"Procesado lote {offset//batch_size + 1}/{(total_leads + batch_size - 1)//batch_size}")
            
            return ProcessingResult(
                success=results["errors"] == 0,
                message=f"Recálculo completo completado: {results['processed']} procesados, {results['scored']} scores actualizados, {results['errors']} errores",
                processed_count=results["processed"],
                scored_count=results["scored"],
                error_count=results["errors"],
                details=results
            )
            
        except Exception as e:
            logger.error(f"Error en recálculo completo: {str(e)}")
            return ProcessingResult(
                success=False,
                message=f"Error en recálculo completo: {str(e)}",
                error_count=1
            )
    
    async def _enrich_lead_data(self, lead: Lead, db: Session) -> Dict[str, Any]:
        """
        Enriquece datos del lead usando servicios externos
        """
        
        enrichment_data = {}
        
        try:
            # 1. Enriquecimiento basado en email (si está disponible)
            if lead.email and not lead.company:
                company_from_email = self._extract_company_from_email(lead.email)
                if company_from_email:
                    enrichment_data['company'] = company_from_email
            
            # 2. Enriquecimiento basado en dominio (si tenemos website)
            if lead.website and not lead.company:
                company_from_domain = await self._get_company_from_domain(lead.website)
                if company_from_domain:
                    enrichment_data['company'] = company_from_domain
            
            # 3. Enriquecimiento de ubicación (si tenemos país pero no ciudad)
            if lead.country and not lead.city:
                # Podrías integrar con una API de geolocalización aquí
                pass
            
            # 4. Enriquecimiento de industria (basado en compañía)
            if lead.company and not lead.industry:
                industry = await self._infer_industry_from_company(lead.company)
                if industry:
                    enrichment_data['industry'] = industry
            
            return enrichment_data
            
        except Exception as e:
            logger.error(f"Error en enriquecimiento de lead {lead.id}: {str(e)}")
            return {}
    
    def _extract_company_from_email(self, email: str) -> Optional[str]:
        """Extrae nombre de compañía del dominio del email"""
        
        try:
            domain = email.split('@')[1]
            company = domain.split('.')[0]
            return company.title() if company else None
        except:
            return None
    
    async def _get_company_from_domain(self, website: str) -> Optional[str]:
        """Obtiene nombre de compañía desde el dominio del website"""
        
        # Placeholder - en producción integrarías con una API como Clearbit
        try:
            domain = website.replace('https://', '').replace('http://', '').split('/')[0]
            company = domain.split('.')[0]
            return company.title() if company else None
        except:
            return None
    
    async def _infer_industry_from_company(self, company: str) -> Optional[str]:
        """Infiere industria basado en el nombre de la compañía"""
        
        # Placeholder - en producción usarías ML o base de datos de industrias
        industry_keywords = {
            'tech': ['tech', 'software', 'cloud', 'ai', 'data'],
            'finance': ['bank', 'financial', 'insurance', 'investment'],
            'healthcare': ['health', 'medical', 'hospital', 'pharma'],
            'education': ['school', 'university', 'college', 'education'],
            'retail': ['store', 'shop', 'retail', 'ecommerce']
        }
        
        company_lower = company.lower()
        for industry, keywords in industry_keywords.items():
            if any(keyword in company_lower for keyword in keywords):
                return industry
        
        return None
    
    async def _recalculate_segmentation_for_leads(self, lead_ids: List[int], db: Session):
        """Recalcula segmentación para leads específicos"""
        
        try:
            for lead_id in lead_ids:
                lead = db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    segments = await self.segmentation_service.calculate_lead_segments(lead, db)
                    await self.segmentation_service.update_lead_segments(lead_id, segments, db)
        except Exception as e:
            logger.error(f"Error recalculando segmentación: {str(e)}")

# ===========================================
# TAREAS CELERY
# ===========================================

# Instancia de Celery
celery_app = Celery("sales_automation")

@celery_app.task(name="lead_scoring_batch_task")
def lead_scoring_batch_task(batch_size: int = 100):
    """Tarea Celery para scoring por lote"""
    
    async def _score_batch():
        db = next(get_db())
        try:
            processor = LeadProcessingService()
            result = await processor.batch_score_leads(db, batch_size)
            logger.info(f"Scoring por lote completado: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_score_batch())

@celery_app.task(name="lead_enrichment_task")
def lead_enrichment_task(batch_size: int = 50):
    """Tarea Celery para enriquecimiento de leads"""
    
    async def _enrich_batch():
        db = next(get_db())
        try:
            processor = LeadProcessingService()
            result = await processor.enrich_leads_data(db, batch_size)
            logger.info(f"Enriquecimiento completado: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_enrich_batch())

@celery_app.task(name="lead_cleanup_task")
def lead_cleanup_task():
    """Tarea Celery para limpieza de leads"""
    
    async def _cleanup():
        db = next(get_db())
        try:
            processor = LeadProcessingService()
            result = await processor.cleanup_invalid_leads(db)
            logger.info(f"Limpieza de leads completada: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_cleanup())

@celery_app.task(name="recalculate_all_scores_task")
def recalculate_all_scores_task():
    """Tarea Celery para recálculo completo de scores"""
    
    async def _recalculate():
        db = next(get_db())
        try:
            processor = LeadProcessingService()
            result = await processor.recalculate_all_scores(db)
            logger.info(f"Recálculo completo completado: {result.message}")
            return result.__dict__
        finally:
            db.close()
    
    return asyncio.run(_recalculate())

# Configuración de tareas periódicas
from celery.schedules import crontab

celery_app.conf.beat_schedule.update({
    'lead-scoring-hourly': {
        'task': 'services.tasks.lead_processing.lead_scoring_batch_task',
        'schedule': crontab(minute=0),  # Cada hora
        'kwargs': {'batch_size': 200}
    },
    'lead-enrichment-daily': {
        'task': 'services.tasks.lead_processing.lead_enrichment_task',
        'schedule': crontab(hour=1, minute=0),  # 1 AM daily
        'kwargs': {'batch_size': 100}
    },
    'lead-cleanup-weekly': {
        'task': 'services.tasks.lead_processing.lead_cleanup_task',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Domingo 2 AM
    },
})

# Instancia global
lead_processing_service = LeadProcessingService()