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


#backend_fix.py - VERSIÓN ACTUALIZADA CON SALES AUTOMATION
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import random

# Configurar variables de entorno mínimas requeridas
os.environ['ALLOWED_HOSTS'] = '["localhost", "127.0.0.1", "0.0.0.0"]'
os.environ['CORS_ORIGINS'] = '["http://localhost:3000", "http://localhost:8501"]'
os.environ['ALERT_EMAIL_RECIPIENTS'] = '["admin@example.com"]'
os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
os.environ['HUBSPOT_ACCESS_TOKEN'] = 'demo-token'

app = FastAPI(
    title="Sales Automation API - Demo Mode",
    description="Backend de demostración para el Sales Automation Dashboard",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos de demostración
demo_leads = []
lead_counter = 1000

@app.get("/")
async def root():
    return {
        "message": "Sales Automation API - Demo Mode", 
        "status": "active",
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/docs")
async def get_docs():
    """Redirigir a la documentación interactiva"""
    return {"message": "Visita /docs para la documentación interactiva"}

@app.get("/dashboard/analytics")
async def get_analytics():
    """Endpoint de analytics de demo"""
    return {
        "total_leads": 47,
        "hot_leads": 14,
        "conversion_rate": 16.2,
        "top_sources": [
            {"source": "website", "count": 18},
            {"source": "social_media", "count": 13},
            {"source": "referral", "count": 9},
            {"source": "event", "count": 5},
            {"source": "cold_call", "count": 2}
        ],
        "average_score": 69.5,
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/webhook/lead")
async def capture_lead(lead_data: dict):
    """Endpoint de captura de lead de demo"""
    global lead_counter
    
    lead_id = lead_counter
    lead_counter += 1
    
    # Calcular score demo basado en los datos
    score = random.randint(40, 95)
    
    # Guardar lead en memoria
    demo_lead = {
        "id": lead_id,
        **lead_data,
        "score": score,
        "created_at": datetime.now().isoformat(),
        "status": "new"
    }
    demo_leads.append(demo_lead)
    
    return {
        "success": True,
        "lead_id": lead_id,
        "score": score,
        "message": f"Lead {lead_data.get('name', 'demo')} capturado exitosamente en modo demo",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/chat/message")
async def chat_message(message_data: dict):
    """Endpoint de chat de demo"""
    lead_id = message_data.get("lead_id", 1)
    user_message = message_data.get("message", "")
    
    # Respuestas predefinidas basadas en el mensaje
    responses = {
        "hola": "¡Hola! Soy tu asistente de ventas en modo demostración. ¿En qué puedo ayudarte hoy?",
        "precio": "Nuestros precios varían según el servicio. ¿Podrías contarme más sobre lo que necesitas?",
        "servicio": "Ofrecemos soluciones personalizadas de automatización de ventas. ¿Qué tipo de negocio tienes?",
        "contacto": "Puedes contactarnos en demo@empresa.com o llamarnos al +1234567890",
        "demo": "¡Claro! Podemos agendar una demostración. ¿Qué día y hora te viene bien?"
    }
    
    # Buscar respuesta o usar una genérica
    response_text = "¡Gracias por tu mensaje! En un entorno real, nuestro sistema de IA analizaría tu consulta para darte la mejor respuesta personalizada."
    
    for keyword, response in responses.items():
        if keyword in user_message.lower():
            response_text = response
            break
    
    return {
        "response": response_text,
        "lead_score": random.randint(60, 85),
        "conversation_id": message_data.get("conversation_id", f"demo_{datetime.now().timestamp()}"),
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.get("/leads/{lead_id}")
async def get_lead_details(lead_id: int):
    """Endpoint de detalles de lead de demo"""
    # Buscar lead en datos demo
    lead = next((l for l in demo_leads if l["id"] == lead_id), None)
    
    if not lead:
        # Crear lead demo si no existe
        lead = {
            "id": lead_id,
            "name": f"Lead Demo {lead_id}",
            "email": f"lead{lead_id}@demo.com",
            "phone": f"+123456789{lead_id % 10}",
            "company": f"Empresa Demo {lead_id}",
            "source": "demo",
            "score": random.randint(50, 90),
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
    
    interactions = [
        {
            "message": "Hola, me interesa conocer más sobre sus servicios",
            "response": "¡Claro! ¿Podrías contarme más sobre tu negocio?",
            "timestamp": "2024-01-15T10:00:00"
        },
        {
            "message": "Tengo una empresa de tecnología con 50 empleados",
            "response": "Perfecto, podemos ayudarte con la automatización de ventas.",
            "timestamp": "2024-01-15T10:05:00"
        }
    ]
    
    return {
        "lead": lead,
        "interactions": interactions,
        "score_breakdown": {
            "engagement": random.randint(60, 95),
            "demographics": random.randint(50, 90),
            "behavior": random.randint(55, 85)
        },
        "mode": "demo"
    }

@app.get("/hubspot/sync-status")
async def get_sync_status():
    """Endpoint de estado de HubSpot de demo"""
    return {
        "total_leads": len(demo_leads) + 45,
        "synced_to_hubspot": len(demo_leads) + 32,
        "pending_sync": 13,
        "sync_percentage": round(((len(demo_leads) + 32) / (len(demo_leads) + 45)) * 100, 1),
        "hubspot_configured": True,
        "mode": "demo",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/hubspot/sync-lead/{lead_id}")
async def sync_lead_to_hubspot(lead_id: int):
    """Sincronizar lead con HubSpot - demo"""
    return {
        "success": True,
        "message": f"Lead {lead_id} sincronizado con HubSpot (modo demo)",
        "hubspot_id": f"hubspot_demo_{lead_id}",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/hubspot/bulk-sync")
async def trigger_bulk_sync():
    """Sincronización masiva - demo"""
    return {
        "success": True,
        "message": "Sincronización masiva con HubSpot iniciada (modo demo)",
        "leads_processed": len(demo_leads),
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/leads/{lead_id}/nurture")
async def trigger_nurturing_sequence(lead_id: int, sequence_type: str = "default"):
    """Secuencia de nurturing - demo"""
    sequences = {
        "default": "Secuencia de nurturing estándar iniciada",
        "premium": "Secuencia premium para leads calificados iniciada",
        "reactivation": "Secuencia de reactivación para leads inactivos iniciada"
    }
    
    return {
        "success": True,
        "message": sequences.get(sequence_type, "Secuencia de nurturing iniciada"),
        "sequence_type": sequence_type,
        "lead_id": lead_id,
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.post("/hubspot/create-deal/{lead_id}")
async def create_hubspot_deal(lead_id: int, deal_data: dict):
    """Crear oportunidad en HubSpot - demo"""
    return {
        "success": True,
        "deal_id": f"deal_demo_{int(datetime.now().timestamp())}",
        "deal_name": deal_data.get('deal_name', 'Oportunidad Demo'),
        "amount": deal_data.get('amount', 0),
        "stage": deal_data.get('stage', 'qualifiedtobuy'),
        "message": "Oportunidad creada exitosamente en HubSpot (modo demo)",
        "hubspot_deal_id": f"hubspot_deal_{random.randint(10000, 99999)}",
        "timestamp": datetime.now().isoformat(),
        "mode": "demo"
    }

@app.get("/leads")
async def get_all_leads():
    """Obtener todos los leads - demo"""
    return {
        "leads": demo_leads[-10:],  # Últimos 10 leads
        "total_count": len(demo_leads),
        "mode": "demo"
    }

if __name__ == "__main__":
    print("🚀 INICIANDO BACKEND DE DEMOSTRACIÓN...")
    print("=" * 50)
    print("📊 API Demo disponible en: http://localhost:8080")
    print("📚 Documentación en: http://localhost:8080/docs")
    print("❤️  Health check en: http://localhost:8080/health")
    print("=" * 50)
    print("🖥️  Frontend disponible en: http://localhost:8501")
    print("⏹️  Presiona Ctrl+C para detener el servidor")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")