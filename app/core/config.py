from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost/salesbot"
    REDIS_URL: str = "redis://localhost:6379"
    
    # APIs
    OPENAI_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    SENDGRID_API_KEY: str
    
    # Meta Ads
    META_ACCESS_TOKEN: str
    META_APP_SECRET: str
    
    # Google Ads
    GOOGLE_ADS_DEVELOPER_TOKEN: str
    GOOGLE_ADS_CLIENT_ID: str
    
    # CRM
    PIPEDRIVE_API_TOKEN: Optional[str] = None
    HUBSPOT_API_KEY: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

settings = Settings()