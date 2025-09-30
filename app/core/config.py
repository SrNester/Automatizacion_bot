from pydantic import BaseSettings, validator
from typing import List, Optional, Dict, Any
from datetime import timedelta
import secrets
import logging
from functools import lru_cache

class Settings(BaseSettings):
    """Configuración de la aplicación usando Pydantic BaseSettings"""
    
    # =========================================================================
    # CONFIGURACIÓN BÁSICA DE LA APLICACIÓN
    # =========================================================================
    APP_NAME: str = "Sales Automation Platform"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Plataforma de automatización de ventas con IA"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development, staging, production
    
    # =========================================================================
    # SEGURIDAD Y AUTENTICACIÓN
    # =========================================================================
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # =========================================================================
    # BASE DE DATOS
    # =========================================================================
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/sales_automation"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False
    
    # =========================================================================
    # REDIS Y CACHE
    # =========================================================================
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutos por defecto
    CACHE_ENABLED: bool = True
    
    # =========================================================================
    # CELERY Y TAREAS EN BACKGROUND
    # =========================================================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    
    # =========================================================================
    # INTEGRACIONES EXTERNAS - HUBSPOT
    # =========================================================================
    HUBSPOT_ACCESS_TOKEN: Optional[str] = None
    HUBSPOT_REFRESH_TOKEN: Optional[str] = None
    HUBSPOT_CLIENT_ID: Optional[str] = None
    HUBSPOT_CLIENT_SECRET: Optional[str] = None
    HUBSPOT_REDIRECT_URI: Optional[str] = None
    HUBSPOT_API_BASE_URL: str = "https://api.hubapi.com"
    
    # =========================================================================
    # EMAIL Y NOTIFICACIONES
    # =========================================================================
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@company.com"
    EMAIL_FROM_NAME: str = "Sales Automation"
    
    # SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "noreply@company.com"
    
    # Slack
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    
    # SMS (Twilio)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    SMS_ENABLED: bool = False
    
    # =========================================================================
    # IA Y MACHINE LEARNING
    # =========================================================================
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None
    AI_MODEL_NAME: str = "gpt-3.5-turbo"
    AI_MAX_TOKENS: int = 1000
    AI_TEMPERATURE: float = 0.7
    
    # =========================================================================
    # MONITOREO Y LOGGING
    # =========================================================================
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_PORT: int = 8001
    
    # =========================================================================
    # ALMACENAMIENTO Y ARCHIVOS
    # =========================================================================
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    UPLOAD_MAX_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # =========================================================================
    # CONFIGURACIÓN DE LA EMPRESA
    # =========================================================================
    COMPANY_NAME: str = "Mi Empresa"
    COMPANY_LOGO_URL: Optional[str] = None
    COMPANY_CONTACT_INFO: str = "contacto@miempresa.com"
    APP_URL: str = "http://localhost:8000"
    
    # =========================================================================
    # CONFIGURACIONES ESPECÍFICAS DEL SISTEMA
    # =========================================================================
    
    # Lead Scoring
    LEAD_SCORING_ENABLED: bool = True
    LEAD_SCORING_THRESHOLD_HOT: int = 80
    LEAD_SCORING_THRESHOLD_WARM: int = 50
    LEAD_SCORING_UPDATE_INTERVAL: int = 60  # minutos
    
    # Workflows
    WORKFLOW_MAX_STEPS: int = 20
    WORKFLOW_MAX_EXECUTIONS_PER_LEAD: int = 3
    WORKFLOW_CLEANUP_DAYS: int = 30
    
    # Email Automation
    EMAIL_MAX_BATCH_SIZE: int = 1000
    EMAIL_RATE_LIMIT_PER_HOUR: int = 1000
    EMAIL_TRACKING_ENABLED: bool = True
    
    # Reportes
    REPORT_CACHE_ENABLED: bool = True
    REPORT_CACHE_TTL: int = 3600  # 1 hora
    REPORT_MAX_RECIPIENTS: int = 50
    REPORT_MAX_SIZE_MB: int = 50
    
    # Alertas
    ALERT_EMAIL_RECIPIENTS: List[str] = ["alerts@company.com"]
    SYSTEM_HEALTH_CHECK_INTERVAL: int = 5  # minutos
    
    # =========================================================================
    # VALIDACIONES Y CONFIGURACIONES DERIVADAS
    # =========================================================================
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALERT_EMAIL_RECIPIENTS", pre=True)
    def parse_alert_recipients(cls, v):
        if isinstance(v, str):
            return [email.strip() for email in v.split(",")]
        return v
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == "staging"
    
    @property
    def database_config(self) -> Dict[str, Any]:
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "echo": self.DATABASE_ECHO
        }
    
    @property
    def celery_config(self) -> Dict[str, Any]:
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_serializer": self.CELERY_TASK_SERIALIZER,
            "accept_content": self.CELERY_ACCEPT_CONTENT,
            "timezone": "UTC"
        }
    
    @property
    def security_config(self) -> Dict[str, Any]:
        return {
            "secret_key": self.SECRET_KEY,
            "algorithm": self.ALGORITHM,
            "access_token_expire": timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
    
    @property
    def email_config(self) -> Dict[str, Any]:
        return {
            "smtp_server": self.SMTP_SERVER,
            "smtp_port": self.SMTP_PORT,
            "smtp_username": self.SMTP_USERNAME,
            "smtp_password": self.SMTP_PASSWORD,
            "from_email": self.EMAIL_FROM,
            "from_name": self.EMAIL_FROM_NAME,
            "sendgrid_api_key": self.SENDGRID_API_KEY
        }
    
    @property
    def hubspot_config(self) -> Dict[str, Any]:
        return {
            "access_token": self.HUBSPOT_ACCESS_TOKEN,
            "refresh_token": self.HUBSPOT_REFRESH_TOKEN,
            "client_id": self.HUBSPOT_CLIENT_ID,
            "client_secret": self.HUBSPOT_CLIENT_SECRET,
            "redirect_uri": self.HUBSPOT_REDIRECT_URI,
            "api_base_url": self.HUBSPOT_API_BASE_URL
        }
    
    @property
    def ai_config(self) -> Dict[str, Any]:
        return {
            "openai_api_key": self.OPENAI_API_KEY,
            "huggingface_api_key": self.HUGGINGFACE_API_KEY,
            "model_name": self.AI_MODEL_NAME,
            "max_tokens": self.AI_MAX_TOKENS,
            "temperature": self.AI_TEMPERATURE
        }
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        return {
            "level": self.LOG_LEVEL,
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        validate_assignment = True

@lru_cache()
def get_settings() -> Settings:
    """
    Retorna la configuración caché de la aplicación
    Uso: settings = get_settings()
    """
    return Settings()

# Instancia global de configuración
settings = get_settings()

def setup_logging():
    """Configura el logging basado en la configuración"""
    
    logging_config = settings.logging_config
    logging.basicConfig(
        level=getattr(logging, logging_config["level"]),
        format=logging_config["format"]
    )
    
    # Configurar loggers específicos
    loggers = [
        "uvicorn",
        "fastapi",
        "sqlalchemy",
        "celery",
        "services",
        "app"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, logging_config["level"]))
    
    return logging_config

# Configurar logging al importar el módulo
setup_logging()