# components/metrics.py - VERSIÓN CORREGIDA
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

def render_metrics(session_manager):
    """Renderizar las métricas principales del dashboard"""
    st.subheader("📊 Métricas de Rendimiento")
    
    # Obtener estadísticas con valores por defecto
    stats = session_manager.get_statistics()
    
    # Asegurar que todas las claves necesarias existen
    safe_stats = {
        "total_sessions": stats.get("total_sessions", 0),
        "success_rate": stats.get("success_rate", 0),
        "total_products": stats.get("total_products", 0),
        "avg_time": stats.get("avg_time", 0),
        "sessions_today": stats.get("sessions_today", 0)
    }
    
    # Crear 4 columnas para las métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            title="Sesiones Totales",
            value=safe_stats["total_sessions"],
            delta=safe_stats["sessions_today"],
            delta_label="hoy",
            icon="📈",
            color="#1f77b4",
            help_text="Total de sesiones de automatización ejecutadas"
        )
    
    with col2:
        render_metric_card(
            title="Tasa de Éxito", 
            value=f"{safe_stats['success_rate']:.1f}%",
            delta=2.5,
            delta_label="vs. ayer",
            icon="✅",
            color="#28a745",
            help_text="Porcentaje de sesiones completadas exitosamente"
        )
    
    with col3:
        render_metric_card(
            title="Productos Procesados",
            value=safe_stats["total_products"],
            delta=127,
            delta_label="últimas 24h",
            icon="📦", 
            color="#ff7f0e",
            help_text="Total de productos procesados por las automatizaciones"
        )
    
    with col4:
        render_metric_card(
            title="Tiempo Promedio",
            value=f"{safe_stats['avg_time']:.1f}s",
            delta=-3.2,
            delta_label="mejoría",
            icon="⏱️",
            color="#dc3545",
            help_text="Tiempo promedio de ejecución por sesión"
        )

def render_metric_card(title, value, delta, delta_label, icon, color, help_text):
    """Renderizar una tarjeta de métrica individual"""
    
    # Determinar color del delta
    delta_color = ""
    delta_prefix = ""
    if isinstance(delta, (int, float)):
        if delta > 0:
            delta_color = "color: #28a745;"
            delta_prefix = "↑"
        elif delta < 0:
            delta_color = "color: #dc3545;"
            delta_prefix = "↓"
        else:
            delta_color = "color: #6c757d;"
            delta_prefix = "→"
    
    delta_display = f"{delta_prefix}{abs(delta)}" if isinstance(delta, (int, float)) else delta
    
    st.markdown(
        f"""
        <div class="metric-card" style="border-left-color: {color};" title="{help_text}">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
                <div style="font-size: 0.8rem; background: {color}20; color: {color}; 
                          padding: 2px 8px; border-radius: 12px; font-weight: bold;">
                    {delta_display}
                </div>
            </div>
            <div style="font-size: 1.8rem; font-weight: bold; color: {color}; margin-bottom: 0.5rem;">
                {value}
            </div>
            <div style="color: #666; font-size: 0.9rem; margin-bottom: 0.25rem;">{title}</div>
            <div style="font-size: 0.7rem; {delta_color}">{delta_label}</div>
        </div>
        """,
        unsafe_allow_html=True
    )