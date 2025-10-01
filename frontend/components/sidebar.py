import streamlit as st
from datetime import datetime
import json

def render_sidebar(config_manager):
    """Renderizar la barra lateral con controles"""
    with st.sidebar:
        # Header del sidebar
        st.markdown(
            """
            <div style='
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 1rem;
                border-radius: 10px;
                margin-bottom: 1rem;
                text-align: center;
            '>
                <h3 style='margin: 0;'>🎮 Panel de Control</h3>
                <p style='margin: 0; font-size: 0.9em;'>Configuración Rápida</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Estado del sistema
        render_system_status(config_manager)
        
        # Configuración rápida
        config_data = render_quick_config()
        
        # Acciones rápidas
        render_quick_actions()
        
        # Información del usuario
        render_user_info(config_manager)
        
        # Footer del sidebar
        render_sidebar_footer()
    
    return config_data

def render_system_status(config_manager):
    """Renderizar estado del sistema"""
    st.subheader("📊 Estado del Sistema")
    
    system_status = config_manager.get_system_status()
    
    # Indicadores de estado
    col1, col2 = st.columns(2)
    
    with col1:
        status_color = "🟢" if system_status["status"] == "online" else "🔴"
        st.metric("Estado", f"{status_color} {system_status['status']}")
    
    with col2:
        st.metric("Sesiones Hoy", system_status['sessions_today'])
    
    # Barra de progreso de uso
    st.progress(system_status['resource_usage'] / 100, 
                text=f"Uso de Recursos: {system_status['resource_usage']}%")
    
    st.markdown("---")

def render_quick_config():
    """Renderizar configuración rápida"""
    st.subheader("⚡ Configuración Rápida")
    
    # Selección de plataforma
    platform = st.selectbox(
        "🌐 Plataforma",
        options=["Mercado Libre", "Amazon", "Shopify", "Woocommerce", "Aliexpress"],
        index=0,
        help="Selecciona la plataforma donde ejecutarás la automatización"
    )
    
    # Tipo de acción
    action = st.selectbox(
        "🎯 Acción",
        options=[
            "Monitorear Precios",
            "Actualizar Inventario", 
            "Buscar Productos",
            "Analizar Competencia",
            "Extraer Reviews",
            "Procesar Pedidos",
            "Actualizar Listados"
        ],
        index=0,
        help="Tipo de automatización a ejecutar"
    )
    
    # Modo de ejecución
    execution_mode = st.radio(
        "⚡ Modo de Ejecución",
        options=["🏁 Normal", "🚀 Rápido", "🔇 Silencioso", "🐢 Lento"],
        index=0,
        horizontal=True,
        help="Velocidad y verbosidad de la ejecución"
    )
    
    # Configuraciones avanzadas
    with st.expander("🔧 Configuraciones Avanzadas", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            timeout = st.slider(
                "⏱️ Timeout (seg)", 
                min_value=10, 
                max_value=120, 
                value=30,
                help="Tiempo máximo de espera para operaciones"
            )
            
            headless = st.checkbox(
                "🖥️ Modo Headless", 
                value=True,
                help="Ejecutar sin interfaz gráfica"
            )
        
        with col2:
            take_screenshots = st.checkbox(
                "📸 Capturar Pantallas", 
                value=True,
                help="Tomar screenshots en caso de errores"
            )
            
            save_logs = st.checkbox(
                "📝 Guardar Logs", 
                value=True,
                help="Guardar logs detallados de la ejecución"
            )
    
    st.markdown("---")
    
    return {
        "platform": platform,
        "action": action,
        "execution_mode": execution_mode.replace(" ", "").lower(),
        "timeout": timeout,
        "headless": headless,
        "take_screenshots": take_screenshots,
        "save_logs": save_logs
    }

def render_quick_actions():
    """Renderizar acciones rápidas"""
    st.subheader("🚀 Acciones Inmediatas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶️ Ejecutar", use_container_width=True, type="primary"):
            st.session_state.quick_execute = True
            st.toast("🚀 Iniciando ejecución...", icon="▶️")
    
    with col2:
        if st.button("⏸️ Pausar", use_container_width=True):
            st.session_state.pause_execution = True
            st.toast("⏸️ Automatización pausada", icon="⏸️")
    
    # Botones de utilidad
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.rerun()
    
    if st.button("📋 Reporte Rápido", use_container_width=True):
        generate_quick_report()
    
    st.markdown("---")

def render_user_info(config_manager):
    """Renderizar información del usuario"""
    st.subheader("👤 Información de Sesión")
    
    user_info = config_manager.get_current_user_info()
    
    st.markdown(
        f"""
        <div style='
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid #1f77b4;
            font-size: 0.9em;
        '>
            <div><strong>🆔 Usuario:</strong> {user_info['username']}</div>
            <div><strong>👥 Rol:</strong> {user_info['role']}</div>
            <div><strong>📅 Conectado:</strong> {user_info['login_time']}</div>
            <div><strong>⏰ Duración:</strong> {user_info['session_duration']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Botón de logout
    if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        st.session_state.authenticated = False
        st.rerun()

def render_sidebar_footer():
    """Renderizar footer del sidebar"""
    st.markdown("---")
    
    st.markdown(
        """
        <div style='
            text-align: center;
            color: #666;
            font-size: 0.8em;
            padding: 1rem 0;
        '>
            <div>🤖 <strong>AutoBot v2.1.0</strong></div>
            <div>© 2024 Sistema de Automatización</div>
            <div style='margin-top: 0.5rem;'>
                <a href='#' style='color: #1f77b4; text-decoration: none;'>📚 Docs</a> • 
                <a href='#' style='color: #1f77b4; text-decoration: none;'>🐛 Reportar Bug</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def generate_quick_report():
    """Generar reporte rápido del sistema"""
    # Simular generación de reporte
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "sessions_today": 15,
        "success_rate": 92.5,
        "issues_found": 2,
        "recommendations": ["Optimizar timeouts", "Aumentar intervalos de verificación"]
    }
    
    # Mostrar resumen del reporte
    with st.expander("📋 Vista Previa del Reporte", expanded=True):
        st.json(report_data)
    
    st.toast("📊 Reporte rápido generado exitosamente", icon="✅")

def get_system_health():
    """Obtener salud del sistema (simulado)"""
    return {
        "cpu_usage": 45,
        "memory_usage": 62,
        "disk_usage": 28,
        "network_status": "stable",
        "last_backup": "2024-01-15 02:00:00"
    }