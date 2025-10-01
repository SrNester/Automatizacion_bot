import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def render_analytics(session_manager):
    """Renderizar panel de analytics"""
    st.header("📊 Analytics y Business Intelligence")
    
    # Filtros de analytics
    render_analytics_filters()
    
    # Métricas clave de negocio
    render_business_metrics(session_manager)
    
    # Gráficos principales
    render_main_charts(session_manager)
    
    # Análisis avanzado
    render_advanced_analytics(session_manager)

def render_analytics_filters():
    """Renderizar filtros para analytics"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        time_range = st.selectbox(
            "📅 Período",
            ["Últimos 7 días", "Últimos 30 días", "Últimos 90 días", "Todo el histórico"],
            key="analytics_range"
        )
    
    with col2:
        platform = st.multiselect(
            "🌐 Plataformas",
            ["Mercado Libre", "Amazon", "Shopify", "Woocommerce"],
            default=["Mercado Libre", "Amazon"],
            key="analytics_platforms"
        )
    
    with col3:
        metric_type = st.selectbox(
            "📊 Métrica Principal",
            ["Sesiones", "Productos", "Eficiencia", "Ingresos", "Errores"],
            key="analytics_metric"
        )
    
    with col4:
        group_by = st.selectbox(
            "📈 Agrupar por",
            ["Día", "Semana", "Mes", "Plataforma", "Acción"],
            key="analytics_group"
        )

def render_business_metrics(session_manager):
    """Renderizar métricas de negocio"""
    st.subheader("💼 Métricas de Negocio")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_business_metric(
            "💰 Ingresos Estimados",
            "₡2,845,000",
            "+12.5%",
            "vs mes anterior",
            "💵",
            "#28a745"
        )
    
    with col2:
        render_business_metric(
            "📈 ROI de Automatización",
            "347%",
            "+45%", 
            "mejoría anual",
            "📊",
            "#20c997"
        )
    
    with col3:
        render_business_metric(
            "⏱️ Tiempo Ahorrado",
            "156 horas",
            "22 horas",
            "este mes",
            "🕒",
            "#17a2b8"
        )
    
    with col4:
        render_business_metric(
            "🎯 Eficiencia Operativa",
            "94.2%",
            "+3.1%",
            "vs trimestre anterior",
            "⚡",
            "#ffc107"
        )

def render_business_metric(title, value, delta, delta_label, icon, color):
    """Renderizar métrica de negocio individual"""
    st.markdown(
        f"""
        <div style='
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid {color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        '>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{icon}</div>
            <div style='font-size: 1.8rem; font-weight: bold; color: {color};'>{value}</div>
            <div style='color: #666; font-size: 0.9rem; margin-bottom: 0.5rem;'>{title}</div>
            <div style='
                background: {color}20;
                color: {color};
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: bold;
            '>
                {delta} {delta_label}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_main_charts(session_manager):
    """Renderizar gráficos principales"""
    st.subheader("📈 Tendencias Principales")
    
    # Primera fila de gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        render_revenue_trend_chart()
    
    with col2:
        render_platform_performance_chart(session_manager)
    
    # Segunda fila de gráficos
    col3, col4 = st.columns(2)
    
    with col3:
        render_efficiency_trend_chart(session_manager)
    
    with col4:
        render_cost_savings_chart()

def render_advanced_analytics(session_manager):
    """Renderizar análisis avanzados"""
    st.subheader("🔍 Análisis Avanzado")
    
    tab1, tab2, tab3 = st.tabs(["📊 Análisis Predictivo", "🎯 Insights", "📋 Recomendaciones"])
    
    with tab1:
        render_predictive_analysis()
    
    with tab2:
        render_business_insights(session_manager)
    
    with tab3:
        render_recommendations()

def render_revenue_trend_chart():
    """Renderizar gráfico de tendencia de ingresos"""
    
    # Datos de ejemplo
    dates = pd.date_range(start='2023-12-01', end='2024-01-15', freq='D')
    revenue = np.cumsum(np.random.normal(50000, 15000, len(dates)))
    sessions = np.random.randint(10, 25, len(dates))
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Línea de ingresos
    fig.add_trace(
        go.Scatter(
            x=dates, y=revenue,
            name="Ingresos Acumulados",
            line=dict(color="#28a745", width=3),
            fill='tozeroy',
            fillcolor='rgba(40, 167, 69, 0.1)'
        ),
        secondary_y=False,
    )
    
    # Barras de sesiones
    fig.add_trace(
        go.Bar(
            x=dates, y=sessions,
            name="Sesiones Diarias",
            marker_color="#1f77b4",
            opacity=0.7
        ),
        secondary_y=True,
    )
    
    fig.update_layout(
        title="Tendencia de Ingresos vs Sesiones",
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(title_text="Ingresos (₡)", secondary_y=False)
    fig.update_yaxes(title_text="Sesiones", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)

def render_platform_performance_chart(session_manager):
    """Renderizar gráfico de rendimiento por plataforma"""
    
    platforms = ['Mercado Libre', 'Amazon', 'Shopify', 'Woocommerce']
    
    # Métricas múltiples
    metrics = {
        'Sesiones': [45, 25, 15, 10],
        'Ingresos (M)': [2.1, 1.2, 0.8, 0.4],
        'ROI (%)': [380, 320, 290, 250],
        'Eficiencia (%)': [96, 92, 88, 85]
    }
    
    fig = go.Figure()
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    
    for i, (metric_name, values) in enumerate(metrics.items()):
        fig.add_trace(go.Bar(
            name=metric_name,
            x=platforms,
            y=values,
            marker_color=colors[i % len(colors)],
            opacity=0.8
        ))
    
    fig.update_layout(
        title="Rendimiento Comparativo por Plataforma",
        barmode='group',
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_efficiency_trend_chart(session_manager):
    """Renderizar gráfico de tendencia de eficiencia"""
    
    # Datos de ejemplo
    weeks = ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4', 'Sem 5']
    efficiency = [88, 90, 92, 91, 94]
    success_rate = [85, 88, 90, 89, 92]
    cost_savings = [45, 52, 58, 55, 62]
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(x=weeks, y=efficiency, name="Eficiencia", line=dict(color="#28a745", width=3)),
        secondary_y=False,
    )
    
    fig.add_trace(
        go.Scatter(x=weeks, y=success_rate, name="Tasa de Éxito", line=dict(color="#17a2b8", width=3, dash='dot')),
        secondary_y=False,
    )
    
    fig.add_trace(
        go.Bar(x=weeks, y=cost_savings, name="Ahorro (%)", marker_color="#ffc107", opacity=0.6),
        secondary_y=True,
    )
    
    fig.update_layout(
        title="Tendencias de Eficiencia y Ahorro",
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(title_text="Eficiencia (%)", secondary_y=False)
    fig.update_yaxes(title_text="Ahorro (%)", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)

def render_cost_savings_chart():
    """Renderizar gráfico de ahorro de costos"""
    
    categories = ['Tiempo Manual', 'Errores Reducidos', 'Optimización', 'Escalabilidad', 'Otros']
    savings = [45, 25, 15, 10, 5]
    colors = ['#1f77b4', '#28a745', '#ffc107', '#dc3545', '#6c757d']
    
    fig = go.Figure(data=[go.Pie(
        labels=categories,
        values=savings,
        hole=.4,
        marker=dict(colors=colors),
        textinfo='label+percent',
        insidetextorientation='radial'
    )])
    
    fig.update_layout(
        title="Distribución de Ahorro de Costos",
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(text='₡2.8M', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_predictive_analysis():
    """Renderizar análisis predictivo"""
    st.info("🤖 Análisis Predictivo con Machine Learning")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Pronóstico de Ingresos")
        
        # Gráfico de pronóstico simple
        months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun']
        actual = [2.1, 2.3, 2.4, 2.6, 2.8, 3.0]
        predicted = [2.2, 2.4, 2.7, 2.9, 3.2, 3.5]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months[:4], y=actual[:4], name="Real", line=dict(color="#1f77b4")))
        fig.add_trace(go.Scatter(x=months[3:], y=predicted[3:], name="Pronóstico", line=dict(color="#28a745", dash='dash')))
        
        fig.update_layout(height=300, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Probabilidad de Éxito")
        
        metrics = {
            "Próxima Semana": "92%",
            "Próximo Mes": "88%", 
            "Próximo Trimestre": "85%"
        }
        
        for period, probability in metrics.items():
            st.progress(int(probability.strip('%')), text=f"{period}: {probability}")
        
        st.metric("📊 Confianza del Modelo", "94.2%", "1.3%")

def render_business_insights(session_manager):
    """Renderizar insights de negocio"""
    
    insights = [
        {
            "title": "🚀 Oportunidad en Amazon",
            "description": "El ROI en Amazon es 15% mayor que en otras plataformas. Considera aumentar la inversión en automatización para Amazon.",
            "impact": "Alto",
            "confidence": "92%"
        },
        {
            "title": "📈 Eficiencia Mejorando", 
            "description": "La eficiencia operativa ha aumentado 3.1% este trimestre. Las optimizaciones están dando resultados.",
            "impact": "Medio",
            "confidence": "88%"
        },
        {
            "title": "⚠️ Alertas en Woocommerce",
            "description": "Woocommerce muestra una tasa de error 12% mayor. Revisa la configuración de conexión.",
            "impact": "Alto", 
            "confidence": "95%"
        },
        {
            "title": "💰 Optimización de Costos",
            "description": "Podrías ahorrar 15% en costos optimizando los horarios de ejecución.",
            "impact": "Medio",
            "confidence": "85%"
        }
    ]
    
    for insight in insights:
        impact_color = {
            "Alto": "#dc3545",
            "Medio": "#ffc107", 
            "Bajo": "#28a745"
        }
        
        with st.expander(f"{insight['title']} ({insight['impact']} Impacto)", expanded=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(insight["description"])
            
            with col2:
                st.metric("Confianza", insight["confidence"])
            
            st.progress(int(insight["confidence"].strip('%')), text=f"Confianza: {insight['confidence']}")

def render_recommendations():
    """Renderizar recomendaciones"""
    
    recommendations = [
        {
            "action": "🔄 Optimizar Horarios",
            "description": "Programa ejecuciones en horarios de menor tráfico para mejorar velocidad",
            "effort": "Bajo",
            "impact": "Alto",
            "eta": "1 semana"
        },
        {
            "action": "📊 Expandir a Nuevas Plataformas", 
            "description": "Considera integrar Aliexpress y eBay para diversificar fuentes",
            "effort": "Medio",
            "impact": "Alto",
            "eta": "3 semanas"
        },
        {
            "action": "🔧 Mejorar Manejo de Errores",
            "description": "Implementa reintentos automáticos para errores temporales",
            "effort": "Bajo", 
            "impact": "Medio",
            "eta": "2 semanas"
        },
        {
            "action": "📈 Análisis de Competencia Avanzado",
            "description": "Incorpora análisis de precios y disponibilidad de competidores",
            "effort": "Alto",
            "impact": "Alto",
            "eta": "4 semanas"
        }
    ]
    
    for rec in recommendations:
        with st.expander(f"{rec['action']} - Esfuerzo: {rec['effort']}", expanded=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(rec["description"])
            
            with col2:
                st.metric("Impacto", rec["impact"])
            
            with col3:
                st.metric("ETA", rec["eta"])
            
            if st.button("✅ Implementar", key=f"implement_{rec['action']}"):
                st.success(f"🎯 {rec['action']} programado para implementación")

def calculate_business_metrics(sessions):
    """Calcular métricas de negocio a partir de sesiones"""
    # En una aplicación real, esto calcularía métricas reales
    return {
        "estimated_revenue": 2845000,
        "time_saved_hours": 156,
        "roi_percentage": 347,
        "operational_efficiency": 94.2
    }