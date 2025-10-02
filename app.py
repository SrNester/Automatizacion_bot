import streamlit as st
import threading
import uvicorn
import time
import sys
import os
from pathlib import Path
import requests
import logging
import subprocess

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agregar el directorio actual al path de Python
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

class UnifiedApp:
    def __init__(self):
        self.automation_bot = None
        self.session_manager = None
        self.backend_process = None
        self.backend_running = False
        self.backend_port = 8000
        
    def initialize_services(self):
        """Inicializar todos los servicios"""
        try:
            # Usar imports absolutos
            from .frontend.core.session_manager import SessionManager
            from .frontend.core.automation_bot import AutomationBot
            
            self.session_manager = SessionManager()
            self.automation_bot = AutomationBot()
            
            logger.info("✅ Servicios del frontend inicializados")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            return self.initialize_services_fallback()
    
    def initialize_services_fallback(self):
        """Fallback para inicialización de servicios"""
        try:
            # Intentar importar directamente
            import importlib.util
            
            # SessionManager
            session_manager_path = current_dir / "core" / "session_manager.py"
            if session_manager_path.exists():
                session_manager_spec = importlib.util.spec_from_file_location(
                    "session_manager", 
                    session_manager_path
                )
                session_manager_module = importlib.util.module_from_spec(session_manager_spec)
                session_manager_spec.loader.exec_module(session_manager_module)
                self.session_manager = session_manager_module.SessionManager()
            
            # AutomationBot
            automation_bot_path = current_dir / "core" / "automation_bot.py"
            if automation_bot_path.exists():
                automation_bot_spec = importlib.util.spec_from_file_location(
                    "automation_bot", 
                    automation_bot_path
                )
                automation_bot_module = importlib.util.module_from_spec(automation_bot_spec)
                automation_bot_spec.loader.exec_module(automation_bot_module)
                self.automation_bot = automation_bot_module.AutomationBot()
            
            logger.info("✅ Servicios inicializados (fallback)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en fallback: {e}")
            return False
    
    def start_backend(self):
        """Iniciar backend FastAPI desde app/main.py"""
        try:
            backend_dir = current_dir / "app"
            
            if not backend_dir.exists():
                logger.error(f"❌ Carpeta backend no encontrada: {backend_dir}")
                return False
            
            # Verificar que main.py existe
            main_py = backend_dir / "main.py"
            if not main_py.exists():
                logger.error(f"❌ main.py no encontrado: {main_py}")
                return False
            
            logger.info(f"🎯 Iniciando backend desde: {backend_dir}")
            
            # Usar subprocess para evitar problemas de imports
            self.backend_process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", 
                "main:app",  # ✅ Cambiado a "main:app" para tu estructura
                "--host", "0.0.0.0",
                "--port", str(self.backend_port),
                "--log-level", "info"
            ], cwd=backend_dir)  # ✅ Ejecutar desde la carpeta app/
            
            self.backend_running = True
            
            # Esperar a que el backend esté listo
            for i in range(15):
                if self.check_backend_health():
                    logger.info("✅ Backend iniciado correctamente")
                    return True
                time.sleep(2)
                if i % 5 == 0:
                    logger.info(f"⏳ Esperando backend... ({i+1}/15)")
            
            logger.warning("⚠️ Backend iniciado pero no responde inmediatamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error iniciando backend: {e}")
            return self.start_backend_fallback()
    
    def start_backend_fallback(self):
        """Método alternativo para iniciar backend"""
        try:
            backend_dir = current_dir / "app"
            
            # Ejecutar directamente el módulo
            self.backend_process = subprocess.Popen([
                sys.executable, 
                str(backend_dir / "main.py")
            ], cwd=backend_dir)
            
            self.backend_running = True
            time.sleep(5)
            
            if self.check_backend_health():
                logger.info("✅ Backend iniciado (fallback)")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Error en fallback backend: {e}")
            return False
    
    def check_backend_health(self):
        """Verificar si el backend está funcionando"""
        try:
            response = requests.get(
                f"http://localhost:{self.backend_port}/health", 
                timeout=2
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_backend_url(self, path=""):
        """Obtener URL del backend"""
        return f"http://localhost:{self.backend_port}{path}"
    
    def run(self):
        """Ejecutar aplicación unificada"""
        st.set_page_config(
            page_title="Sales Automation Bot",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Sidebar simplificada
        with st.sidebar:
            st.title("⚙️ Sistema")
            
            # Estado del sistema
            backend_status = "🟢 Activo" if self.check_backend_health() else "🔴 Inactivo"
            st.write(f"Backend: {backend_status}")
            
            frontend_status = "🟢 Listo" if self.automation_bot else "🔴 No Inicializado"
            st.write(f"Frontend: {frontend_status}")
            
            st.markdown("---")
            
            # Controles
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Iniciar Todo", use_container_width=True, type="primary"):
                    self.initialize_all_services()
            
            with col2:
                if st.button("🔄 Reiniciar", use_container_width=True):
                    st.rerun()
            
            # Controles individuales
            if st.button("🔧 Solo Backend", use_container_width=True):
                if self.start_backend():
                    st.success("✅ Backend iniciado")
                    time.sleep(2)
                    st.rerun()
            
            if st.button("📊 Solo Frontend", use_container_width=True):
                if self.initialize_services():
                    st.success("✅ Frontend listo")
                    time.sleep(2)
                    st.rerun()
            
            # Enlaces si el backend está activo
            if self.check_backend_health():
                st.markdown("---")
                st.subheader("🔗 Enlaces Backend")
                st.markdown(f"[📡 API Docs]({self.get_backend_url('/docs')})")
                st.markdown(f"[❤️ Health]({self.get_backend_url('/health')})")
        
        # Contenido principal
        self.run_main_content()
    
    def run_main_content(self):
        """Ejecutar contenido principal"""
        st.title("🤖 Sales Automation Bot - Sistema Unificado")
        
        # Verificar estados
        backend_healthy = self.check_backend_health()
        frontend_ready = self.automation_bot is not None
        
        # Tarjetas de estado
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_icon = "🟢" if frontend_ready else "🔴"
            st.metric("Frontend", f"{status_icon} {'Listo' if frontend_ready else 'No Inicializado'}")
        
        with col2:
            status_icon = "🟢" if backend_healthy else "🔴"
            st.metric("Backend API", f"{status_icon} {'Activo' if backend_healthy else 'Inactivo'}")
        
        with col3:
            if frontend_ready and backend_healthy:
                st.metric("Sistema", "🟢 Operativo")
            elif frontend_ready or backend_healthy:
                st.metric("Sistema", "🟡 Parcial")
            else:
                st.metric("Sistema", "🔴 Inactivo")
        
        # Mostrar contenido según el estado
        if not frontend_ready and not backend_healthy:
            self.show_welcome_screen()
        elif frontend_ready and backend_healthy:
            self.show_combined_dashboard()
        elif frontend_ready:
            self.show_frontend_only()
        else:
            self.show_backend_only()
    
    def show_welcome_screen(self):
        """Pantalla de bienvenida"""
        st.markdown("---")
        st.subheader("🎯 Bienvenido al Sales Automation Bot")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **🚀 Características:**
            
            • **Automatización de Ventas**
            • **Gestión de Leads** 
            • **IA Integrada**
            • **HubSpot Sync**
            • **Analytics Avanzados**
            """)
        
        with col2:
            st.warning("""
            **⚡ Para Comenzar:**
            
            1. **Click en '🚀 Iniciar Todo'**
            2. **Espera la inicialización**
            3. **Accede a la documentación**
            
            **📁 Estructura:**
            - `app.py` - Streamlit (frontend)
            - `app/main.py` - FastAPI (backend)
            - `core/` - Servicios principales
            """)
        
        st.markdown("---")
        
        # Inicialización rápida
        if st.button("🎯 Inicializar Sistema Completo", type="primary", use_container_width=True):
            self.initialize_all_services()
    
    def initialize_all_services(self):
        """Inicializar todos los servicios"""
        with st.spinner("🔄 Inicializando sistema completo..."):
            # Inicializar frontend
            frontend_ready = self.initialize_services()
            
            # Inicializar backend
            backend_ready = self.start_backend()
            
            if frontend_ready:
                st.success("✅ Frontend inicializado")
                if backend_ready:
                    st.success("✅ Backend inicializado")
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ Error inicializando servicios")
    
    def show_combined_dashboard(self):
        """Mostrar dashboard combinado"""
        st.success("✅ Sistema completo operativo")
        
        # Mostrar información del backend
        try:
            response = requests.get(self.get_backend_url("/dashboard/analytics"), timeout=5)
            if response.status_code == 200:
                analytics = response.json()
                self.show_backend_analytics(analytics)
        except:
            pass
        
        # Ejecutar dashboard del frontend
        try:
            from frontend.dashboard import Dashboard
            dashboard = Dashboard(self.automation_bot, self.session_manager)
            dashboard.run()
        except Exception as e:
            st.error(f"❌ Error cargando dashboard: {e}")
            self.show_frontend_fallback()
    
    def show_backend_analytics(self, analytics):
        """Mostrar analytics del backend"""
        st.subheader("📊 Métricas en Tiempo Real")
        
        if analytics:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Leads", analytics.get("total_leads", 0))
            
            with col2:
                st.metric("Hot Leads", analytics.get("hot_leads", 0))
            
            with col3:
                st.metric("Tasa Conversión", f"{analytics.get('conversion_rate', 0)}%")
            
            with col4:
                st.metric("Score Promedio", f"{analytics.get('average_score', 0)}")
        
        st.markdown("---")
    
    def show_frontend_only(self):
        """Mostrar solo frontend"""
        st.warning("⚠️ Ejecutando en modo Solo Frontend")
        
        try:
            from frontend.dashboard import Dashboard
            dashboard = Dashboard(self.automation_bot, self.session_manager)
            dashboard.run()
        except Exception as e:
            st.error(f"❌ Error cargando dashboard: {e}")
            self.show_frontend_fallback()
    
    def show_backend_only(self):
        """Mostrar información del backend"""
        st.info("🔧 Modo Backend - API REST ejecutándose")
        
        st.subheader("📋 Endpoints Disponibles")
        
        endpoints = [
            "GET    /health - Estado del sistema",
            "GET    /docs - Documentación Swagger UI", 
            "POST   /webhook/lead - Capturar nuevo lead",
            "POST   /chat/message - Mensaje de chat con IA",
            "GET    /dashboard/analytics - Métricas del dashboard",
            "POST   /hubspot/sync-lead/{lead_id} - Sincronizar lead",
            "POST   /hubspot/create-deal/{lead_id} - Crear oportunidad",
            "GET    /hubspot/sync-status - Estado sincronización",
            "GET    /leads/{lead_id} - Detalles de lead",
            "POST   /leads/{lead_id}/nurture - Secuencia nurturing"
        ]
        
        for endpoint in endpoints:
            st.code(endpoint)
    
    def show_frontend_fallback(self):
        """Fallback cuando el dashboard no carga"""
        st.error("❌ No se pudo cargar el dashboard completo")
        
        # Mostrar componentes básicos si están disponibles
        if self.automation_bot and self.session_manager:
            try:
                # Intentar importar componentes individuales
                from frontend.components.metrics import render_metrics
                from frontend.components.controls import render_controls
                
                render_metrics(self.session_manager)
                render_controls(self.automation_bot, self.session_manager, {})
                
            except Exception as e:
                st.error(f"❌ Error cargando componentes: {e}")
                st.info("💡 Verifica la estructura de archivos y los imports")

def main():
    """Función principal"""
    unified_app = UnifiedApp()
    unified_app.run()

if __name__ == "__main__":
    main()