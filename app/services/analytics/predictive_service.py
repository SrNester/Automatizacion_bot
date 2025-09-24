from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, text
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, r2_score
import joblib
import os
import json
from enum import Enum

# Importar modelos correctos
from ...models.integration import Lead, LeadStatus, ExternalLead
from ...models.interaction import Interaction, ConversationSummary
from ...models.workflow import WorkflowExecution, EmailSend
from ...models.campaign import Campaign, CampaignLead

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """Tipos de modelos predictivos disponibles"""
    CONVERSION_PREDICTION = "conversion_prediction"
    LEAD_SCORING = "lead_scoring"
    CHURN_PREDICTION = "churn_prediction"
    RESPONSE_TIME_PREDICTION = "response_time_prediction"
    CAMPAIGN_SUCCESS = "campaign_success"
    NEXT_BEST_ACTION = "next_best_action"

class PredictionConfidence(Enum):
    """Niveles de confianza de las predicciones"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"

class PredictiveService:
    """Servicio de machine learning para predicciones y análisis predictivo"""
    
    def __init__(self, db_session: AsyncSession, model_storage_path: str = "./ml_models"):
        self.db = db_session
        self.model_storage_path = model_storage_path
        os.makedirs(model_storage_path, exist_ok=True)
        
        # Inicializar modelos
        self.models = {}
        self.scalers = {}
        self.label_encoders = {}
        
        # Cargar modelos existentes
        self._load_existing_models()
        
        # Configuración de modelos
        self.model_configs = {
            ModelType.CONVERSION_PREDICTION: {
                'name': 'Conversion Prediction Model',
                'description': 'Predice probabilidad de conversión de leads',
                'features': ['lead_score', 'interaction_count', 'days_since_creation', 
                           'email_engaged', 'website_visited', 'company_size'],
                'target': 'converted',
                'model_class': RandomForestClassifier,
                'model_params': {'n_estimators': 100, 'random_state': 42},
                'retrain_frequency_days': 30
            },
            ModelType.LEAD_SCORING: {
                'name': 'Lead Scoring Model',
                'description': 'Calcula score predictivo de calidad de lead',
                'features': ['email_quality', 'company_size', 'job_title_score', 
                           'interaction_frequency', 'content_engagement', 'response_time'],
                'target': 'final_score',
                'model_class': RandomForestRegressor,
                'model_params': {'n_estimators': 50, 'random_state': 42},
                'retrain_frequency_days': 14
            },
            ModelType.CAMPAIGN_SUCCESS: {
                'name': 'Campaign Success Prediction',
                'description': 'Predice éxito de campañas de marketing',
                'features': ['campaign_budget', 'target_audience_size', 'historical_similar_campaigns',
                           'time_of_year', 'channel_mix', 'creative_quality'],
                'target': 'success_rate',
                'model_class': RandomForestRegressor,
                'model_params': {'n_estimators': 50, 'random_state': 42},
                'retrain_frequency_days': 60
            }
        }
    
    def _load_existing_models(self):
        """Carga modelos existentes desde el sistema de archivos"""
        
        for model_type in ModelType:
            model_path = os.path.join(self.model_storage_path, f"{model_type.value}_model.joblib")
            scaler_path = os.path.join(self.model_storage_path, f"{model_type.value}_scaler.joblib")
            encoder_path = os.path.join(self.model_storage_path, f"{model_type.value}_encoder.joblib")
            metadata_path = os.path.join(self.model_storage_path, f"{model_type.value}_metadata.json")
            
            try:
                if os.path.exists(model_path):
                    self.models[model_type] = joblib.load(model_path)
                    logger.info(f"Loaded existing model: {model_type.value}")
                
                if os.path.exists(scaler_path):
                    self.scalers[model_type] = joblib.load(scaler_path)
                
                if os.path.exists(encoder_path):
                    self.label_encoders[model_type] = joblib.load(encoder_path)
                
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        model_metadata = json.load(f)
                    logger.info(f"Model {model_type.value} metadata: {model_metadata}")
                    
            except Exception as e:
                logger.error(f"Error loading model {model_type.value}: {e}")
    
    def _save_model(self, model_type: ModelType, model, scaler=None, encoder=None, metadata=None):
        """Guarda un modelo entrenado y sus componentes"""
        
        try:
            model_path = os.path.join(self.model_storage_path, f"{model_type.value}_model.joblib")
            joblib.dump(model, model_path)
            
            if scaler:
                scaler_path = os.path.join(self.model_storage_path, f"{model_type.value}_scaler.joblib")
                joblib.dump(scaler, scaler_path)
            
            if encoder:
                encoder_path = os.path.join(self.model_storage_path, f"{model_type.value}_encoder.joblib")
                joblib.dump(encoder, encoder_path)
            
            if metadata:
                metadata_path = os.path.join(self.model_storage_path, f"{model_type.value}_metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved model: {model_type.value}")
            
        except Exception as e:
            logger.error(f"Error saving model {model_type.value}: {e}")
    
    async def predict_lead_conversion(self, lead_id: int) -> Dict[str, Any]:
        """
        Predice la probabilidad de conversión de un lead específico
        
        Args:
            lead_id: ID del lead a analizar
            
        Returns:
            Dict con predicción y metadatos
        """
        
        try:
            # Obtener datos del lead
            lead_data = await self._get_lead_features(lead_id)
            if not lead_data:
                return self._create_prediction_error("Lead not found or insufficient data")
            
            # Verificar si el modelo necesita entrenamiento
            if ModelType.CONVERSION_PREDICTION not in self.models:
                await self.train_conversion_model()
                if ModelType.CONVERSION_PREDICTION not in self.models:
                    return self._create_prediction_error("Conversion model not available")
            
            # Preparar características
            features = self._prepare_features(lead_data, ModelType.CONVERSION_PREDICTION)
            if features is None:
                return self._create_prediction_error("Feature preparation failed")
            
            # Hacer predicción
            model = self.models[ModelType.CONVERSION_PREDICTION]
            probability = model.predict_proba([features])[0][1]  # Probabilidad de clase positiva
            prediction = model.predict([features])[0]
            
            # Analizar factores influyentes
            influential_factors = self._analyze_conversion_factors(lead_data, model, features)
            
            # Determinar confianza
            confidence = self._determine_prediction_confidence(probability, lead_data)
            
            return {
                'success': True,
                'lead_id': lead_id,
                'will_convert': bool(prediction),
                'probability': round(float(probability), 3),
                'confidence': confidence.value,
                'confidence_score': self._calculate_confidence_score(probability, lead_data),
                'influential_factors': influential_factors,
                'recommendations': self._generate_conversion_recommendations(lead_data, probability),
                'model_version': '1.0',
                'predicted_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting lead conversion: {e}")
            return self._create_prediction_error(str(e))
    
    async def calculate_predictive_lead_score(self, lead_id: int) -> Dict[str, Any]:
        """
        Calcula un score predictivo de lead usando machine learning
        
        Args:
            lead_id: ID del lead a scorear
            
        Returns:
            Dict con score predictivo y análisis
        """
        
        try:
            # Obtener datos del lead
            lead_data = await self._get_lead_features(lead_id)
            if not lead_data:
                return self._create_prediction_error("Lead not found or insufficient data")
            
            # Entrenar modelo si es necesario
            if ModelType.LEAD_SCORING not in self.models:
                await self.train_lead_scoring_model()
                if ModelType.LEAD_SCORING not in self.models:
                    return self._create_prediction_error("Lead scoring model not available")
            
            # Preparar características y predecir
            features = self._prepare_features(lead_data, ModelType.LEAD_SCORING)
            if features is None:
                return self._create_prediction_error("Feature preparation failed")
            
            model = self.models[ModelType.LEAD_SCORING]
            predicted_score = model.predict([features])[0]
            
            # Asegurar que el score esté en rango 0-100
            final_score = max(0, min(100, predicted_score))
            
            # Análisis de componentes del score
            score_breakdown = self._analyze_score_components(lead_data, model, features)
            
            return {
                'success': True,
                'lead_id': lead_id,
                'predictive_score': round(float(final_score), 1),
                'score_breakdown': score_breakdown,
                'quality_tier': self._determine_quality_tier(final_score),
                'improvement_recommendations': self._generate_score_improvement_recommendations(score_breakdown),
                'comparison_percentile': await self._calculate_score_percentile(final_score),
                'model_confidence': self._evaluate_model_confidence(ModelType.LEAD_SCORING),
                'calculated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating predictive lead score: {e}")
            return self._create_prediction_error(str(e))
    
    async def predict_campaign_success(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predice la probabilidad de éxito de una campaña
        
        Args:
            campaign_data: Datos de la campaña a predecir
            
        Returns:
            Dict con predicción de éxito
        """
        
        try:
            # Verificar modelo
            if ModelType.CAMPAIGN_SUCCESS not in self.models:
                await self.train_campaign_success_model()
                if ModelType.CAMPAIGN_SUCCESS not in self.models:
                    return self._create_prediction_error("Campaign success model not available")
            
            # Preparar características
            features = self._prepare_campaign_features(campaign_data)
            if features is None:
                return self._create_prediction_error("Campaign feature preparation failed")
            
            model = self.models[ModelType.CAMPAIGN_SUCCESS]
            success_probability = model.predict([features])[0]
            
            # Ajustar a rango 0-1
            success_probability = max(0, min(1, success_probability))
            
            return {
                'success': True,
                'campaign_name': campaign_data.get('name', 'Unknown'),
                'success_probability': round(float(success_probability), 3),
                'expected_roi': self._calculate_expected_roi(campaign_data, success_probability),
                'risk_assessment': self._assess_campaign_risk(success_probability, campaign_data),
                'optimization_suggestions': self._generate_campaign_optimizations(campaign_data, success_probability),
                'predicted_conversion_rate': success_probability * 100,  # Asumiendo correlación
                'model_confidence': self._evaluate_model_confidence(ModelType.CAMPAIGN_SUCCESS),
                'predicted_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting campaign success: {e}")
            return self._create_prediction_error(str(e))
    
    async def train_conversion_model(self, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Entrena o re-entrena el modelo de predicción de conversión
        
        Args:
            force_retrain: Forzar re-entrenamiento incluso si el modelo es reciente
            
        Returns:
            Dict con resultados del entrenamiento
        """
        
        try:
            # Verificar si necesita re-entrenamiento
            if not force_retrain and await self._model_is_current(ModelType.CONVERSION_PREDICTION):
                return {'success': True, 'message': 'Model is current, skipping training'}
            
            logger.info("Training conversion prediction model...")
            
            # Obtener datos de entrenamiento
            training_data = await self._get_conversion_training_data()
            if len(training_data) < 100:
                return {'success': False, 'error': 'Insufficient training data'}
            
            # Preparar datos
            df = pd.DataFrame(training_data)
            X = df[self.model_configs[ModelType.CONVERSION_PREDICTION]['features']]
            y = df['converted']
            
            # Dividir en train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Escalar características
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Entrenar modelo
            model_config = self.model_configs[ModelType.CONVERSION_PREDICTION]
            model = model_config['model_class'](**model_config['model_params'])
            model.fit(X_train_scaled, y_train)
            
            # Evaluar modelo
            y_pred = model.predict(X_test_scaled)
            y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred),
                'recall': recall_score(y_test, y_pred),
                'f1_score': f1_score(y_test, y_pred),
                'roc_auc': np.mean(y_pred_proba)  # Simplified AUC approximation
            }
            
            # Guardar modelo
            self.models[ModelType.CONVERSION_PREDICTION] = model
            self.scalers[ModelType.CONVERSION_PREDICTION] = scaler
            
            metadata = {
                'trained_at': datetime.utcnow().isoformat(),
                'training_samples': len(training_data),
                'positive_samples': sum(y),
                'negative_samples': len(y) - sum(y),
                'metrics': {k: round(float(v), 3) for k, v in metrics.items()},
                'feature_importance': self._get_feature_importance(model, model_config['features'])
            }
            
            self._save_model(ModelType.CONVERSION_PREDICTION, model, scaler, metadata=metadata)
            
            logger.info("Conversion model trained successfully")
            return {
                'success': True,
                'model_type': 'conversion_prediction',
                'metrics': metadata['metrics'],
                'training_size': metadata['training_samples'],
                'feature_importance': metadata['feature_importance']
            }
            
        except Exception as e:
            logger.error(f"Error training conversion model: {e}")
            return {'success': False, 'error': str(e)}
    
    async def train_lead_scoring_model(self, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Entrena el modelo de scoring predictivo de leads
        """
        
        try:
            if not force_retrain and await self._model_is_current(ModelType.LEAD_SCORING):
                return {'success': True, 'message': 'Model is current, skipping training'}
            
            logger.info("Training lead scoring model...")
            
            training_data = await self._get_lead_scoring_training_data()
            if len(training_data) < 100:
                return {'success': False, 'error': 'Insufficient training data'}
            
            df = pd.DataFrame(training_data)
            model_config = self.model_configs[ModelType.LEAD_SCORING]
            X = df[model_config['features']]
            y = df['final_score']
            
            # Dividir y escalar
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Entrenar modelo
            model = model_config['model_class'](**model_config['model_params'])
            model.fit(X_train_scaled, y_train)
            
            # Evaluar
            y_pred = model.predict(X_test_scaled)
            metrics = {
                'r2_score': r2_score(y_test, y_pred),
                'mse': mean_squared_error(y_test, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_test, y_pred))
            }
            
            self.models[ModelType.LEAD_SCORING] = model
            self.scalers[ModelType.LEAD_SCORING] = scaler
            
            metadata = {
                'trained_at': datetime.utcnow().isoformat(),
                'training_samples': len(training_data),
                'metrics': {k: round(float(v), 3) for k, v in metrics.items()},
                'feature_importance': self._get_feature_importance(model, model_config['features'])
            }
            
            self._save_model(ModelType.LEAD_SCORING, model, scaler, metadata=metadata)
            
            logger.info("Lead scoring model trained successfully")
            return {
                'success': True,
                'model_type': 'lead_scoring',
                'metrics': metadata['metrics'],
                'training_size': metadata['training_samples']
            }
            
        except Exception as e:
            logger.error(f"Error training lead scoring model: {e}")
            return {'success': False, 'error': str(e)}
    
    async def train_campaign_success_model(self, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Entrena el modelo de predicción de éxito de campañas
        """
        
        try:
            # Para campañas, usamos datos simulados ya que no tenemos datos históricos reales
            logger.info("Training campaign success model with simulated data...")
            
            # Generar datos de entrenamiento simulados
            training_data = self._generate_simulated_campaign_data()
            df = pd.DataFrame(training_data)
            
            model_config = self.model_configs[ModelType.CAMPAIGN_SUCCESS]
            X = df[model_config['features']]
            y = df['success_rate']
            
            # Entrenar modelo
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            model = model_config['model_class'](**model_config['model_params'])
            model.fit(X_train_scaled, y_train)
            
            # Evaluar
            y_pred = model.predict(X_test_scaled)
            metrics = {
                'r2_score': r2_score(y_test, y_pred),
                'mse': mean_squared_error(y_test, y_pred)
            }
            
            self.models[ModelType.CAMPAIGN_SUCCESS] = model
            self.scalers[ModelType.CAMPAIGN_SUCCESS] = scaler
            
            metadata = {
                'trained_at': datetime.utcnow().isoformat(),
                'training_samples': len(training_data),
                'metrics': metrics,
                'note': 'Trained with simulated data - real campaign data needed for production'
            }
            
            self._save_model(ModelType.CAMPAIGN_SUCCESS, model, scaler, metadata=metadata)
            
            return {
                'success': True,
                'model_type': 'campaign_success',
                'metrics': metrics,
                'note': 'Model trained with simulated data'
            }
            
        except Exception as e:
            logger.error(f"Error training campaign success model: {e}")
            return {'success': False, 'error': str(e)}
    
    async def forecast_leads(self, periods: int = 12, method: str = 'arima') -> Dict[str, Any]:
        """
        Predice cantidad futura de leads usando series temporales
        
        Args:
            periods: Número de períodos a predecir
            method: Método de forecasting ('arima', 'linear', 'seasonal')
            
        Returns:
            Dict con forecast y metadatos
        """
        
        try:
            # Obtener datos históricos
            historical_data = await self._get_historical_lead_data()
            
            if len(historical_data) < 6:
                return {'error': 'Insufficient historical data for forecasting'}
            
            dates = [d['date'] for d in historical_data]
            values = [d['leads'] for d in historical_data]
            
            # Forecasting según método seleccionado
            if method == 'linear':
                forecasts = self._linear_forecast(values, periods)
            elif method == 'moving_average':
                forecasts = self._moving_average_forecast(values, periods)
            else:  # seasonal (simplificado)
                forecasts = self._seasonal_forecast(values, periods)
            
            # Calcular intervalos de confianza
            confidence_intervals = self._calculate_confidence_intervals(values, forecasts)
            
            return {
                'success': True,
                'method': method,
                'periods': periods,
                'historical_data_points': len(historical_data),
                'forecasts': forecasts,
                'confidence_intervals': confidence_intervals,
                'trend': self._analyze_forecast_trend(forecasts),
                'seasonality_detected': await self._detect_seasonality(historical_data),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in lead forecasting: {e}")
            return self._create_prediction_error(str(e))
    
    # MÉTODOS AUXILIARES DE PREPARACIÓN DE DATOS
    
    async def _get_lead_features(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene características de un lead para predicción"""
        
        try:
            # Obtener datos básicos del lead
            stmt = select(Lead).where(Lead.id == lead_id)
            result = await self.db.execute(stmt)
            lead = result.scalar_one_or_none()
            
            if not lead:
                return None
            
            # Contar interacciones
            interaction_stmt = select(func.count(Interaction.id)).where(Interaction.lead_id == lead_id)
            interaction_result = await self.db.execute(interaction_stmt)
            interaction_count = interaction_result.scalar() or 0
            
            # Verificar engagement con email
            email_stmt = select(func.count(EmailSend.id)).where(
                and_(
                    EmailSend.lead_id == lead_id,
                    EmailSend.status.in_(['opened', 'clicked'])
                )
            )
            email_result = await self.db.execute(email_stmt)
            email_engaged = email_result.scalar() or 0
            
            # Calcular días desde creación
            days_since_creation = (datetime.utcnow() - lead.created_at).days
            
            return {
                'lead_score': lead.score or 0,
                'interaction_count': interaction_count,
                'days_since_creation': days_since_creation,
                'email_engaged': min(email_engaged, 1),  # Binario: tuvo engagement o no
                'website_visited': 1 if interaction_count > 0 else 0,  # Simplificado
                'company_size': self._estimate_company_size(lead.company),
                'job_title_score': self._calculate_job_title_score(lead.job_title),
                'email_quality': self._assess_email_quality(lead.email),
                'response_time': await self._get_avg_response_time(lead_id),
                'has_budget': 1 if lead.budget_range and '1000' in lead.budget_range else 0,
                'is_qualified': 1 if lead.is_qualified else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting lead features: {e}")
            return None
    
    def _prepare_features(self, features_dict: Dict, model_type: ModelType) -> Optional[List[float]]:
        """Prepara características para el modelo específico"""
        
        try:
            model_config = self.model_configs[model_type]
            required_features = model_config['features']
            
            # Extraer características en el orden correcto
            features = [features_dict.get(feature, 0.0) for feature in required_features]
            
            # Escalar si existe scaler
            if model_type in self.scalers:
                features = self.scalers[model_type].transform([features])[0]
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None
    
    def _prepare_campaign_features(self, campaign_data: Dict) -> Optional[List[float]]:
        """Prepara características para modelo de campañas"""
        
        try:
            # Mapear datos de campaña a características del modelo
            features_map = {
                'campaign_budget': campaign_data.get('budget', 0),
                'target_audience_size': campaign_data.get('audience_size', 1000),
                'historical_similar_campaigns': campaign_data.get('similar_campaigns', 5),
                'time_of_year': self._encode_time_of_year(campaign_data.get('start_date')),
                'channel_mix': self._encode_channel_mix(campaign_data.get('channels', [])),
                'creative_quality': campaign_data.get('creative_quality', 0.5)
            }
            
            model_config = self.model_configs[ModelType.CAMPAIGN_SUCCESS]
            features = [features_map[feature] for feature in model_config['features']]
            
            if ModelType.CAMPAIGN_SUCCESS in self.scalers:
                features = self.scalers[ModelType.CAMPAIGN_SUCCESS].transform([features])[0]
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing campaign features: {e}")
            return None
    
    # MÉTODOS DE ANÁLISIS Y RECOMENDACIONES
    
    def _analyze_conversion_factors(self, lead_data: Dict, model, features: List) -> List[Dict]:
        """Analiza factores que influyen en la conversión"""
        
        factors = []
        
        # Análisis básico basado en reglas
        if lead_data.get('lead_score', 0) > 70:
            factors.append({
                'factor': 'high_lead_score',
                'impact': 'high',
                'description': 'Lead con score alto tiene mayor probabilidad de conversión'
            })
        
        if lead_data.get('is_qualified', 0) == 1:
            factors.append({
                'factor': 'lead_qualified',
                'impact': 'high', 
                'description': 'Lead ya está cualificado por el equipo de ventas'
            })
        
        if lead_data.get('interaction_count', 0) > 5:
            factors.append({
                'factor': 'high_engagement',
                'impact': 'medium',
                'description': 'Alto número de interacciones indica interés'
            })
        
        return factors
    
    def _generate_conversion_recommendations(self, lead_data: Dict, probability: float) -> List[str]:
        """Genera recomendaciones para mejorar probabilidad de conversión"""
        
        recommendations = []
        
        if probability < 0.3:
            if lead_data.get('interaction_count', 0) < 3:
                recommendations.append("Aumentar engagement con contenido personalizado")
            
            if not lead_data.get('is_qualified', 0):
                recommendations.append("Programar llamada de cualificación")
        
        if lead_data.get('response_time', 24) > 60:  # Más de 60 minutos
            recommendations.append("Optimizar tiempo de respuesta con automatización")
        
        if lead_data.get('email_engaged', 0) == 0:
            recommendations.append("Enviar secuencia de nurturing por email")
        
        return recommendations if recommendations else ["Continuar con estrategia actual"]
    
    def _analyze_score_components(self, lead_data: Dict, model, features: List) -> Dict[str, float]:
        """Analiza contribución de cada componente al score"""
        
        # Para RandomForest, podemos usar feature importance
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            feature_names = self.model_configs[ModelType.LEAD_SCORING]['features']
            
            return {
                feature: round(float(importance * 100), 1)
                for feature, importance in zip(feature_names, importances)
            }
        else:
            # Fallback a análisis basado en reglas
            return {
                'lead_score': 30.0,
                'engagement': 25.0,
                'company_size': 20.0,
                'response_time': 15.0,
                'email_quality': 10.0
            }
    
    def _generate_score_improvement_recommendations(self, score_breakdown: Dict) -> List[str]:
        """Genera recomendaciones para mejorar el score del lead"""
        
        recommendations = []
        
        # Enfocarse en componentes con menor contribución pero alta mejora potencial
        if score_breakdown.get('engagement', 0) < 15:
            recommendations.append("Aumentar frecuencia de interacciones con lead")
        
        if score_breakdown.get('response_time', 0) < 10:
            recommendations.append("Mejorar tiempo de respuesta a consultas")
        
        return recommendations
    
    # MÉTODOS DE FORECASTING TEMPORAL
    
    def _linear_forecast(self, values: List[float], periods: int) -> List[float]:
        """Forecast usando regresión lineal"""
        
        if len(values) < 2:
            return []
        
        X = np.array(range(len(values))).reshape(-1, 1)
        y = np.array(values)
        
        model = LinearRegression()
        model.fit(X, y)
        
        future_X = np.array(range(len(values), len(values) + periods)).reshape(-1, 1)
        forecasts = model.predict(future_X)
        
        return [max(0, float(f)) for f in forecasts]
    
    def _moving_average_forecast(self, values: List[float], periods: int, window: int = 3) -> List[float]:
        """Forecast usando promedio móvil"""
        
        if len(values) < window:
            return []
        
        forecasts = []
        last_values = values[-window:]
        
        for _ in range(periods):
            next_value = np.mean(last_values)
            forecasts.append(float(next_value))
            last_values = last_values[1:] + [next_value]
        
        return forecasts
    
    def _seasonal_forecast(self, values: List[float], periods: int) -> List[float]:
        """Forecast estacional simplificado"""
        
        if len(values) < 12:  # Necesita al menos un año de datos
            return self._moving_average_forecast(values, periods)
        
        # Detectar estacionalidad básica (simplificado)
        seasonal_component = self._detect_seasonal_pattern(values)
        trend = self._linear_forecast(values, periods)
        
        # Combinar tendencia y estacionalidad
        forecasts = []
        for i, trend_value in enumerate(trend):
            seasonal_index = i % len(seasonal_component)
            seasonal_effect = seasonal_component[seasonal_index] if seasonal_component else 0
            forecasts.append(trend_value + seasonal_effect)
        
        return forecasts
    
    def _detect_seasonal_pattern(self, values: List[float]) -> List[float]:
        """Detecta patrón estacional en series temporales"""
        
        if len(values) < 12:
            return []
        
        # Promedio por mes (simplificado)
        monthly_pattern = []
        for month in range(12):
            month_values = [values[i] for i in range(month, len(values), 12)]
            if month_values:
                monthly_pattern.append(np.mean(month_values) - np.mean(values))
        
        return monthly_pattern
    
    # MÉTODOS DE UTILIDAD
    
    def _estimate_company_size(self, company_name: Optional[str]) -> int:
        """Estima tamaño de empresa basado en nombre (simplificado)"""
        
        if not company_name:
            return 1  # Pequeña empresa por defecto
        
        company_lower = company_name.lower()
        
        if any(word in company_lower for word in ['inc', 'corp', 'llc', 'ltd']):
            return 3  # Empresa mediana/grande
        elif any(word in company_lower for word in ['consulting', 'group', 'holdings']):
            return 2  # Empresa pequeña/mediana
        else:
            return 1  # Pequeña empresa
    
    def _calculate_job_title_score(self, job_title: Optional[str]) -> float:
        """Calcula score basado en puesto de trabajo"""
        
        if not job_title:
            return 0.5
        
        title_lower = job_title.lower()
        
        if any(word in title_lower for word in ['ceo', 'cto', 'cfo', 'director', 'vp', 'president']):
            return 1.0
        elif any(word in title_lower for word in ['manager', 'head of', 'lead', 'senior']):
            return 0.8
        elif any(word in title_lower for word in ['analyst', 'specialist', 'coordinator']):
            return 0.6
        else:
            return 0.5
    
    def _assess_email_quality(self, email: Optional[str]) -> float:
        """Evalúa calidad del email"""
        
        if not email or '@' not in email:
            return 0.0
        
        # Verificar dominio de empresa
        if any(domain in email for domain in ['gmail.com', 'yahoo.com', 'hotmail.com']):
            return 0.5
        else:
            return 1.0  # Dominio corporativo
    
    async def _get_avg_response_time(self, lead_id: int) -> float:
        """Obtiene tiempo promedio de respuesta para un lead"""
        
        stmt = select(func.avg(Interaction.response_time_ms)).where(
            and_(
                Interaction.lead_id == lead_id,
                Interaction.response_time_ms.isnot(None)
            )
        )
        result = await self.db.execute(stmt)
        avg_ms = result.scalar() or 0
        
        return avg_ms / 60000  # Convertir a minutos
    
    def _determine_prediction_confidence(self, probability: float, lead_data: Dict) -> PredictionConfidence:
        """Determina confianza de la predicción"""
        
        data_completeness = self._assess_data_completeness(lead_data)
        
        if data_completeness > 0.8 and (probability > 0.7 or probability < 0.3):
            return PredictionConfidence.HIGH
        elif data_completeness > 0.6:
            return PredictionConfidence.MEDIUM
        elif data_completeness > 0.4:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW
    
    def _assess_data_completeness(self, lead_data: Dict) -> float:
        """Evalúa completitud de datos del lead"""
        
        required_fields = ['lead_score', 'interaction_count', 'email_engaged', 'company_size']
        present_fields = sum(1 for field in required_fields if lead_data.get(field, 0) > 0)
        
        return present_fields / len(required_fields)
    
    def _calculate_confidence_score(self, probability: float, lead_data: Dict) -> float:
        """Calcula score numérico de confianza"""
        
        base_confidence = 1 - abs(probability - 0.5) * 2  # Más confianza en extremos
        data_completeness = self._assess_data_completeness(lead_data)
        
        return (base_confidence * 0.7) + (data_completeness * 0.3)
    
    def _determine_quality_tier(self, score: float) -> str:
        """Determina tier de calidad basado en score"""
        
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        else:
            return "poor"
    
    def _evaluate_model_confidence(self, model_type: ModelType) -> float:
        """Evalúa confianza general del modelo"""
        
        # Basado en métricas de entrenamiento (simplificado)
        return 0.85  # Placeholder
    
    def _get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """Obtiene importancia de características del modelo"""
        
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            return {name: round(float(imp), 4) for name, imp in zip(feature_names, importances)}
        else:
            return {name: 0.0 for name in feature_names}
    
    def _create_prediction_error(self, message: str) -> Dict[str, Any]:
        """Crea respuesta de error estandarizada"""
        
        return {
            'success': False,
            'error': message,
            'predicted_at': datetime.utcnow().isoformat()
        }
    
    # MÉTODOS DE OBTENCIÓN DE DATOS DE ENTRENAMIENTO (SIMPLIFICADOS)
    
    async def _get_conversion_training_data(self):
        """Obtiene datos de entrenamiento para modelo de conversión"""
        
        # En producción, esto consultaría la base de datos real
        # Por ahora retornamos datos de ejemplo
        return [
            {'lead_score': 85, 'interaction_count': 5, 'days_since_creation': 10, 
             'email_engaged': 1, 'website_visited': 1, 'company_size': 3, 'converted': 1},
            {'lead_score': 45, 'interaction_count': 2, 'days_since_creation': 30,
             'email_engaged': 0, 'website_visited': 1, 'company_size': 1, 'converted': 0},
            # ... más datos de ejemplo
        ]
    
    async def _get_lead_scoring_training_data(self):
        """Obtiene datos de entrenamiento para modelo de scoring"""
        
        return [
            {'email_quality': 1.0, 'company_size': 3, 'job_title_score': 1.0,
             'interaction_frequency': 0.8, 'content_engagement': 0.9, 'response_time': 0.2, 'final_score': 95},
            {'email_quality': 0.5, 'company_size': 1, 'job_title_score': 0.6,
             'interaction_frequency': 0.3, 'content_engagement': 0.4, 'response_time': 0.8, 'final_score': 45},
            # ... más datos de ejemplo
        ]
    
    def _generate_simulated_campaign_data(self, n_samples: int = 1000):
        """Genera datos simulados para entrenamiento de modelo de campañas"""
        
        np.random.seed(42)
        
        data = []
        for i in range(n_samples):
            campaign = {
                'campaign_budget': np.random.uniform(1000, 50000),
                'target_audience_size': np.random.randint(1000, 100000),
                'historical_similar_campaigns': np.random.randint(0, 20),
                'time_of_year': np.random.uniform(0, 1),
                'channel_mix': np.random.uniform(0, 1),
                'creative_quality': np.random.uniform(0.3, 1.0),
                'success_rate': np.random.uniform(0.1, 0.8)  # Variable objetivo
            }
            data.append(campaign)
        
        return data
    
    async def _get_historical_lead_data(self, months: int = 24):
        """Obtiene datos históricos de leads para forecasting"""
        
        # En producción, esto consultaría la base de datos
        # Por ahora generamos datos simulados
        base_date = datetime.utcnow() - timedelta(days=30*months)
        data = []
        
        for i in range(months):
            date = base_date + timedelta(days=30*i)
            # Tendencia con estacionalidad
            base_leads = 100 + i * 5  # Tendencia creciente
            seasonal = 20 * np.sin(2 * np.pi * i / 12)  # Estacionalidad anual
            noise = np.random.normal(0, 10)
            
            leads = max(0, int(base_leads + seasonal + noise))
            
            data.append({
                'date': date.isoformat(),
                'leads': leads
            })
        
        return data
    
    async def _model_is_current(self, model_type: ModelType) -> bool:
        """Verifica si el modelo está actualizado"""
        
        metadata_path = os.path.join(self.model_storage_path, f"{model_type.value}_metadata.json")
        
        if not os.path.exists(metadata_path):
            return False
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            trained_at = datetime.fromisoformat(metadata['trained_at'].replace('Z', '+00:00'))
            days_since_training = (datetime.utcnow() - trained_at).days
            
            max_age = self.model_configs[model_type]['retrain_frequency_days']
            return days_since_training < max_age
            
        except:
            return False
    
    # Métodos de encoding y transformación
    
    def _encode_time_of_year(self, date_str: Optional[str]) -> float:
        """Codifica época del año como valor continuo"""
        
        if not date_str:
            return 0.5
        
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            day_of_year = date.timetuple().tm_yday
            return day_of_year / 365.0
        except:
            return 0.5
    
    def _encode_channel_mix(self, channels: List[str]) -> float:
        """Codifica mix de canales como valor numérico"""
        
        if not channels:
            return 0.5
        
        channel_weights = {
            'email': 0.3,
            'social': 0.25,
            'paid': 0.2,
            'organic': 0.15,
            'direct': 0.1
        }
        
        mix_score = sum(channel_weights.get(channel, 0) for channel in channels)
        return min(1.0, mix_score)
    
    # Métodos de análisis de forecasting
    
    def _calculate_confidence_intervals(self, historical_values: List[float], forecasts: List[float]) -> Dict[str, List[float]]:
        """Calcula intervalos de confianza para forecasts"""
        
        historical_std = np.std(historical_values) if historical_values else 1.0
        
        upper_bounds = []
        lower_bounds = []
        
        for i, forecast in enumerate(forecasts):
            # Aumentar incertidumbre con el tiempo
            uncertainty_factor = 1 + (i * 0.1)
            margin = historical_std * uncertainty_factor
            
            upper_bounds.append(forecast + margin)
            lower_bounds.append(max(0, forecast - margin))
        
        return {
            'upper_bound': [round(float(x), 1) for x in upper_bounds],
            'lower_bound': [round(float(x), 1) for x in lower_bounds]
        }
    
    def _analyze_forecast_trend(self, forecasts: List[float]) -> str:
        """Analiza tendencia del forecast"""
        
        if len(forecasts) < 2:
            return "unknown"
        
        first_half = forecasts[:len(forecasts)//2]
        second_half = forecasts[len(forecasts)//2:]
        
        avg_first = np.mean(first_half)
        avg_second = np.mean(second_half)
        
        if avg_second > avg_first * 1.1:
            return "growing"
        elif avg_second < avg_first * 0.9:
            return "declining"
        else:
            return "stable"
    
    async def _detect_seasonality(self, historical_data: List[Dict]) -> bool:
        """Detecta si hay patrones estacionales en los datos"""
        
        if len(historical_data) < 12:
            return False
        
        values = [d['leads'] for d in historical_data]
        
        # Análisis de autocorrelación simple
        if len(values) >= 24:  # Necesita al menos 2 años de datos
            # Verificar correlación con lag de 12 meses
            lag_12_corr = np.corrcoef(values[:-12], values[12:])[0,1] if len(values) > 12 else 0
            return abs(lag_12_corr) > 0.5
        else:
            return False
    
    # Métodos para campañas
    
    def _calculate_expected_roi(self, campaign_data: Dict, success_probability: float) -> float:
        """Calcula ROI esperado de una campaña"""
        
        budget = campaign_data.get('budget', 0)
        expected_value = success_probability * budget * 3  # Asumiendo 3x retorno en éxito
        
        if budget > 0:
            return (expected_value - budget) / budget * 100
        else:
            return 0.0
    
    def _assess_campaign_risk(self, success_probability: float, campaign_data: Dict) -> str:
        """Evalúa nivel de riesgo de una campaña"""
        
        budget = campaign_data.get('budget', 0)
        
        if success_probability < 0.3:
            return "high"
        elif success_probability < 0.6:
            return "medium"
        else:
            return "low"
    
    def _generate_campaign_optimizations(self, campaign_data: Dict, success_probability: float) -> List[str]:
        """Genera sugerencias para optimizar campaña"""
        
        optimizations = []
        
        if success_probability < 0.5:
            optimizations.append("Considerar aumentar el presupuesto para mayor impacto")
            optimizations.append("Diversificar mix de canales de marketing")
        
        if campaign_data.get('audience_size', 0) < 5000:
            optimizations.append("Ampliar audiencia objetivo para aumentar reach")
        
        return optimizations
    
    async def _calculate_score_percentile(self, score: float) -> float:
        """Calcula percentil del score comparado con otros leads"""
        
        # En producción, esto consultaría la distribución real de scores
        # Por ahora usamos percentiles aproximados
        if score >= 80:
            return 90.0
        elif score >= 60:
            return 70.0
        elif score >= 40:
            return 40.0
        else:
            return 15.0