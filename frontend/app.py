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
        
        # Inicializar datos de ejemplo si no existen
        self.initialize_sample_data()
    
    def setup_page_config(self):
        """Configurar la página de Streamlit"""
        st.set_page_config(
            page_title="🤖 Bot de Automatización - Dashboard",
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
                    "platform": "Mercado Libre",
                    "action": "Monitorear Precios",
                    "status": "completed",
                    "products_processed": 25,
                    "duration": 45.2,
                    "errors": 0,
                    "timestamp": "2024-01-15T09:30:00"
                },
                {
                    "id": 2,
                    "session_id": "SESSION_0002", 
                    "platform": "Amazon",
                    "action": "Actualizar Inventario",
                    "status": "completed",
                    "products_processed": 18,
                    "duration": 32.1,
                    "errors": 1,
                    "timestamp": "2024-01-15T11:15:00"
                },
                {
                    "id": 3,
                    "session_id": "SESSION_0003",
                    "platform": "Shopify",
                    "action": "Buscar Productos",
                    "status": "failed",
                    "products_processed": 0,
                    "duration": 12.5,
                    "errors": 3,
                    "timestamp": "2024-01-15T14:45:00"
                }
            ]
            self.session_manager.sessions = sample_sessions
            self.session_manager.save_sessions()
    
    def render_login(self):
        """Renderizar pantalla de login"""
        st.markdown(
            """
            <div style='text-align: center; padding: 4rem 0;'>
                <h1>🤖 Bot de Automatización</h1>
                <p style='color: #666;'>Sistema de Gestión de Ventas Automatizadas</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                st.subheader("🔐 Iniciar Sesión")
                
                username = st.text_input("Usuario", placeholder="usuario@empresa.com")
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
        """Renderizar layout principal"""
        # Header
        render_header()
        
        # Sidebar
        config_data = render_sidebar(self.config_manager)
        
        # Métricas principales
        render_metrics(self.session_manager)
        
        # Pestañas principales
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🎮 Control", "📊 Analytics", "📋 Historial", "⚙️ Configuración", "🔧 Herramientas"
        ])
        
        with tab1:
            render_controls(self.automation_bot, self.session_manager, config_data)
        
        with tab2:
            render_analytics(self.session_manager)
        
        with tab3:
            render_history(self.session_manager)
        
        with tab4:
            self.render_configuration_tab()
        
        with tab5:
            self.render_tools_tab()
    
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
            st.subheader("Configuración de Plataformas")
            self.config_manager.render_platforms_settings()
            
            st.subheader("Preferencias de UI")
            self.config_manager.render_ui_settings()
    
    def render_tools_tab(self):
        """Renderizar pestaña de herramientas"""
        st.header("🔧 Herramientas del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Mantenimiento")
            
            if st.button("🔄 Limpiar Cache", use_container_width=True):
                self.session_manager.clear_old_sessions(days=7)
                st.success("✅ Cache limpiado exitosamente")
            
            if st.button("📊 Generar Reporte Completo", use_container_width=True):
                self.generate_comprehensive_report()
            
            if st.button("🔍 Ver Logs del Sistema", use_container_width=True):
                self.show_system_logs()
        
        with col2:
            st.subheader("Utilidades")
            
            if st.button("📤 Exportar Todos los Datos", use_container_width=True):
                self.export_all_data()
            
            if st.button("🛠️ Probar Conexiones", use_container_width=True):
                self.test_connections()
            
            if st.button("📝 Documentación", use_container_width=True):
                self.show_documentation()
    
    def generate_comprehensive_report(self):
        """Generar reporte completo del sistema"""
        stats = self.session_manager.get_statistics()
        
        report = f"""
        # 📊 Reporte del Sistema de Automatización
        **Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        ## 📈 Métricas Principales
        - **Sesiones Totales:** {stats['total_sessions']}
        - **Tasa de Éxito:** {stats['success_rate']:.1f}%
        - **Productos Procesados:** {stats['total_products']}
        - **Tiempo Promedio:** {stats['avg_time']:.1f}s
        
        ## 🌐 Plataformas Configuradas
        """
        
        for platform, config in self.config_manager.configs['platforms'].items():
            report += f"- **{platform.replace('_', ' ').title()}:** {'✅ Habilitada' if config.get('enabled') else '❌ Deshabilitada'}\n"
        
        st.download_button(
            label="📥 Descargar Reporte PDF",
            data=report,
            file_name=f"reporte_automatizacion_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
        st.success("📋 Reporte generado exitosamente")
    
    def show_system_logs(self):
        """Mostrar logs del sistema"""
        st.subheader("📝 Logs del Sistema")
        
        try:
            with open('logs/dashboard.log', 'r') as f:
                logs = f.read()
            
            st.text_area("Logs recientes", logs, height=300)
        except FileNotFoundError:
            st.info("No hay logs disponibles aún")
    
    def export_all_data(self):
        """Exportar todos los datos"""
        import pandas as pd
        
        # Exportar sesiones
        df_sessions = pd.DataFrame(self.session_manager.sessions)
        csv_sessions = df_sessions.to_csv(index=False)
        
        st.download_button(
            label="📥 Descargar Sesiones (CSV)",
            data=csv_sessions,
            file_name="sesiones_automatizacion.csv",
            mime="text/csv"
        )
    
    def test_connections(self):
        """Probar conexiones del sistema"""
        with st.spinner("🔍 Probando conexiones..."):
            import time
            time.sleep(2)
            
            results = [
                {"Servicio": "Base de datos", "Estado": "✅ Conectado", "Latencia": "45ms"},
                {"Servicio": "API Mercado Libre", "Estado": "✅ Conectado", "Latencia": "120ms"},
                {"Servicio": "API Amazon", "Estado": "⚠️ Lento", "Latencia": "450ms"},
                {"Servicio": "Servidor de Logs", "Estado": "✅ Conectado", "Latencia": "30ms"},
            ]
            
            st.table(results)
    
    def show_documentation(self):
        """Mostrar documentación"""
        st.subheader("📚 Documentación del Sistema")
        
        with st.expander("🎯 Cómo Usar el Dashboard", expanded=True):
            st.markdown("""
            ### Guía Rápida de Uso
            
            1. **🎮 Control**: Ejecuta automatizaciones manualmente
            2. **📊 Analytics**: Ve métricas y gráficos de rendimiento  
            3. **📋 Historial**: Revisa sesiones anteriores
            4. **⚙️ Configuración**: Personaliza el sistema
            5. **🔧 Herramientas**: Utilidades avanzadas
            
            ### Flujo de Trabajo Recomendado
            - Configura tus plataformas primero
            - Prueba con ejecuciones manuales
            - Revisa el historial y analytics
            - Optimiza configuraciones basado en resultados
            """)
        
        with st.expander("🔧 Configuración de Plataformas"):
            st.markdown("""
            ### Mercado Libre
            - Necesitas credenciales de desarrollador
            - Configura los timeouts apropiadamente
            - Respeta los límites de la API
            
            ### Amazon
            - Requiere cuenta profesional
            - Configuración específica por región
            - Considera límites de solicitudes
            """)
    
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