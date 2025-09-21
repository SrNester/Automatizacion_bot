import aiohttp
import json
import hashlib
import hmac
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...models.lead import Lead
from ...models.integration import Integration, ExternalLead, SyncLog
from ...services.lead_scoring import LeadScoringService
from ...services.workflow_engine import WorkflowEngine, TriggerType

class MetaAdsService:
    """Servicio completo para integración con Meta Ads (Facebook/Instagram)"""
    
    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.app_secret = settings.META_APP_SECRET
        self.ad_account_id = settings.META_AD_ACCOUNT_ID
        self.base_url = "https://graph.facebook.com/v18.0"
        
        # Servicios internos
        self.scoring_service = LeadScoringService()
        self.workflow_engine = WorkflowEngine()
        
        # Mapeo de campos Meta → campos internos
        self.field_mapping = {
            'email': 'email',
            'full_name': 'name',
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone_number': 'phone',
            'company_name': 'company',
            'job_title': 'job_title',
            'city': 'city',
            'state': 'state',
            'country': 'country',
            'zip_code': 'zip_code',
            'website': 'website'
        }
    
    async def setup_webhooks(self, webhook_url: str) -> Dict[str, Any]:
        """Configura webhooks para recibir leads en tiempo real"""
        
        url = f"{self.base_url}/me/subscriptions"
        
        webhook_data = {
            "object": "page",
            "callback_url": webhook_url,
            "fields": ["leadgen"],
            "verify_token": settings.META_WEBHOOK_VERIFY_TOKEN,
            "access_token": self.access_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=webhook_data) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print(f"✅ Meta webhook configurado exitosamente")
                        return {"success": True, "data": result}
                    else:
                        print(f"❌ Error configurando webhook: {result}")
                        return {"success": False, "error": result}
                        
        except Exception as e:
            print(f"❌ Excepción configurando webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_ad_accounts(self) -> List[Dict[str, Any]]:
        """Obtiene todas las cuentas de anuncios disponibles"""
        
        url = f"{self.base_url}/me/adaccounts"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,account_status,currency,timezone_name,business"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result:
                        return result["data"]
                    else:
                        print(f"❌ Error obteniendo ad accounts: {result}")
                        return []
                        
        except Exception as e:
            print(f"❌ Excepción obteniendo ad accounts: {e}")
            return []
    
    async def get_lead_gen_forms(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene todos los formularios de generación de leads"""
        
        url = f"{self.base_url}/{self.ad_account_id}/leadgen_forms"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,status,locale,privacy_policy_url,questions,created_time",
            "limit": limit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result:
                        return result["data"]
                    else:
                        print(f"❌ Error obteniendo formularios: {result}")
                        return []
                        
        except Exception as e:
            print(f"❌ Excepción obteniendo formularios: {e}")
            return []
    
    async def get_campaigns(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene campañas activas de la cuenta de anuncios"""
        
        url = f"{self.base_url}/{self.ad_account_id}/campaigns"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,status,objective,created_time,start_time,stop_time,spend,impressions,clicks,actions",
            "limit": limit,
            "filtering": [{"field": "status", "operator": "IN", "value": ["ACTIVE", "PAUSED"]}]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result:
                        return result["data"]
                    else:
                        print(f"❌ Error obteniendo campañas: {result}")
                        return []
                        
        except Exception as e:
            print(f"❌ Excepción obteniendo campañas: {e}")
            return []
    
    async def get_leads_from_form(self, form_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene leads de un formulario específico"""
        
        url = f"{self.base_url}/{form_id}/leads"
        params = {
            "access_token": self.access_token,
            "limit": limit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result:
                        return result["data"]
                    else:
                        print(f"❌ Error obteniendo leads del formulario {form_id}: {result}")
                        return []
                        
        except Exception as e:
            print(f"❌ Excepción obteniendo leads: {e}")
            return []
    
    async def process_webhook_lead(self, webhook_data: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
        """Procesa un lead recibido via webhook"""
        
        if not db:
            db = next(get_db())
        
        try:
            # Extraer datos del webhook
            entry = webhook_data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])
            
            processed_leads = []
            
            for change in changes:
                if change.get('field') != 'leadgen':
                    continue
                
                lead_data = change.get('value', {})
                leadgen_id = lead_data.get('leadgen_id')
                form_id = lead_data.get('form_id')
                ad_id = lead_data.get('ad_id')
                
                if not leadgen_id:
                    continue
                
                # Obtener datos completos del lead
                full_lead_data = await self.get_lead_details(leadgen_id)
                
                if full_lead_data:
                    # Procesar y guardar el lead
                    processed_lead = await self.create_lead_from_meta(
                        full_lead_data, form_id, ad_id, db
                    )
                    
                    if processed_lead:
                        processed_leads.append(processed_lead)
            
            return {
                "success": True,
                "processed_leads": len(processed_leads),
                "leads": processed_leads
            }
            
        except Exception as e:
            print(f"❌ Error procesando webhook lead: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_lead_details(self, leadgen_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene detalles completos de un lead específico"""
        
        url = f"{self.base_url}/{leadgen_id}"
        params = {
            "access_token": self.access_token,
            "fields": "id,created_time,ad_id,form_id,field_data"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "id" in result:
                        return result
                    else:
                        print(f"❌ Error obteniendo detalles del lead {leadgen_id}: {result}")
                        return None
                        
        except Exception as e:
            print(f"❌ Excepción obteniendo detalles del lead: {e}")
            return None
    
    async def create_lead_from_meta(self, 
                                  meta_lead_data: Dict[str, Any],
                                  form_id: str,
                                  ad_id: str,
                                  db: Session) -> Optional[Lead]:
        """Crea un lead en el sistema desde datos de Meta"""
        
        try:
            # Extraer y mapear campos
            field_data = meta_lead_data.get('field_data', [])
            mapped_data = self._map_meta_fields(field_data)
            
            # Verificar si el lead ya existe
            email = mapped_data.get('email')
            phone = mapped_data.get('phone')
            
            if email:
                existing_lead = db.query(Lead).filter(Lead.email == email).first()
                if existing_lead:
                    # Actualizar lead existente con nueva información
                    return await self._update_existing_lead(existing_lead, mapped_data, db)
            
            # Crear nuevo lead
            lead_score = await self._calculate_meta_lead_score(mapped_data, form_id, ad_id)
            
            new_lead = Lead(
                name=mapped_data.get('name') or f"{mapped_data.get('first_name', '')} {mapped_data.get('last_name', '')}".strip(),
                email=email,
                phone=self._normalize_phone(phone) if phone else None,
                company=mapped_data.get('company'),
                source='meta_ads',
                status='new',
                score=lead_score,
                metadata={
                    'meta_leadgen_id': meta_lead_data.get('id'),
                    'meta_form_id': form_id,
                    'meta_ad_id': ad_id,
                    'meta_created_time': meta_lead_data.get('created_time'),
                    'original_fields': mapped_data,
                    'utm_source': 'facebook',
                    'utm_medium': 'lead_ad'
                },
                created_at=datetime.utcnow()
            )
            
            # Agregar campos adicionales
            for field, value in mapped_data.items():
                if hasattr(new_lead, field) and value:
                    setattr(new_lead, field, value)
            
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
            
            # Crear registro en ExternalLead para tracking
            external_lead = ExternalLead(
                lead_id=new_lead.id,
                external_id=meta_lead_data.get('id'),
                external_source='meta_ads',
                external_form_id=form_id,
                external_campaign_id=ad_id,
                raw_data=meta_lead_data,
                processed_at=datetime.utcnow()
            )
            
            db.add(external_lead)
            
            # Log de sincronización
            sync_log = SyncLog(
                integration_type='meta_ads',
                operation='create_lead',
                external_id=meta_lead_data.get('id'),
                internal_id=new_lead.id,
                status='success',
                details={'mapped_fields': len(mapped_data), 'lead_score': lead_score}
            )
            
            db.add(sync_log)
            db.commit()
            
            # Disparar workflows automáticos
            await self._trigger_meta_lead_workflows(new_lead, db)
            
            print(f"✅ Lead creado desde Meta: {new_lead.email or new_lead.phone} (Score: {lead_score})")
            
            return new_lead
            
        except Exception as e:
            print(f"❌ Error creando lead desde Meta: {e}")
            
            # Log error
            if 'meta_lead_data' in locals():
                sync_log = SyncLog(
                    integration_type='meta_ads',
                    operation='create_lead',
                    external_id=meta_lead_data.get('id'),
                    status='failed',
                    error_message=str(e)
                )
                db.add(sync_log)
                db.commit()
            
            return None
    
    def _map_meta_fields(self, field_data: List[Dict]) -> Dict[str, Any]:
        """Mapea campos de Meta a campos internos"""
        
        mapped_data = {}
        
        for field in field_data:
            field_name = field.get('name', '').lower()
            field_values = field.get('values', [])
            
            if not field_values:
                continue
            
            # Tomar el primer valor
            field_value = field_values[0].strip() if field_values[0] else None
            
            if not field_value:
                continue
            
            # Mapear según el diccionario de campos
            if field_name in self.field_mapping:
                internal_field = self.field_mapping[field_name]
                mapped_data[internal_field] = field_value
            else:
                # Campos custom van a metadata
                mapped_data[f'custom_{field_name}'] = field_value
        
        # Construir nombre completo si no existe
        if 'name' not in mapped_data and ('first_name' in mapped_data or 'last_name' in mapped_data):
            first_name = mapped_data.get('first_name', '')
            last_name = mapped_data.get('last_name', '')
            mapped_data['name'] = f"{first_name} {last_name}".strip()
        
        return mapped_data
    
    async def _calculate_meta_lead_score(self, mapped_data: Dict, form_id: str, ad_id: str) -> int:
        """Calcula score inicial para lead de Meta Ads"""
        
        base_score = 35  # Score base para leads de Meta Ads
        
        # Bonus por tener información completa
        if mapped_data.get('email'):
            base_score += 15
        
        if mapped_data.get('phone'):
            base_score += 10
        
        if mapped_data.get('company'):
            base_score += 15
        
        if mapped_data.get('job_title'):
            base_score += 10
        
        # Bonus por campos adicionales
        additional_fields = len([v for v in mapped_data.values() if v and str(v).strip()])
        base_score += min(additional_fields * 2, 15)  # Max 15 puntos por campos adicionales
        
        return min(base_score, 100)
    
    def _normalize_phone(self, phone: str) -> str:
        """Normaliza número de teléfono"""
        
        if not phone:
            return phone
        
        # Remover caracteres no numéricos excepto +
        cleaned = ''.join(char for char in phone if char.isdigit() or char == '+')
        
        # Agregar + al inicio si no lo tiene
        if cleaned and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    async def _update_existing_lead(self, lead: Lead, mapped_data: Dict, db: Session) -> Lead:
        """Actualiza un lead existente con nueva información de Meta"""
        
        updated_fields = []
        
        # Actualizar campos si el nuevo valor es más completo
        for field, value in mapped_data.items():
            if hasattr(lead, field) and value:
                current_value = getattr(lead, field)
                if not current_value or len(str(value)) > len(str(current_value)):
                    setattr(lead, field, value)
                    updated_fields.append(field)
        
        # Aumentar score por re-engagement
        if updated_fields:
            lead.score = min(lead.score + 5, 100)
            lead.updated_at = datetime.utcnow()
        
        # Actualizar metadata
        if not lead.metadata:
            lead.metadata = {}
        
        lead.metadata['last_meta_interaction'] = datetime.utcnow().isoformat()
        lead.metadata['meta_reengagement_count'] = lead.metadata.get('meta_reengagement_count', 0) + 1
        
        db.commit()
        
        print(f"✅ Lead actualizado desde Meta: {lead.email} (Campos: {updated_fields})")
        
        return lead
    
    async def _trigger_meta_lead_workflows(self, lead: Lead, db: Session):
        """Dispara workflows específicos para leads de Meta"""
        
        # Trigger para nuevos leads de Meta Ads
        await self.workflow_engine.trigger_workflow(
            trigger_type=TriggerType.FORM_SUBMITTED,
            lead_id=lead.id,
            trigger_data={
                'source': 'meta_ads',
                'form_type': 'lead_ad',
                'lead_score': lead.score,
                'has_email': bool(lead.email),
                'has_phone': bool(lead.phone),
                'has_company': bool(lead.company)
            },
            db=db
        )
    
    async def sync_historical_leads(self, 
                                  days_back: int = 7,
                                  batch_size: int = 50,
                                  db: Session = None) -> Dict[str, int]:
        """Sincroniza leads históricos de Meta Ads"""
        
        if not db:
            db = next(get_db())
        
        results = {
            "total_processed": 0,
            "new_leads": 0,
            "updated_leads": 0,
            "errors": 0
        }
        
        try:
            # Obtener formularios de lead gen
            forms = await self.get_lead_gen_forms()
            
            print(f"🔄 Sincronizando leads de {len(forms)} formularios...")
            
            for form in forms:
                form_id = form['id']
                form_name = form.get('name', 'Unknown')
                
                print(f"📋 Procesando formulario: {form_name} ({form_id})")
                
                # Obtener leads del formulario
                leads = await self.get_leads_from_form(form_id, limit=batch_size)
                
                for meta_lead in leads:
                    try:
                        # Filtrar por fecha si es necesario
                        created_time = meta_lead.get('created_time')
                        if created_time and days_back > 0:
                            lead_date = datetime.fromisoformat(created_time.replace('T', ' ').replace('Z', ''))
                            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
                            
                            if lead_date < cutoff_date:
                                continue
                        
                        # Verificar si ya fue procesado
                        external_id = meta_lead.get('id')
                        existing_external = db.query(ExternalLead)\
                            .filter(ExternalLead.external_id == external_id)\
                            .filter(ExternalLead.external_source == 'meta_ads')\
                            .first()
                        
                        if existing_external:
                            continue  # Ya procesado
                        
                        # Obtener detalles completos
                        full_lead_data = await self.get_lead_details(external_id)
                        
                        if full_lead_data:
                            # Crear lead
                            new_lead = await self.create_lead_from_meta(
                                full_lead_data, form_id, None, db
                            )
                            
                            if new_lead:
                                results["new_leads"] += 1
                            
                            results["total_processed"] += 1
                        
                    except Exception as e:
                        print(f"❌ Error procesando lead {meta_lead.get('id')}: {e}")
                        results["errors"] += 1
                
                # Pausa entre formularios para no saturar la API
                await asyncio.sleep(1)
        
        except Exception as e:
            print(f"❌ Error en sincronización histórica: {e}")
            results["errors"] += 1
        
        print(f"✅ Sincronización completada: {results}")
        
        return results
    
    async def get_campaign_metrics(self, 
                                 campaign_id: str,
                                 date_preset: str = "last_7d") -> Dict[str, Any]:
        """Obtiene métricas detalladas de una campaña"""
        
        url = f"{self.base_url}/{campaign_id}/insights"
        params = {
            "access_token": self.access_token,
            "fields": "impressions,clicks,spend,actions,cost_per_action_type,cpm,ctr,frequency",
            "date_preset": date_preset,
            "action_breakdown": "action_type"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result and result["data"]:
                        metrics_data = result["data"][0]  # Tomar el primer (y único) resultado
                        
                        # Procesar acciones para obtener leads
                        actions = metrics_data.get("actions", [])
                        leads_count = 0
                        
                        for action in actions:
                            if action.get("action_type") == "lead":
                                leads_count = int(action.get("value", 0))
                                break
                        
                        # Calcular métricas adicionales
                        spend = float(metrics_data.get("spend", 0))
                        cost_per_lead = spend / leads_count if leads_count > 0 else 0
                        
                        return {
                            "campaign_id": campaign_id,
                            "date_preset": date_preset,
                            "impressions": int(metrics_data.get("impressions", 0)),
                            "clicks": int(metrics_data.get("clicks", 0)),
                            "spend": spend,
                            "leads": leads_count,
                            "cost_per_lead": cost_per_lead,
                            "cpm": float(metrics_data.get("cpm", 0)),
                            "ctr": float(metrics_data.get("ctr", 0)),
                            "frequency": float(metrics_data.get("frequency", 0)),
                            "raw_data": metrics_data
                        }
                    else:
                        return {"error": "No data available", "raw_response": result}
                        
        except Exception as e:
            print(f"❌ Error obteniendo métricas de campaña {campaign_id}: {e}")
            return {"error": str(e)}
    
    async def get_all_campaign_metrics(self, date_preset: str = "last_7d") -> List[Dict[str, Any]]:
        """Obtiene métricas de todas las campañas activas"""
        
        campaigns = await self.get_campaigns()
        all_metrics = []
        
        for campaign in campaigns:
            campaign_id = campaign["id"]
            campaign_name = campaign.get("name", "Unknown")
            
            metrics = await self.get_campaign_metrics(campaign_id, date_preset)
            
            if "error" not in metrics:
                metrics["campaign_name"] = campaign_name
                metrics["campaign_status"] = campaign.get("status")
                all_metrics.append(metrics)
            
            # Pausa para no saturar la API
            await asyncio.sleep(0.5)
        
        return all_metrics
    
    async def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verifica la firma del webhook de Meta"""
        
        if not signature.startswith('sha256='):
            return False
        
        expected_signature = hmac.new(
            self.app_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la conexión con Meta API"""
        
        url = f"{self.base_url}/me"
        params = {
            "access_token": self.access_token,
            "fields": "id,name"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if response.status == 200 and "id" in result:
                        # Verificar también acceso a ad account
                        ad_accounts = await self.get_ad_accounts()
                        
                        return {
                            "status": "healthy",
                            "user_id": result.get("id"),
                            "user_name": result.get("name"),
                            "ad_accounts_accessible": len(ad_accounts),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": result.get("error", "Unknown error"),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def create_test_webhook_subscription(self) -> Dict[str, Any]:
        """Crea una suscripción de webhook para testing"""
        
        # Esta función es útil para desarrollo y testing
        webhook_url = f"{settings.APP_BASE_URL}/api/v1/webhooks/meta-ads"
        
        return await self.setup_webhooks(webhook_url)
    
    async def get_webhook_subscriptions(self) -> List[Dict[str, Any]]:
        """Obtiene suscripciones de webhook actuales"""
        
        url = f"{self.base_url}/me/subscriptions"
        params = {
            "access_token": self.access_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    
                    if "data" in result:
                        return result["data"]
                    else:
                        return []
                        
        except Exception as e:
            print(f"❌ Error obteniendo suscripciones de webhook: {e}")
            return []
    
    async def delete_webhook_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Elimina una suscripción de webhook"""
        
        url = f"{self.base_url}/{subscription_id}"
        params = {
            "access_token": self.access_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, params=params) as response:
                    if response.status == 200:
                        return {"success": True, "message": "Webhook eliminado exitosamente"}
                    else:
                        result = await response.json()
                        return {"success": False, "error": result}
                        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_custom_audience(self, 
                                   name: str,
                                   description: str,
                                   emails: List[str]) -> Dict[str, Any]:
        """Crea una audiencia personalizada con emails de leads"""
        
        url = f"{self.base_url}/{self.ad_account_id}/customaudiences"
        
        # Hash emails para privacidad
        hashed_emails = [hashlib.sha256(email.lower().encode()).hexdigest() for email in emails]
        
        audience_data = {
            "name": name,
            "description": description,
            "subtype": "CUSTOM",
            "customer_file_source": "USER_PROVIDED_ONLY",
            "access_token": self.access_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Crear audiencia
                async with session.post(url, data=audience_data) as response:
                    result = await response.json()
                    
                    if "id" in result:
                        audience_id = result["id"]
                        
                        # Agregar usuarios a la audiencia
                        users_url = f"{self.base_url}/{audience_id}/users"
                        users_data = {
                            "payload": {
                                "schema": ["EMAIL_SHA256"],
                                "data": [[email] for email in hashed_emails]
                            },
                            "access_token": self.access_token
                        }
                        
                        async with session.post(users_url, json=users_data) as users_response:
                            users_result = await users_response.json()
                            
                            return {
                                "success": True,
                                "audience_id": audience_id,
                                "audience_name": name,
                                "users_added": len(emails),
                                "details": users_result
                            }
                    else:
                        return {"success": False, "error": result}
                        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def sync_leads_to_crm(self, lead_ids: List[int], crm_type: str, db: Session = None):
        """Sincroniza leads específicos con CRM externo"""
        
        if not db:
            db = next(get_db())
        
        # Esta función se integrará con el CRM Sync Manager
        from .crm_sync_manager import CRMSyncManager
        
        crm_manager = CRMSyncManager()
        
        results = []
        
        for lead_id in lead_ids:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            
            if lead and lead.source == 'meta_ads':
                try:
                    sync_result = await crm_manager.sync_lead_to_crm(lead, crm_type, db)
                    results.append({
                        "lead_id": lead_id,
                        "email": lead.email,
                        "success": sync_result.get("success", False),
                        "crm_id": sync_result.get("crm_id")
                    })
                    
                except Exception as e:
                    results.append({
                        "lead_id": lead_id,
                        "email": lead.email if lead else "Unknown",
                        "success": False,
                        "error": str(e)
                    })
        
        return {
            "total_processed": len(results),
            "successful": len([r for r in results if r["success"]]),
            "failed": len([r for r in results if not r["success"]]),
            "details": results
        }
    
    async def get_attribution_report(self, 
                                   days: int = 30,
                                   db: Session = None) -> Dict[str, Any]:
        """Genera reporte de atribución para leads de Meta Ads"""
        
        if not db:
            db = next(get_db())
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Obtener leads de Meta Ads
        meta_leads = db.query(Lead)\
            .filter(Lead.source == 'meta_ads')\
            .filter(Lead.created_at > since_date)\
            .all()
        
        # Obtener métricas de campañas
        campaign_metrics = await self.get_all_campaign_metrics("last_30d")
        
        # Calcular attribution
        total_leads_db = len(meta_leads)
        total_leads_meta = sum(metrics.get("leads", 0) for metrics in campaign_metrics)
        total_spend = sum(metrics.get("spend", 0) for metrics in campaign_metrics)
        
        # Leads por score range
        score_distribution = {
            "0-25": len([l for l in meta_leads if l.score <= 25]),
            "26-50": len([l for l in meta_leads if 26 <= l.score <= 50]),
            "51-75": len([l for l in meta_leads if 51 <= l.score <= 75]),
            "76-100": len([l for l in meta_leads if l.score >= 76])
        }
        
        # Qualified leads (score >= 50)
        qualified_leads = len([l for l in meta_leads if l.score >= 50])
        qualification_rate = qualified_leads / total_leads_db if total_leads_db > 0 else 0
        
        # Cost per qualified lead
        cost_per_qualified = total_spend / qualified_leads if qualified_leads > 0 else 0
        
        return {
            "period_days": days,
            "summary": {
                "total_leads_captured": total_leads_db,
                "total_leads_reported_by_meta": total_leads_meta,
                "attribution_accuracy": total_leads_db / total_leads_meta if total_leads_meta > 0 else 0,
                "total_spend": total_spend,
                "cost_per_lead": total_spend / total_leads_db if total_leads_db > 0 else 0,
                "cost_per_qualified_lead": cost_per_qualified
            },
            "lead_quality": {
                "qualified_leads": qualified_leads,
                "qualification_rate": qualification_rate,
                "score_distribution": score_distribution,
                "avg_score": sum(l.score for l in meta_leads) / len(meta_leads) if meta_leads else 0
            },
            "campaign_performance": campaign_metrics,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def cleanup_old_external_leads(self, days_to_keep: int = 90, db: Session = None):
        """Limpia registros antiguos de external leads para mantener performance"""
        
        if not db:
            db = next(get_db())
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Eliminar external leads antiguos
        old_external_leads = db.query(ExternalLead)\
            .filter(ExternalLead.processed_at < cutoff_date)\
            .filter(ExternalLead.external_source == 'meta_ads')\
            .count()
        
        db.query(ExternalLead)\
            .filter(ExternalLead.processed_at < cutoff_date)\
            .filter(ExternalLead.external_source == 'meta_ads')\
            .delete()
        
        # Eliminar sync logs antiguos
        old_sync_logs = db.query(SyncLog)\
            .filter(SyncLog.created_at < cutoff_date)\
            .filter(SyncLog.integration_type == 'meta_ads')\
            .count()
        
        db.query(SyncLog)\
            .filter(SyncLog.created_at < cutoff_date)\
            .filter(SyncLog.integration_type == 'meta_ads')\
            .delete()
        
        db.commit()
        
        print(f"🧹 Cleanup Meta Ads: {old_external_leads} external leads, {old_sync_logs} sync logs eliminados")
        
        return {
            "deleted_external_leads": old_external_leads,
            "deleted_sync_logs": old_sync_logs
        }

# Funciones de utilidad para Meta Ads

async def batch_process_meta_leads(lead_ids: List[str], 
                                 batch_size: int = 20,
                                 db: Session = None) -> Dict[str, Any]:
    """Procesa leads de Meta en lotes para mejor performance"""
    
    meta_service = MetaAdsService()
    
    results = {
        "total_leads": len(lead_ids),
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "errors": []
    }
    
    # Procesar en lotes
    for i in range(0, len(lead_ids), batch_size):
        batch = lead_ids[i:i + batch_size]
        
        for lead_id in batch:
            try:
                lead_data = await meta_service.get_lead_details(lead_id)
                
                if lead_data:
                    processed_lead = await meta_service.create_lead_from_meta(
                        lead_data, None, None, db
                    )
                    
                    if processed_lead:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1
                
                results["processed"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead_id, "error": str(e)})
        
        # Pausa entre lotes
        await asyncio.sleep(2)
    
    return results

def validate_meta_webhook_data(webhook_data: Dict[str, Any]) -> bool:
    """Valida que los datos del webhook de Meta están completos"""
    
    required_fields = ['entry']
    
    for field in required_fields:
        if field not in webhook_data:
            return False
    
    entry = webhook_data.get('entry', [])
    if not entry or not isinstance(entry, list):
        return False
    
    for entry_item in entry:
        if 'changes' not in entry_item:
            return False
        
        changes = entry_item.get('changes', [])
        for change in changes:
            if change.get('field') == 'leadgen' and 'value' in change:
                return True
    
    return False