import os
from typing import Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/automatizacion_bot")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # WhatsApp Business API
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_WEBHOOK_SECRET: str = os.getenv("WHATSAPP_WEBHOOK_SECRET", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_verify_token_here")
    
    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    
    # HubSpot
    HUBSPOT_ACCESS_TOKEN: str = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
    HUBSPOT_CLIENT_SECRET: str = os.getenv("HUBSPOT_CLIENT_SECRET", "")
    HUBSPOT_CLIENT_ID: str = os.getenv("HUBSPOT_CLIENT_ID", "")
    
    # Meta Ads API (Fase 4)
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_AD_ACCOUNT_ID: str = os.getenv("META_AD_ACCOUNT_ID", "")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Redis (para cache y sesiones)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Email (SendGrid Fase 3)
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@tudominio.com")
    
    # Slack/Teams (para notificaciones)
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")
    
    # App Settings
    APP_NAME: str = "Automatización Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: list = ["*"]  # Cambiar en producción
    
    # Chatbot Settings
    MAX_CONVERSATION_DURATION_HOURS: int = 24
    MAX_MESSAGES_PER_CONVERSATION: int = 50
    AUTO_ESCALATION_THRESHOLD: int = 10
    RESPONSE_TIMEOUT_SECONDS: int = 30
    
    # Lead Scoring Settings
    INITIAL_LEAD_SCORE: int = 25
    CHATBOT_INTERACTION_BOOST: int = 5
    BUYING_SIGNAL_BOOST: int = 15
    DEMO_REQUEST_BOOST: int = 25
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    WEBHOOK_RATE_LIMIT: int = 1000
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Instancia global de configuración
settings = Settings()

# Validaciones de configuración
def validate_config():
    """Valida que la configuración esté completa para cada fase"""
    
    missing_vars = []
    warnings = []
    
    # Validaciones básicas (Fase 1)
    if not settings.DATABASE_URL or settings.DATABASE_URL == "postgresql://user:pass@localhost/automatizacion_bot":
        warnings.append("DATABASE_URL usando valor por defecto")
    
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-here-change-in-production":
        missing_vars.append("SECRET_KEY debe ser configurado")
    
    # Validaciones Fase 2 (Chatbot)
    if not settings.OPENAI_API_KEY:
        missing_vars.append("OPENAI_API_KEY requerido para AI Assistant")
    
    # WhatsApp (opcional Fase 2)
    whatsapp_vars = [
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID", 
        "WHATSAPP_WEBHOOK_SECRET"
    ]
    
    whatsapp_missing = [var for var in whatsapp_vars if not getattr(settings, var)]
    if whatsapp_missing:
        warnings.append(f"WhatsApp no configurado completamente: {whatsapp_missing}")
    
    # HubSpot (parcialmente implementado)
    hubspot_vars = ["HUBSPOT_ACCESS_TOKEN", "HUBSPOT_CLIENT_SECRET"]
    hubspot_missing = [var for var in hubspot_vars if not getattr(settings, var)]
    if hubspot_missing:
        warnings.append(f"HubSpot no configurado completamente: {hubspot_missing}")
    
    # Resultado de validación
    validation_result = {
        "is_valid": len(missing_vars) == 0,
        "missing_required": missing_vars,
        "warnings": warnings,
        "phase_readiness": {
            "phase_1": len(missing_vars) == 0,  # Core system
            "phase_2": len(missing_vars) == 0 and settings.OPENAI_API_KEY,  # Chatbot
            "phase_3": settings.SENDGRID_API_KEY != "",  # Email automation
            "phase_4": settings.META_ACCESS_TOKEN != "",  # Integrations
            "phase_5": True  # Dashboard (solo frontend)
        }
    }
    
    return validation_result

def get_phase_config(phase: int) -> dict:
    """Retorna configuración específica para cada fase"""
    
    phase_configs = {
        1: {
            "name": "Core System",
            "required_vars": ["DATABASE_URL", "SECRET_KEY"],
            "optional_vars": ["DEBUG", "REDIS_URL"],
            "description": "Base de datos, modelos, APIs básicas"
        },
        2: {
            "name": "Chatbot e IA Assistant", 
            "required_vars": ["OPENAI_API_KEY"],
            "optional_vars": ["WHATSAPP_ACCESS_TOKEN", "TELEGRAM_BOT_TOKEN"],
            "description": "AI Assistant, webhooks, procesamiento de mensajes"
        },
        3: {
            "name": "Nurturing Automation",
            "required_vars": ["SENDGRID_API_KEY", "FROM_EMAIL"],
            "optional_vars": ["SLACK_WEBHOOK_URL"],
            "description": "Email automation, workflows, notificaciones"
        },
        4: {
            "name": "Integraciones",
            "required_vars": ["META_ACCESS_TOKEN", "HUBSPOT_ACCESS_TOKEN"],
            "optional_vars": ["META_AD_ACCOUNT_ID"],
            "description": "Meta Ads, CRM sync, WhatsApp Business completo"
        },
        5: {
            "name": "Dashboard y Analytics",
            "required_vars": [],
            "optional_vars": ["REDIS_URL"],
            "description": "Frontend, métricas, reportes"
        }
    }
    
    return phase_configs.get(phase, {})

def print_config_status():
    """Imprime el estado actual de la configuración"""
    
    validation = validate_config()
    
    print("\n🔧 ESTADO DE CONFIGURACIÓN")
    print("="*50)
    
    if validation["is_valid"]:
        print("✅ Configuración básica completa")
    else:
        print("❌ Configuración incompleta")
        for missing in validation["missing_required"]:
            print(f"   • Falta: {missing}")
    
    if validation["warnings"]:
        print("\n⚠️  Advertencias:")
        for warning in validation["warnings"]:
            print(f"   • {warning}")
    
    print("\n📋 PREPARACIÓN POR FASES:")
    for phase, ready in validation["phase_readiness"].items():
        status = "✅" if ready else "❌"
        phase_num = phase.split("_")[1]
        config = get_phase_config(int(phase_num))
        print(f"   {status} {config.get('name', f'Fase {phase_num}')}")
    
    print("\n🚀 PRÓXIMOS PASOS:")
    if not validation["is_valid"]:
        print("   1. Configurar variables faltantes en .env")
        print("   2. Ejecutar tests de configuración")
    else:
        ready_phases = [p for p, ready in validation["phase_readiness"].items() if ready]
        if len(ready_phases) >= 2:
            print("   1. Ejecutar tests de Fase 2")
            print("   2. Configurar webhooks en desarrollo")
        else:
            print("   1. Configurar OpenAI API Key")
            print("   2. Configurar al menos una plataforma (WhatsApp/Telegram)")

# Configuración para diferentes entornos
def get_environment_config(env: str = "development") -> dict:
    """Retorna configuración específica por entorno"""
    
    configs = {
        "development": {
            "DEBUG": True,
            "LOG_LEVEL": "DEBUG",
            "WEBHOOK_VALIDATION": False,  # Desactivar para testing
        },
        "staging": {
            "DEBUG": False,
            "LOG_LEVEL": "INFO", 
            "WEBHOOK_VALIDATION": True,
        },
        "production": {
            "DEBUG": False,
            "LOG_LEVEL": "WARNING",
            "WEBHOOK_VALIDATION": True,
            "RATE_LIMIT_STRICT": True,
        }
    }
    
    return configs.get(env, configs["development"])

if __name__ == "__main__":
    # Ejecutar validación si se corre directamente
    print_config_status()