import streamlit as st
from datetime import datetime

def render_header():
    """Renderizar el encabezado de la aplicación"""
    # Container principal del header
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            # Logo de la aplicación
            try:
                st.image("static/images/logo.png", width=80)
            except:
                # Fallback si no hay logo
                st.markdown(
                    """
                    <div style='
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        width: 80px;
                        height: 80px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 2rem;
                        font-weight: bold;
                    '>🤖</div>
                    """,
                    unsafe_allow_html=True
                )
        
        with col2:
            # Título y descripción
            st.markdown(
                """
                <div style='text-align: center;'>
                    <h1 style='margin-bottom: 0; color: #1f77b4; font-size: 2.5rem;'>
                        🤖 Bot de Automatización
                    </h1>
                    <p style='margin-top: 0; color: #666; font-size: 1.1rem;'>
                        Sistema Inteligente de Gestión de Ventas
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        with col3:
            # Información de tiempo y usuario
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            user = st.session_state.get('user', 'Administrador')
            
            st.markdown(
                f"""
                <div style='
                    text-align: right; 
                    color: #888; 
                    font-size: 0.9em;
                    background: #f8f9fa;
                    padding: 10px;
                    border-radius: 8px;
                    border-left: 3px solid #1f77b4;
                '>
                    <div style='font-weight: bold; color: #333;'>{user}</div>
                    <div style='font-size: 0.8em;'>{current_time}</div>
                    <div style='font-size: 0.7em; color: #1f77b4;'>v2.1.0</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
    
    # Barra de estado del sistema
    render_status_bar()

def render_status_bar():
    """Renderizar barra de estado del sistema"""
    # Simular estado del sistema (en una app real esto vendría de una API)
    system_status = get_system_status()
    
    status_color = {
        "online": "#28a745",
        "warning": "#ffc107", 
        "offline": "#dc3545"
    }
    
    status_icon = {
        "online": "🟢",
        "warning": "🟡",
        "offline": "🔴"
    }
    
    st.markdown(
        f"""
        <div style='
            background: linear-gradient(90deg, {status_color[system_status['status']]}, #6c757d);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin: 15px 0;
            text-align: center;
            font-weight: bold;
            font-size: 0.9em;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        '>
            <span style='font-size: 1.2em;'>{status_icon[system_status['status']]}</span>
            SISTEMA {system_status['status'].upper()} | 
            📊 {system_status['sessions_today']} SESIONES HOY | 
            ⚡ {system_status['efficiency']}% EFICIENCIA |
            🚀 {system_status['active_bots']} BOTS ACTIVOS
        </div>
        """,
        unsafe_allow_html=True
    )

def get_system_status():
    """Obtener estado del sistema (simulado para demo)"""
    # En una aplicación real, esto consultaría APIs o bases de datos
    return {
        "status": "online",
        "sessions_today": 15,
        "efficiency": 98,
        "active_bots": 3,
        "last_update": datetime.now().strftime("%H:%M:%S")
    }

def render_quick_actions():
    """Renderizar acciones rápidas en el header"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("📊 Reporte", use_container_width=True):
            generate_quick_report()
    
    with col3:
        if st.button("🔔 Notificaciones", use_container_width=True):
            show_notifications()
    
    with col4:
        if st.button("❓ Ayuda", use_container_width=True):
            show_help()

def generate_quick_report():
    """Generar reporte rápido"""
    st.toast("📋 Reporte rápido generado", icon="✅")

def show_notifications():
    """Mostrar notificaciones"""
    st.toast("🔔 3 notificaciones nuevas", icon="📱")

def show_help():
    """Mostrar ayuda rápida"""
    st.toast("❓ Abriendo documentación...", icon="📚")