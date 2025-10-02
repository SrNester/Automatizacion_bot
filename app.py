import streamlit as st
import threading
import uvicorn
import time
import sys
import os
from pathlib import Path
import requests
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnifiedApp:
    def __init__(self):
        self.automation_bot = None
        self.session_manager = None
        self.backend_thread = None
        self.backend_running = False
        self.backend_port = 8000
        
    def initialize_services(self):
        """Inicializar todos los servicios"""
        try:
            # Importar servicios del frontend
            from .frontend.core.session_manager import SessionManager
            from .frontend.core.automation_bot import AutomationBot
            
            self.session_manager = SessionManager()
            self.automation_bot = AutomationBot()
            
            logger.info("✅ Servicios del frontend inicializados")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            return False
    
    def start_backend(self):
        """Iniciar backend FastAPI desde tu main.py"""
        def run_backend():
            try:
                # Cambiar al directorio backend para imports relativos
                backend_dir = Path(__file__).parent / "backend"
                os.chdir(backend_dir)
                
                # Ejecutar tu main.py directamente
                uvicorn.run(
                    "main:app",  # ✅ Apunta a TU main.py
                    host="0.0.0.0",
                    port=self.backend_port,
                    log_level="info",
                    reload=False  # Desactivar reload en producción
                )
            except Exception as e:
                logger.error(f"❌ Error en backend thread: {e}")
            finally:
                # Volver al directorio original
                os.chdir(Path(__file__).parent)
        
        if not self.backend_running:
            try:
                self.backend_thread = threading.Thread(target=run_backend, daemon=True)
                self.backend_thread.start()
                self.backend_running = True
                
                # Esperar a que el backend esté listo
                for i in range(10):
                    if self.check_backend_health():
                        logger.info("✅ Backend iniciado correctamente")
                        return True
                    time.sleep(1)
                
                logger.warning("⚠️ Backend iniciado pero no responde inmediatamente")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error iniciando backend: {e}")
                return False
        return True
    
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
            page_title="Sales Automation Bot - Sistema Unificado",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Sidebar para controles del sistema
        with st.sidebar:
            st.title("⚙️ Configuración del Sistema")
            
            # Estado del sistema
            st.subheader("📊 Estado del Sistema")
            
            backend_status = "🟢 Activo" if self.check_backend_health() else "🔴 Inactivo"
            st.write(f"Backend API: {backend_status}")
            
            frontend_status = "🟢 Listo" if self.automation_bot else "🔴 No Inicializado"
            st.write(f"Frontend: {frontend_status}")
            
            # Enlaces rápidos si el backend está activo
            if self.check_backend_health():
                st.markdown(f"[📡 API Docs]({self.get_backend_url('/docs')})")
                st.markdown(f"[❤️ Health Check]({self.get_backend_url('/health')})")
                st.markdown(f"[📊 Redoc Docs]({self.get_backend_url('/redoc')})")
            
            st.markdown("---")
            
            # Controles del sistema
            st.subheader("🎛️ Controles del Sistema")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Sistema Completo", use_container_width=True):
                    self.initialize_all_services()
                    
            with col2:
                if st.button("🔄 Reiniciar", use_container_width=True):
                    st.rerun()
            
            # Controles individuales
            if st.button("🔧 Iniciar Solo Backend", use_container_width=True):
                if self.start_backend():
                    st.success("✅ Backend iniciado")
                    time.sleep(2)
                    st.rerun()
            
            if st.button("📊 Iniciar Solo Frontend", use_container_width=True):
                if self.initialize_services():
                    st.success("✅ Frontend listo")
                    time.sleep(2)
                    st.rerun()
        
        # Contenido principal
        self.run_main_content()
    
    def initialize_all_services(self):
        """Inicializar todos los servicios"""
        with st.spinner("🔄 Inicializando sistema completo..."):
            # Inicializar frontend
            frontend_ready = self.initialize_services()
            
            # Inicializar backend
            backend_ready = self.start_backend()
            
            if frontend_ready and backend_ready:
                st.success("✅ Sistema completo inicializado correctamente")
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ Error inicializando algunos servicios")
    
    def run_main_content(self):
        """Ejecutar contenido principal basado en el estado"""
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
            **🚀 Características del Sistema:**
            
            • **Automatización de Ventas** - Flujos automatizados
            • **Gestión de Leads** - Captura y seguimiento
            • **IA Integrada** - Chatbot inteligente
            • **HubSpot Sync** - Sincronización en tiempo real
            • **Analytics** - Métricas y reportes
            • **Nurturing** - Secuencias automatizadas
            """)
        
        with col2:
            st.warning("""
            **⚡ Para Comenzar:**
            
            1. **Sistema Completo** - Inicia frontend + backend
            2. **Solo Backend** - Solo API REST (puerto 8000)
            3. **Solo Frontend** - Interfaz con datos simulados
            
            **📊 Endpoints Principales:**
            - `POST /webhook/lead` - Capturar leads
            - `POST /chat/message` - Chat con IA
            - `GET /dashboard/analytics` - Métricas
            - `POST /hubspot/sync-lead` - Sincronización
            """)
        
        st.markdown("---")
        
        # Inicialización rápida
        if st.button("🎯 Inicializar Sistema Completo", type="primary", use_container_width=True):
            self.initialize_all_services()
    
    def show_combined_dashboard(self):
        """Mostrar dashboard combinado"""
        st.success("✅ Sistema completo operativo - Todos los servicios activos")
        
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
            st.error(f"❌ Error cargando el dashboard: {e}")
            st.info("💡 Ejecutando en modo backend-only")
            self.show_backend_only()
    
    def show_backend_analytics(self, analytics):
        """Mostrar analytics del backend"""
        st.subheader("📊 Métricas en Tiempo Real del Backend")
        
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
        st.warning("⚠️ Ejecutando en modo Solo Frontend - Backend no disponible")
        
        try:
            from frontend.dashboard import Dashboard
            dashboard = Dashboard(self.automation_bot, self.session_manager)
            dashboard.run()
        except Exception as e:
            st.error(f"❌ Error cargando dashboard: {e}")
    
    def show_backend_only(self):
        """Mostrar información del backend"""
        st.info("🔧 Modo Backend - API REST ejecutándose")
        
        st.subheader("📋 Endpoints de Tu API")
        
        # Endpoints basados en tu main.py
        endpoints = [
            "GET    /health - Estado del sistema",
            "GET    /docs - Documentación Swagger UI",
            "GET    /redoc - Documentación Redoc",
            "POST   /webhook/lead - Capturar nuevo lead",
            "POST   /chat/message - Mensaje de chat con IA", 
            "GET    /dashboard/analytics - Métricas del dashboard",
            "POST   /hubspot/sync-lead/{lead_id} - Sincronizar lead",
            "POST   /hubspot/create-deal/{lead_id} - Crear oportunidad",
            "GET    /hubspot/sync-status - Estado sincronización",
            "POST   /hubspot/bulk-sync - Sincronización masiva",
            "GET    /leads/{lead_id} - Detalles de lead",
            "POST   /leads/{lead_id}/nurture - Secuencia nurturing"
        ]
        
        for endpoint in endpoints:
            st.code(endpoint)
        
        st.markdown("---")
        
        # Información de la base de datos
        try:
            response = requests.get(self.get_backend_url("/hubspot/sync-status"), timeout=5)
            if response.status_code == 200:
                sync_status = response.json()
                self.show_sync_status(sync_status)
        except:
            st.info("📊 La información de sincronización no está disponible")
    
    def show_sync_status(self, sync_status):
        """Mostrar estado de sincronización"""
        st.subheader("🔄 Estado de Sincronización HubSpot")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Leads", sync_status.get("total_leads", 0))
        
        with col2:
            st.metric("Sincronizados", sync_status.get("synced_to_hubspot", 0))
        
        with col3:
            st.metric("Pendientes", sync_status.get("pending_sync", 0))
        
        with col4:
            st.metric("Porcentaje", f"{sync_status.get('sync_percentage', 0)}%")

def main():
    """Función principal"""
    unified_app = UnifiedApp()
    unified_app.run()

if __name__ == "__main__":
    main()