import streamlit as st
import pandas as pd
from datetime import datetime
import json

def render_history(session_manager):
    """Renderizar historial de sesiones"""
    st.header("📋 Historial de Sesiones")
    
    # Filtros y controles
    render_history_controls(session_manager)
    
    # Vista de datos
    render_sessions_table(session_manager)
    
    # Detalles de sesión
    render_session_details(session_manager)

def render_history_controls(session_manager):
    """Renderizar controles del historial"""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 Buscar sesiones", placeholder="Buscar por plataforma, acción...")
    
    with col2:
        platform_filter = st.selectbox(
            "🌐 Plataforma",
            ["Todas", "Mercado Libre", "Amazon", "Shopify", "Woocommerce"]
        )
    
    with col3:
        status_filter = st.selectbox(
            "📊 Estado",
            ["Todos", "Completado", "Fallido", "En progreso"]
        )
    
    with col4:
        date_filter = st.selectbox(
            "📅 Período",
            ["Últimas 24h", "Última semana", "Último mes", "Todo el tiempo"]
        )
    
    # Botones de acción
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("📤 Exportar CSV", use_container_width=True):
            export_sessions_csv(session_manager)
    
    with col3:
        if st.button("🗑️ Limpiar Historial", use_container_width=True):
            clear_old_sessions(session_manager)
    
    with col4:
        if st.button("📊 Estadísticas", use_container_width=True):
            show_session_statistics(session_manager)

def render_sessions_table(session_manager):
    """Renderizar tabla de sesiones"""
    
    # Obtener sesiones filtradas
    sessions = get_filtered_sessions(session_manager)
    
    if not sessions:
        st.info("📭 No hay sesiones que coincidan con los filtros seleccionados")
        return
    
    # Convertir a DataFrame para mejor visualización
    df = pd.DataFrame(sessions)
    
    # Preparar datos para visualización
    display_data = []
    for session in sessions:
        display_data.append({
            "ID": session.get('session_id', 'N/A'),
            "Plataforma": session.get('platform', 'N/A'),
            "Acción": session.get('action', 'N/A'),
            "Estado": get_status_badge(session.get('status', 'unknown')),
            "Productos": session.get('products_processed', 0),
            "Duración": f"{session.get('duration', 0):.1f}s",
            "Errores": session.get('errors', 0),
            "Fecha": format_timestamp(session.get('timestamp')),
            "_raw_data": session  # Guardar datos originales para detalles
        })
    
    # Crear DataFrame de visualización
    display_df = pd.DataFrame(display_data)
    
    # Mostrar tabla
    st.dataframe(
        display_df.drop(columns=['_raw_data']),
        use_container_width=True,
        height=400
    )
    
    # Estadísticas rápidas
    st.markdown("---")
    render_quick_stats(display_df)

def render_session_details(session_manager):
    """Renderizar detalles de sesión seleccionada"""
    st.subheader("🔍 Detalles de Sesión")
    
    # En una aplicación real, aquí se seleccionaría una sesión específica
    sessions = session_manager.get_recent_sessions(limit=5)
    
    if sessions:
        # Mostrar detalles de la última sesión como ejemplo
        latest_session = sessions[0]
        
        col1, col2 = st.columns(2)
        
        with col1:
            render_session_summary(latest_session)
        
        with col2:
            render_session_metrics(latest_session)
        
        # Logs y detalles técnicos
        render_session_logs(latest_session)

def get_filtered_sessions(session_manager):
    """Obtener sesiones filtradas"""
    sessions = session_manager.sessions
    
    # Aplicar filtros (simplificado para demo)
    filtered_sessions = sessions
    
    # Filtrar por búsqueda
    search_term = st.session_state.get('search_term', '')
    if search_term:
        filtered_sessions = [
            s for s in filtered_sessions 
            if search_term.lower() in str(s.get('platform', '')).lower() 
            or search_term.lower() in str(s.get('action', '')).lower()
        ]
    
    return filtered_sessions

def get_status_badge(status):
    """Obtener badge de estado"""
    badges = {
        "completed": "✅ Completado",
        "failed": "❌ Fallido", 
        "running": "🔄 En progreso",
        "pending": "⏳ Pendiente"
    }
    return badges.get(status, "❓ Desconocido")

def format_timestamp(timestamp):
    """Formatear timestamp para visualización"""
    if not timestamp:
        return "N/A"
    
    try:
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        
        return dt.strftime("%d/%m/%Y %H:%M")
    except:
        return str(timestamp)

def render_quick_stats(df):
    """Renderizar estadísticas rápidas"""
    if df.empty:
        return
    
    total_sessions = len(df)
    completed_sessions = len(df[df['Estado'].str.contains('✅')])
    success_rate = (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0
    total_products = df['Productos'].sum()
    avg_duration = pd.to_numeric(df['Duración'].str.replace('s', ''), errors='coerce').mean()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Sesiones Mostradas", total_sessions)
    
    with col2:
        st.metric("Tasa de Éxito", f"{success_rate:.1f}%")
    
    with col3:
        st.metric("Productos Total", total_products)
    
    with col4:
        st.metric("Duración Promedio", f"{avg_duration:.1f}s")

def render_session_summary(session):
    """Renderizar resumen de sesión"""
    st.markdown(
        f"""
        <div style='
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid {"#28a745" if session.get("status") == "completed" else "#dc3545"};
        '>
            <h4>📋 Resumen de Ejecución</h4>
            <div style='line-height: 2;'>
                <strong>🆔 ID:</strong> {session.get('session_id', 'N/A')}<br>
                <strong>🌐 Plataforma:</strong> {session.get('platform', 'N/A')}<br>
                <strong>🎯 Acción:</strong> {session.get('action', 'N/A')}<br>
                <strong>📅 Fecha:</strong> {format_timestamp(session.get('timestamp'))}<br>
                <strong>⏱️ Duración:</strong> {session.get('duration', 0):.1f} segundos<br>
                <strong>📦 Productos:</strong> {session.get('products_processed', 0)} procesados<br>
                <strong>❌ Errores:</strong> {session.get('errors', 0)} encontrados
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_session_metrics(session):
    """Renderizar métricas de sesión"""
    st.markdown(
        f"""
        <div style='
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
        '>
            <h4>📊 Métricas de Rendimiento</h4>
            <div style='line-height: 2;'>
                <strong>⚡ Velocidad:</strong> {(session.get('products_processed', 0) / max(session.get('duration', 1), 1)):.1f} productos/seg<br>
                <strong>🎯 Precisión:</strong> {100 - (session.get('errors', 0) / max(session.get('products_processed', 1), 1) * 100):.1f}%<br>
                <strong>📈 Eficiencia:</strong> {calculate_efficiency(session):.1f}%<br>
                <strong>🔄 Tasa de Éxito:</strong> {"100%" if session.get("status") == "completed" else "0%"}<br>
                <strong>💾 Uso de Memoria:</strong> {session.get('memory_usage', '45.2')} MB<br>
                <strong>🔗 Requests:</strong> {session.get('requests_made', 125)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_session_logs(session):
    """Renderizar logs de sesión"""
    with st.expander("📝 Logs de Ejecución", expanded=False):
        
        # Logs simulados
        logs = [
            {"time": "10:30:01", "level": "INFO", "message": "Iniciando sesión en la plataforma"},
            {"time": "10:30:05", "level": "SUCCESS", "message": "Sesión iniciada exitosamente"},
            {"time": "10:30:10", "level": "INFO", "message": "Buscando productos..."},
            {"time": "10:30:15", "level": "WARNING", "message": "Producto no disponible: SKU-001"},
            {"time": "10:30:20", "level": "INFO", "message": "Procesando 25 productos encontrados"},
            {"time": "10:30:45", "level": "SUCCESS", "message": "Automatización completada exitosamente"}
        ]
        
        for log in logs:
            level_color = {
                "INFO": "#17a2b8",
                "SUCCESS": "#28a745", 
                "WARNING": "#ffc107",
                "ERROR": "#dc3545"
            }
            
            st.markdown(
                f"""
                <div style='
                    background: {level_color[log["level"]]}10;
                    border-left: 3px solid {level_color[log["level"]]};
                    padding: 0.5rem;
                    margin: 0.25rem 0;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 0.9em;
                '>
                    <span style='color: #666;'>[{log["time"]}]</span>
                    <span style='color: {level_color[log["level"]]}; font-weight: bold;'>[{log["level"]}]</span>
                    <span>{log["message"]}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

def export_sessions_csv(session_manager):
    """Exportar sesiones a CSV"""
    try:
        df = pd.DataFrame(session_manager.sessions)
        
        if not df.empty:
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"sesiones_automatizacion_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No hay datos para exportar")
            
    except Exception as e:
        st.error(f"Error exportando datos: {str(e)}")

def clear_old_sessions(session_manager):
    """Limpiar sesiones antiguas"""
    if st.button("Confirmar limpieza", type="primary"):
        session_manager.clear_old_sessions(days=7)
        st.success("✅ Historial limpiado exitosamente")
        st.rerun()

def show_session_statistics(session_manager):
    """Mostrar estadísticas de sesiones"""
    stats = session_manager.get_statistics()
    
    st.subheader("📈 Estadísticas Detalladas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Sesiones Totales", stats["total_sessions"])
        st.metric("Tasa de Éxito", f"{stats['success_rate']:.1f}%")
        st.metric("Sesiones Hoy", stats["sessions_today"])
    
    with col2:
        st.metric("Productos Procesados", stats["total_products"])
        st.metric("Tiempo Total", f"{(stats['total_sessions'] * stats['avg_time']) / 60:.1f} min")
        st.metric("Eficiencia Promedio", "94.2%")

def calculate_efficiency(session):
    """Calcular eficiencia de sesión"""
    products = session.get('products_processed', 0)
    errors = session.get('errors', 0)
    duration = session.get('duration', 1)
    
    if products == 0:
        return 0
    
    accuracy = (products - errors) / products * 100
    speed_score = min(products / duration * 10, 100)  # Normalizar velocidad
    
    return (accuracy + speed_score) / 2