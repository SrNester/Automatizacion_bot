from sqlalchemy.orm import Session
from ..models.lead import Lead, LeadStatus
from ..models.interaction import Interaction
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

def create_lead(db: Session, lead_data: Dict[str, Any]) -> Lead:
    """
    Crea un nuevo lead en la base de datos.
    """
    new_lead = Lead(
        email=lead_data.get("email"),
        name=lead_data.get("name"),
        phone=lead_data.get("phone"),
        company=lead_data.get("company"),
        source=lead_data.get("source"),
        utm_campaign=lead_data.get("utm_campaign"),
        job_title=lead_data.get("job_title"),
        score=25.0,  # Puntaje inicial
        status=LeadStatus.COLD,
        is_active=True
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return new_lead

def get_lead(db: Session, lead_id: int) -> Optional[Lead]:
    """
    Obtiene un lead por su ID.
    """
    return db.query(Lead).filter(Lead.id == lead_id).first()

def get_lead_by_email(db: Session, email: str) -> Optional[Lead]:
    """
    Obtiene un lead por su dirección de correo electrónico.
    """
    return db.query(Lead).filter(Lead.email == email).first()

def update_lead_score_and_status(db: Session, lead: Lead, new_score: float) -> Lead:
    """
    Actualiza el score y el status de un lead.
    """
    old_score = lead.score
    lead.score = new_score
    if new_score >= 70:
        lead.status = LeadStatus.HOT
    elif new_score >= 40:
        lead.status = LeadStatus.WARM
    else:
        lead.status = LeadStatus.COLD
    
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

def get_total_leads(db: Session) -> int:
    """
    Obtiene el número total de leads.
    """
    return db.query(Lead).count()

def get_hot_leads_count(db: Session) -> int:
    """
    Obtiene el número de leads con estado 'hot'.
    """
    return db.query(Lead).filter(Lead.status == LeadStatus.HOT).count()

def calculate_conversion_rate(db: Session) -> float:
    """
    Calcula la tasa de conversión.
    """
    total_leads = db.query(Lead).count()
    converted_leads = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
    return (converted_leads / total_leads) * 100 if total_leads > 0 else 0.0

def get_top_lead_sources(db: Session, limit: int = 5) -> Dict[str, int]:
    """
    Obtiene las fuentes de leads más comunes.
    """
    sources = db.query(
        Lead.source,
        db.func.count(Lead.id).label('count')
    ).group_by(Lead.source).order_by(db.func.count(Lead.id).desc()).limit(limit).all()
    
    return {source: count for source, count in sources}

def get_conversation_history(db: Session, lead_id: int, limit: int = 10) -> List[Dict[str, str]]:
    """
    Obtiene el historial de conversaciones para un lead.
    """
    interactions = db.query(Interaction).filter(Interaction.lead_id == lead_id).order_by(Interaction.created_at.desc()).limit(limit).all()
    
    history = []
    for interaction in reversed(interactions):
        if interaction.user_message:
            history.append({"role": "user", "content": interaction.user_message})
        if interaction.bot_response:
            history.append({"role": "assistant", "content": interaction.bot_response})
    
    return history

def save_interaction(db: Session, lead_id: int, user_message: str, bot_response: str) -> Interaction:
    """
    Guarda una interacción entre el usuario y el bot.
    """
    interaction = Interaction(
        lead_id=lead_id,
        user_message=user_message,
        bot_response=bot_response,
        type="chatbot",
        timestamp=datetime.utcnow()
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction