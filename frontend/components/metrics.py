import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

def render_metrics(session_manager):
    """Renderizar las métricas principales del dashboard"""
    st.subheader("📊 Métricas de Rendimiento en Tiempo Real")
    
    # Obtener estadísticas
    stats = session_manager.get_statistics()
    
    # Métricas principales en 4 columnas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            title="Sesiones Totales",
            value=stats["total_sessions"],
            delta=stats["sessions_today"],
            delta_label="hoy",
            icon="📈",
            color="#1f77b4",
            help_text="Total de sesiones de automatización ejecutadas"
        )
    
    with col2:
        render_metric_card(
            title="Tasa de Éxito", 
            value=f"{stats['success_rate']:.1f}%",
            delta=2.5,
            delta_label="vs. ayer",
            icon="✅",
            color="#28a745",
            help_text="Porcentaje de sesiones completadas exitosamente"
        )
    
    with col3:
        render_metric_card(
            title="Productos Procesados",
            value=stats["total_products"],
            delta=127,
            delta_label="últimas 24h",
            icon="📦", 
            color="#ff7f0e",
            help_text="Total de productos procesados por las automatizaciones"
        )
    
    with col4:
        render_metric_card(
            title="Tiempo Promedio",
            value=f"{stats['avg_time']:.1f}s",
            delta=-3.2,
            delta_label="mejoría",
            icon="⏱️",
            color="#dc3545",
            help_text="Tiempo promedio de ejecución por sesión"
        )
    
    # Segunda fila de métricas
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        error_rate = 100 - stats['success_rate']
        render_metric_card(
            title="Tasa de Error",
            value=f"{error_rate:.1f}%",
            delta=-1.2 if error_rate < 5 else 0.5,
            delta_label="tendencia",
            icon="❌",
            color="#dc3545" if error_rate > 5 else "#ffc107",
            help_text="Porcentaje de sesiones con errores"
        )
    
    with col6:
        render_metric_card(
            title="Eficiencia",
            value="98%",
            delta=0.8,
            delta_label="mejoría",
            icon="⚡",
            color="#20c997",
            help_text="Eficiencia general del sistema"
        )
    
    with col7:
        active_bots = 3
        render_metric_card(
            title="Bots Activos",
            value=active_bots,
            delta=0,
            delta_label="estable",
            icon="🤖",
            color="#6f42c1",
            help_text="Número de bots de automatización activos"
        )
    
    with col8:
        revenue_impact = "₡2.8M"
        render_metric_card(
            title="Impacto en Ventas",
            value=revenue_impact,
            delta="₡450K",
            delta_label="este mes",
            icon="💰",
            color="#198754",
            help_text="Impacto estimado en revenue por automatizaciones"
        )
    
    # Gráficos de rendimiento
    render_performance_charts(session_manager)

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

def render_performance_charts(session_manager):
    """Renderizar gráficos de rendimiento"""
    st.markdown("---")
    st.subheader("📈 Tendencias y Análisis")
    
    # Dos columnas para gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        render_sessions_trend_chart(session_manager)
    
    with col2:
        render_success_rate_chart(session_manager)
    
    # Segunda fila de gráficos
    col3, col4 = st.columns(2)
    
    with col3:
        render_platform_distribution_chart(session_manager)
    
    with col4:
        render_performance_heatmap()

def render_sessions_trend_chart(session_manager):
    """Renderizar gráfico de tendencia de sesiones"""
    
    # Datos de ejemplo para el gráfico
    dates = pd.date_range(start='2024-01-08', end='2024-01-15', freq='D')
    sessions = [12, 15, 18, 14, 16, 20, 15, 18]
    successful = [10, 13, 16, 12, 15, 18, 14, 17]
    
    fig = go.Figure()
    
    # Sesiones totales
    fig.add_trace(go.Scatter(
        x=dates,
        y=sessions,
        mode='lines+markers',
        name='Sesiones Totales',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=6)
    ))
    
    # Sesiones exitosas
    fig.add_trace(go.Scatter(
        x=dates,
        y=successful,
        mode='lines+markers',
        name='Sesiones Exitosas',
        line=dict(color='#28a745', width=3, dash='dot'),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title="Tendencia de Sesiones (Últimos 7 días)",
        xaxis_title="Fecha",
        yaxis_title="Número de Sesiones",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_success_rate_chart(session_manager):
    """Renderizar gráfico de tasa de éxito por plataforma"""
    
    # Datos de ejemplo
    platforms = ['Mercado Libre', 'Amazon', 'Shopify', 'Woocommerce']
    success_rates = [95, 88, 92, 85]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    
    fig = go.Figure(data=[
        go.Bar(
            x=platforms,
            y=success_rates,
            marker_color=colors,
            text=success_rates,
            texttemplate='%{text}%',
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Tasa de Éxito por Plataforma",
        xaxis_title="Plataforma",
        yaxis_title="Tasa de Éxito (%)",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(range=[0, 100])
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_platform_distribution_chart(session_manager):
    """Renderizar gráfico de distribución por plataforma"""
    
    # Datos de ejemplo
    platforms = ['Mercado Libre', 'Amazon', 'Shopify', 'Woocommerce', 'Otros']
    distribution = [45, 25, 15, 10, 5]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    fig = go.Figure(data=[go.Pie(
        labels=platforms,
        values=distribution,
        hole=.3,
        marker=dict(colors=colors)
    )])
    
    fig.update_layout(
        title="Distribución de Sesiones por Plataforma",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_performance_heatmap():
    """Renderizar heatmap de rendimiento por hora"""
    
    # Datos de ejemplo para heatmap
    hours = list(range(24))
    days = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    
    # Simular datos de performance
    import numpy as np
    np.random.seed(42)
    performance_data = np.random.randint(70, 99, size=(7, 24))
    
    fig = go.Figure(data=go.Heatmap(
        z=performance_data,
        x=hours,
        y=days,
        colorscale='Viridis',
        hoverongaps=False,
        hovertemplate='Día: %{y}<br>Hora: %{x}:00<br>Rendimiento: %{z}%<extra></extra>'
    ))
    
    fig.update_layout(
        title="Rendimiento por Hora y Día de la Semana",
        xaxis_title="Hora del Día",
        yaxis_title="Día de la Semana",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def get_real_time_metrics():
    """Obtener métricas en tiempo real (simulado)"""
    return {
        "current_sessions": 3,
        "avg_response_time": 1.2,
        "error_rate": 2.1,
        "queue_size": 0,
        "system_load": 45.6
    }