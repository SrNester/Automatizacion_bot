# app.py - VERSIÓN ACTUALIZADA CON SALES AUTOMATION
import streamlit as st
import sys
import os
import json
from datetime import datetime

# Agregar paths para imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'components'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Importar componentes
from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metrics
from components.controls import render_controls
from components.history import render_history
from components.analytics import render_analytics
from components.sales_automation import render_sales_automation
from components.diagnostics import render_diagnostics_panel

# Importar core
from core.session_manager import SessionManager
from core.config_manager import ConfigManager
from core.automation_bot import AutomationBot
from core.security import SecurityManager

class AutomationDashboard:
    def __init__(self):
        self.setup_page_config()
        self.security_manager = SecurityManager()
        self.session_manager = SessionManager()
        self.config_manager = ConfigManager()
        self.automation_bot = AutomationBot()
        
        # Inicializar datos de ejemplo
        self.initialize_sample_data()
    
    def setup_page_config(self):
        """Configurar la página de Streamlit"""
        st.set_page_config(
            page_title="🤖 Sales Automation Dashboard",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Cargar estilos CSS personalizados
        self.load_custom_styles()
    
    def load_custom_styles(self):
        """Cargar estilos CSS personalizados"""
        try:
            with open('static/css/custom_styles.css', 'r') as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        except FileNotFoundError:
            # Estilos básicos si el archivo no existe
            st.markdown("""
            <style>
            .metric-card {
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                border-left: 4px solid #1f77b4;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin: 0.5rem 0;
            }
            </style>
            """, unsafe_allow_html=True)
    
    def initialize_sample_data(self):
        """Inicializar datos de ejemplo para demostración"""
        if len(self.session_manager.sessions) == 0:
            sample_sessions = [
                {
                    "id": 1,
                    "session_id": "SESSION_0001",
                    "platform": "Sales Automation",
                    "action": "Capturar Lead",
                    "status": "completed",
                    "products_processed": 1,
                    "duration": 2.5,
                    "errors": 0,
                    "is_real_data": False,
                    "timestamp": (datetime.now()).isoformat()
                },
                {
                    "id": 2,
                    "session_id": "SESSION_0002",
                    "platform": "Sales Automation", 
                    "action": "Chat con Lead",
                    "status": "completed",
                    "products_processed": 1,
                    "duration": 3.2,
                    "errors": 0,
                    "is_real_data": False,
                    "timestamp": (datetime.now()).isoformat()
                },
                {
                    "id": 3,
                    "session_id": "SESSION_0003",
                    "platform": "Mercado Libre",
                    "action": "Monitorear Precios",
                    "status": "completed",
                    "products_processed": 25,
                    "duration": 45.2,
                    "errors": 0,
                    "is_real_data": False,
                    "timestamp": (datetime.now()).isoformat()
                }
            ]
            self.session_manager.sessions = sample_sessions
            self.session_manager.save_sessions()
    
    def render_login(self):
        """Renderizar pantalla de login"""
        st.markdown(
            """
            <div style='text-align: center; padding: 4rem 0;'>
                <h1>🤖 Sales Automation Dashboard</h1>
                <p style='color: #666;'>Sistema Integrado de Automatización de Ventas</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                st.subheader("🔐 Iniciar Sesión")
                
                username = st.text_input("Usuario", placeholder="admin@sales.com")
                password = st.text_input("Contraseña", type="password", placeholder="••••••••")
                
                if st.form_submit_button("🚀 Ingresar al Dashboard", use_container_width=True):
                    if username and password:
                        if self.security_manager.authenticate(username, password):
                            st.session_state.authenticated = True
                            st.session_state.user = username
                            st.rerun()
                        else:
                            st.error("❌ Credenciales incorrectas")
                    else:
                        st.warning("⚠️ Por favor completa todos los campos")
            
            st.markdown("---")
            st.info("**Demo:** Usa 'admin' / 'admin' para acceder")
    
    def render_main_layout(self):
        """Renderizar layout principal ACTUALIZADO"""
        # Header
        render_header()
        
        # Sidebar
        config_data = render_sidebar(self.config_manager)
        
        # Métricas principales
        render_metrics(self.session_manager)
        
        # PESTAÑAS ACTUALIZADAS - AGREGAR SALES AUTOMATION
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🎮 Control", "🤖 Ventas", "📊 Analytics", "📋 Historial", "⚙️ Configuración", "🔧 Diagnóstico"
        ])
        
        with tab1:
            render_controls(self.automation_bot, self.session_manager, config_data)
        
        with tab2:
            render_sales_automation(self.automation_bot, self.session_manager)
        
        with tab3:
            render_analytics(self.session_manager)
        
        with tab4:
            render_history(self.session_manager)
        
        with tab5:
            self.render_configuration_tab()
        
        with tab6:
            render_diagnostics_panel(self.automation_bot)
    
    def render_configuration_tab(self):
        """Renderizar pestaña de configuración"""
        st.header("⚙️ Configuración del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Configuración General")
            self.config_manager.render_general_settings()
            
            st.subheader("Configuración de Seguridad")
            self.security_manager.render_security_settings()
        
        with col2:
            st.subheader("Configuración de Backend")
            self.render_backend_configuration()
            
            st.subheader("Preferencias de UI")
            self.config_manager.render_ui_settings()
    
    def render_backend_configuration(self):
        """Configuración específica del backend FastAPI"""
        st.subheader("🔗 Configuración del Backend")
        
        with st.form("backend_config_form"):
            backend_url = st.text_input(
                "URL del Backend FastAPI",
                value="http://localhost:8000",
                help="URL donde está ejecutándose tu servidor FastAPI"
            )
            
            timeout = st.number_input(
                "Timeout (segundos)",
                min_value=5,
                max_value=60,
                value=10,
                help="Tiempo máximo de espera para requests"
            )
            
            auto_retry = st.checkbox(
                "Reintento automático",
                value=True,
                help="Reintentar automáticamente en caso de error de conexión"
            )
            
            if st.form_submit_button("💾 Guardar Configuración Backend"):
                # Aquí guardarías la configuración
                st.success("✅ Configuración del backend guardada")
    
    def run(self):
        """Ejecutar la aplicación"""
        # Verificar autenticación
        if not hasattr(st.session_state, 'authenticated'):
            st.session_state.authenticated = False
        
        if not st.session_state.authenticated:
            self.render_login()
        else:
            self.render_main_layout()

# Punto de entrada de la aplicación
if __name__ == "__main__":
    dashboard = AutomationDashboard()
    dashboard.run()