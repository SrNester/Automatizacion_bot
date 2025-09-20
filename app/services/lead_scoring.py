import json
from typing import Dict, List
import openai
from sqlalchemy.orm import Session
from ..models.lead import Lead, LeadStatus
from ..core.config import settings
from datetime import datetime

class LeadScoringService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        
    def calculate_score(self, lead: Lead, interactions: List[Dict]) -> float:
        """Calcula el puntaje del lead usando múltiples factores"""
        
        score = 0.0
        
        # 1. Score basado en perfil demográfico
        demographic_score = self._score_demographics(lead)
        
        # 2. Score basado en comportamiento
        behavior_score = self._score_behavior(interactions)
        
        # 3. Score basado en engagement
        engagement_score = self._score_engagement(interactions)
        
        # 4. Score usando IA para análisis de texto
        ai_score = self._ai_sentiment_analysis(interactions)
        
        # Peso ponderado
        total_score = (
            demographic_score * 0.3 +
            behavior_score * 0.3 +
            engagement_score * 0.2 +
            ai_score * 0.2
        )
        
        return min(100.0, max(0.0, total_score))
    
    def _score_demographics(self, lead: Lead) -> float:
        """Score basado en cargo, empresa, etc."""
        score = 0.0
        
        # Cargo relevante
        high_value_titles = ['ceo', 'cto', 'director', 'manager', 'head of']
        if any(title in lead.job_title.lower() for title in high_value_titles):
            score += 30
        
        # Presupuesto
        budget_scores = {
            'less_than_1k': 10,
            '1k_to_5k': 25,
            '5k_to_10k': 40,
            'more_than_10k': 50
        }
        score += budget_scores.get(lead.budget_range, 0)
        
        return score
    
    def _score_behavior(self, interactions: List[Dict]) -> float:
        """Score basado en acciones del usuario"""
        score = 0.0
        
        for interaction in interactions:
            if interaction['type'] == 'website_visit':
                score += 5
            elif interaction['type'] == 'download':
                score += 15
            elif interaction['type'] == 'email_response':
                score += 10
            elif interaction['type'] == 'demo_request':
                score += 30
        
        return min(50.0, score)
    
    def _score_engagement(self, interactions: List[Dict]) -> float:
        """Score basado en frecuencia y recencia"""
        if not interactions:
            return 0.0
        
        # Más interacciones = mayor score
        interaction_count = len(interactions)
        frequency_score = min(30.0, interaction_count * 3)
        
        # Interacciones recientes valen más
        recent_interactions = [i for i in interactions 
                             if (datetime.now() - i['timestamp']).days <= 7]
        recency_score = len(recent_interactions) * 5
        
        return frequency_score + recency_score
    
    def _ai_sentiment_analysis(self, interactions: List[Dict]) -> float:
        """Análisis de sentimiento usando IA"""
        if not interactions:
            return 0.0
        
        # Concatenar contenido de interacciones
        content = " ".join([i.get('content', '') for i in interactions])
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analiza el sentimiento e interés de compra en este texto. Responde con un número del 0 al 30 donde 30 indica máximo interés de compra."
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=50
            )
            
            score_text = response.choices[0].message.content
            return float(score_text.split()[0]) if score_text.split()[0].isdigit() else 0.0
        
        except Exception as e:
            print(f"Error en análisis AI: {e}")
            return 0.0
    
    def update_lead_status(self, db: Session, lead_id: int, score: float):
        """Actualiza el status del lead basado en el score"""
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        
        if score >= 70:
            status = LeadStatus.HOT
        elif score >= 40:
            status = LeadStatus.WARM
        else:
            status = LeadStatus.COLD
        
        lead.score = score
        lead.status = status
        db.commit()
        
        return lead