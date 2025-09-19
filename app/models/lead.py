from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from enum import Enum

Base = declarative_base()

class LeadStatus(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    phone = Column(String)
    company = Column(String)
    job_title = Column(String)
    
    # Lead Scoring
    score = Column(Float, default=0.0)
    status = Column(String, default=LeadStatus.COLD)
    
    # Tracking
    source = Column(String)  # meta_ads, google_ads, linkedin, website
    utm_campaign = Column(String)
    first_interaction = Column(DateTime, default=func.now())
    last_interaction = Column(DateTime, default=func.now())
    
    # Preferences
    interests = Column(Text)  # JSON string
    budget_range = Column(String)
    timeline = Column(String)
    
    # Flags
    is_qualified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, index=True)
    type = Column(String)  # email, whatsapp, call, website_visit, download
    content = Column(Text)
    response = Column(Text)
    sentiment_score = Column(Float)
    timestamp = Column(DateTime, default=func.now())