# app_unificada.py
import streamlit as st
import requests
import json
import time
import pandas as pd
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =============================================================================
# CONFIGURACIÓN INICIAL DE STREAMLIT
# =============================================================================
st.set_page_config(
    page_title="Sales Automation Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicar estilos CSS personalizados
st.markdown("""
<style>
.metric-card {
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    border-left: 4px solid #1f77b4;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 1rem;
    transition: transform 0.2s ease;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.session-card {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #28a745;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.status-success { color: #28a745; font-weight: bold; }
.status-error { color: #dc3545; font-weight: bold; }
.status-running { color: #ffc107; font-weight: bold; }

.chat-container {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 1rem;
    background-color: #f9f9f9;
    max-height: 400px;
    overflow-y: auto;
    margin-bottom: 1rem;
}

.chat-message {
    margin-bottom: 1rem;
    padding: 0.5rem;
    border-radius: 8px;
}

.chat-user {
    background-color: #e3f2fd;
    border-left: 4px solid #2196f3;
}

.chat-assistant {
    background-color: #f3e5f5;
    border-left: 4px solid #9c27b0;
}

.chat-system {
    background-color: #e8f5e8;
    border-left: 4px solid #4caf50;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CLASE BACKEND SIMULADO (Reemplaza FastAPI)
# =============================================================================
class SalesAutomationBackend:
    """Simulación del backend FastAPI en memoria"""
    
    def __init__(self):
        self.demo_leads = []
        self.lead_counter = 1000
        self.conversations = {}
        self.sessions = []
    
    def get_health(self):
        return {
            "status": "healthy",
            "mode": "demo",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_analytics(self):
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
    
    def capture_lead(self, lead_data: dict):
        lead_id = self.lead_counter
        self.lead_counter += 1
        
        score = random.randint(40, 95)
        
        demo_lead = {
            "id": lead_id,
            **lead_data,
            "score": score,
            "created_at": datetime.now().isoformat(),
            "status": "new"
        }
        self.demo_leads.append(demo_lead)
        
        return {
            "success": True,
            "lead_id": lead_id,
            "score": score,
            "message": f"Lead {lead_data.get('name', 'demo')} capturado exitosamente",
            "timestamp": datetime.now().isoformat(),
            "mode": "demo"
        }
    
    def chat_message(self, message_data: dict):
        lead_id = message_data.get("lead_id", 1)
        user_message = message_data.get("message", "")
        
        responses = {
            "hola": "¡Hola! Soy tu asistente de ventas. ¿En qué puedo ayudarte hoy?",
            "precio": "Nuestros precios varían según el servicio. ¿Podrías contarme más sobre lo que necesitas?",
            "servicio": "Ofrecemos soluciones personalizadas de automatización de ventas. ¿Qué tipo de negocio tienes?",
            "contacto": "Puedes contactarnos en demo@empresa.com o llamarnos al +1234567890",
            "demo": "¡Claro! Podemos agendar una demostración. ¿Qué día y hora te viene bien?"
        }
        
        response_text = "¡Gracias por tu mensaje! Nuestro sistema de IA analizaría tu consulta para darte la mejor respuesta personalizada."
        
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
    
    def get_lead_details(self, lead_id: int):
        lead = next((l for l in self.demo_leads if l["id"] == lead_id), None)
        
        if not lead:
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
    
    def get_sync_status(self):
        return {
            "total_leads": len(self.demo_leads) + 45,
            "synced_to_hubspot": len(self.demo_leads) + 32,
            "pending_sync": 13,
            "sync_percentage": round(((len(self.demo_leads) + 32) / (len(self.demo_leads) + 45)) * 100, 1),
            "hubspot_configured": True,
            "mode": "demo",
            "timestamp": datetime.now().isoformat()
        }
    
    def sync_lead_to_hubspot(self, lead_id: int):
        return {
            "success": True,
            "message": f"Lead {lead_id} sincronizado con HubSpot",
            "hubspot_id": f"hubspot_demo_{lead_id}",
            "timestamp": datetime.now().isoformat(),
            "mode": "demo"
        }
    
    def trigger_bulk_sync(self):
        return {
            "success": True,
            "message": "Sincronización masiva con HubSpot iniciada",
            "leads_processed": len(self.demo_leads),
            "timestamp": datetime.now().isoformat(),
            "mode": "demo"
        }
    
    def trigger_nurturing_sequence(self, lead_id: int, sequence_type: str = "default"):
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
    
    def create_hubspot_deal(self, lead_id: int, deal_data: dict):
        return {
            "success": True,
            "deal_id": f"deal_demo_{int(datetime.now().timestamp())}",
            "deal_name": deal_data.get('deal_name', 'Oportunidad Demo'),
            "amount": deal_data.get('amount', 0),
            "stage": deal_data.get('stage', 'qualifiedtobuy'),
            "message": "Oportunidad creada exitosamente en HubSpot",
            "hubspot_deal_id": f"hubspot_deal_{random.randint(10000, 99999)}",
            "timestamp": datetime.now().isoformat(),
            "mode": "demo"
        }
    
    def get_all_leads(self):
        return {
            "leads": self.demo_leads[-10:],
            "total_count": len(self.demo_leads),
            "mode": "demo"
        }

# =============================================================================
# GESTOR DE SESIONES (Para las métricas)
# =============================================================================
class SessionManager:
    """Gestor de sesiones para las métricas del dashboard"""
    
    def __init__(self):
        self.sessions = self._generate_sample_sessions()
    
    def _generate_sample_sessions(self):
        """Generar datos de sesiones de ejemplo"""
        sessions = []
        statuses = ['completed', 'failed', 'running']
        platforms = ['Shopify', 'WooCommerce', 'Mercado Libre', 'Amazon']
        
        for i in range(50):
            session_date = datetime.now() - timedelta(hours=random.randint(0, 72))
            sessions.append({
                'id': i + 1,
                'platform': random.choice(platforms),
                'status': random.choice(statuses),
                'products_processed': random.randint(1, 50),
                'duration': random.randint(30, 300),
                'start_time': session_date,
                'end_time': session_date + timedelta(minutes=random.randint(1, 10))
            })
        return sessions
    
    def get_statistics(self):
        """Obtener estadísticas para las métricas"""
        total_sessions = len(self.sessions)
        completed_sessions = len([s for s in self.sessions if s['status'] == 'completed'])
        success_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        total_products = sum(s['products_processed'] for s in self.sessions)
        avg_time = sum(s['duration'] for s in self.sessions) / total_sessions if total_sessions > 0 else 0
        
        # Sesiones de hoy
        today = datetime.now().date()
        sessions_today = len([s for s in self.sessions if s['start_time'].date() == today])
        
        return {
            "total_sessions": total_sessions,
            "success_rate": success_rate,
            "total_products": total_products,
            "avg_time": avg_time,
            "sessions_today": sessions_today
        }
    
    def get_recent_sessions(self, limit=10):
        """Obtener sesiones recientes"""
        return sorted(self.sessions, key=lambda x: x['start_time'], reverse=True)[:limit]

# =============================================================================
# COMPONENTES DE MÉTRICAS (Desde tu dashboard.py)
# =============================================================================
def render_metrics(session_manager):
    """Renderizar las métricas principales del dashboard"""
    st.subheader("📊 Métricas de Rendimiento")
    
    # Obtener estadísticas con valores por defecto
    stats = session_manager.get_statistics()
    
    # Asegurar que todas las claves necesarias existen
    safe_stats = {
        "total_sessions": stats.get("total_sessions", 0),
        "success_rate": stats.get("success_rate", 0),
        "total_products": stats.get("total_products", 0),
        "avg_time": stats.get("avg_time", 0),
        "sessions_today": stats.get("sessions_today", 0)
    }
    
    # Crear 4 columnas para las métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            title="Sesiones Totales",
            value=safe_stats["total_sessions"],
            delta=safe_stats["sessions_today"],
            delta_label="hoy",
            icon="📈",
            color="#1f77b4",
            help_text="Total de sesiones de automatización ejecutadas"
        )
    
    with col2:
        render_metric_card(
            title="Tasa de Éxito", 
            value=f"{safe_stats['success_rate']:.1f}%",
            delta=2.5,
            delta_label="vs. ayer",
            icon="✅",
            color="#28a745",
            help_text="Porcentaje de sesiones completadas exitosamente"
        )
    
    with col3:
        render_metric_card(
            title="Productos Procesados",
            value=safe_stats["total_products"],
            delta=127,
            delta_label="últimas 24h",
            icon="📦", 
            color="#ff7f0e",
            help_text="Total de productos procesados por las automatizaciones"
        )
    
    with col4:
        render_metric_card(
            title="Tiempo Promedio",
            value=f"{safe_stats['avg_time']:.1f}s",
            delta=-3.2,
            delta_label="mejoría",
            icon="⏱️",
            color="#dc3545",
            help_text="Tiempo promedio de ejecución por sesión"
        )

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

# =============================================================================
# INICIALIZACIÓN
# =============================================================================
@st.cache_resource
def get_backend():
    return SalesAutomationBackend()

@st.cache_resource
def get_session_manager():
    return SessionManager()

backend = get_backend()
session_manager = get_session_manager()

# =============================================================================
# COMPONENTES DE LA INTERFAZ
# =============================================================================
def render_sidebar():
    """Barra lateral con navegación"""
    with st.sidebar:
        st.title("🚀 Sales Automation")
        st.markdown("---")
        
        # Navegación
        page = st.radio(
            "Navegación",
            ["📊 Dashboard", "👥 Gestión de Leads", "💬 Chat con Leads", "🔄 Sincronización", "⚙️ Configuración"]
        )
        
        st.markdown("---")
        
        # Estado del sistema
        st.subheader("Estado del Sistema")
        health = backend.get_health()
        st.success(f"✅ {health['status'].upper()}")
        st.caption(f"Modo: {health['mode']}")
        
        # Métricas rápidas
        analytics = backend.get_analytics()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Leads", analytics["total_leads"])
        with col2:
            st.metric("Tasa Conversión", f"{analytics['conversion_rate']}%")
        
        st.markdown("---")
        st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
    
    return page

def render_dashboard():
    """Página principal del dashboard"""
    st.title("📊 Sales Automation Dashboard")
    
    # Métricas de rendimiento
    render_metrics(session_manager)
    
    st.markdown("---")
    
    # Obtener datos de analytics
    analytics = backend.get_analytics()
    
    # Métricas principales de ventas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Leads", analytics["total_leads"], delta="+12%")
    with col2:
        st.metric("Leads Calientes", analytics["hot_leads"], delta="+5%")
    with col3:
        st.metric("Tasa de Conversión", f"{analytics['conversion_rate']}%", delta="+2.1%")
    with col4:
        st.metric("Score Promedio", f"{analytics['average_score']}/100", delta="+3.2")
    
    st.markdown("---")
    
    # Gráficos y datos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Fuentes de Leads")
        sources_df = pd.DataFrame(analytics["top_sources"])
        fig = px.pie(sources_df, values='count', names='source', 
                    title="Distribución por Fuente")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🔄 Estado de Sincronización")
        sync_status = backend.get_sync_status()
        
        # Gráfico de gauge
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = sync_status["sync_percentage"],
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Sincronización HubSpot"},
            delta = {'reference': 80},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90}}
        ))
        st.plotly_chart(fig, use_container_width=True)

def render_lead_management():
    """Gestión de leads"""
    st.title("👥 Gestión de Leads")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("➕ Capturar Nuevo Lead")
        
        with st.form("capture_lead"):
            name = st.text_input("Nombre completo")
            email = st.text_input("Email")
            phone = st.text_input("Teléfono")
            company = st.text_input("Empresa")
            source = st.selectbox("Fuente", ["website", "social_media", "referral", "event", "cold_call"])
            
            if st.form_submit_button("Capturar Lead"):
                if name and email:
                    lead_data = {
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "company": company,
                        "source": source
                    }
                    
                    with st.spinner("Procesando lead..."):
                        result = backend.capture_lead(lead_data)
                        st.success(result["message"])
                        st.info(f"Score asignado: {result['score']}/100")
                else:
                    st.error("Nombre y email son obligatorios")
    
    with col2:
        st.subheader("📋 Últimos Leads Capturados")
        
        leads_data = backend.get_all_leads()
        leads = leads_data["leads"]
        
        if leads:
            for lead in reversed(leads[-5:]):
                with st.container():
                    col_a, col_b, col_c = st.columns([3, 2, 1])
                    with col_a:
                        st.write(f"**{lead.get('name', 'N/A')}**")
                        st.caption(f"{lead.get('company', 'N/A')} • {lead.get('email', 'N/A')}")
                    with col_b:
                        st.write(f"Fuente: {lead.get('source', 'N/A')}")
                        st.write(f"Estado: {lead.get('status', 'N/A')}")
                    with col_c:
                        score = lead.get('score', 0)
                        color = "green" if score > 80 else "orange" if score > 60 else "red"
                        st.metric("Score", score, delta_color="off")
                    
                    st.markdown("---")
        else:
            st.info("No hay leads capturados aún")

def render_chat():
    """Chat con leads"""
    st.title("💬 Chat con Leads")
    
    # Selección de lead
    leads_data = backend.get_all_leads()
    leads = leads_data["leads"]
    
    if leads:
        lead_options = {f"{lead['id']} - {lead['name']}": lead['id'] for lead in leads}
        selected_lead = st.selectbox("Seleccionar Lead", list(lead_options.keys()))
        lead_id = lead_options[selected_lead]
    else:
        lead_id = 1000
        st.info("Usando lead de demostración")
    
    # Área de chat
    st.subheader("Conversación")
    
    # Obtener detalles del lead (incluye historial de conversación)
    lead_details = backend.get_lead_details(lead_id)
    
    # Contenedor de chat con CSS personalizado
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Mostrar historial de conversación
    for interaction in lead_details["interactions"]:
        st.markdown(
            f"""
            <div class="chat-message chat-system">
                <strong>Lead:</strong> {interaction['message']}<br>
                <strong>Sistema:</strong> {interaction['response']}<br>
                <small>🕒 {interaction['timestamp']}</small>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    # Mostrar mensajes adicionales si existen en session_state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    for msg in st.session_state.chat_messages:
        if msg['lead_id'] == lead_id:
            st.markdown(
                f"""
                <div class="chat-message chat-user">
                    <strong>Tú:</strong> {msg['user_message']}<br>
                    <small>🕒 {msg['timestamp']}</small>
                </div>
                """, 
                unsafe_allow_html=True
            )
            st.markdown(
                f"""
                <div class="chat-message chat-assistant">
                    <strong>Asistente:</strong> {msg['response']}<br>
                    <small>🕒 {msg['timestamp']}</small>
                </div>
                """, 
                unsafe_allow_html=True
            )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Input de mensaje
    col1, col2 = st.columns([4, 1])
    with col1:
        user_message = st.text_input("Escribe tu mensaje...", key="chat_input")
    with col2:
        send_button = st.button("Enviar", use_container_width=True)
    
    if send_button and user_message:
        message_data = {
            "lead_id": lead_id,
            "message": user_message,
            "conversation_id": f"conv_{lead_id}"
        }
        
        with st.spinner("Procesando..."):
            response = backend.chat_message(message_data)
            
            # Guardar mensaje en session state
            st.session_state.chat_messages.append({
                'lead_id': lead_id,
                'user_message': user_message,
                'response': response['response'],
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
            
            st.success("Mensaje enviado!")
            time.sleep(1)
            st.rerun()

def render_sync():
    """Sincronización con HubSpot"""
    st.title("🔄 Sincronización con HubSpot")
    
    # Estado actual
    sync_status = backend.get_sync_status()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Estado de Conexión")
        
        if sync_status["hubspot_configured"]:
            st.success("✅ Conectado a HubSpot")
        else:
            st.error("❌ No conectado a HubSpot")
        
        st.metric("Porcentaje Sincronizado", f"{sync_status['sync_percentage']}%")
        
        # Progress bar
        st.progress(sync_status["sync_percentage"] / 100)
        
        st.write(f"**Total leads:** {sync_status['total_leads']}")
        st.write(f"**Sincronizados:** {sync_status['synced_to_hubspot']}")
        st.write(f"**Pendientes:** {sync_status['pending_sync']}")
    
    with col2:
        st.subheader("Acciones")
        
        if st.button("🔄 Sincronización Masiva", use_container_width=True):
            with st.spinner("Iniciando sincronización masiva..."):
                result = backend.trigger_bulk_sync()
                st.success(result["message"])
                time.sleep(2)
                st.rerun()
        
        if st.button("📊 Crear Oportunidad", use_container_width=True):
            with st.form("create_deal"):
                deal_name = st.text_input("Nombre de la oportunidad", "Oportunidad Demo")
                amount = st.number_input("Monto", min_value=0, value=10000)
                stage = st.selectbox("Etapa", ["qualifiedtobuy", "decisionmakerboughtin", "contractsent", "closedwon"])
                
                if st.form_submit_button("Crear Oportunidad"):
                    deal_data = {
                        "deal_name": deal_name,
                        "amount": amount,
                        "stage": stage
                    }
                    
                    # Usar el primer lead disponible o demo
                    leads_data = backend.get_all_leads()
                    lead_id = leads_data["leads"][0]["id"] if leads_data["leads"] else 1000
                    
                    result = backend.create_hubspot_deal(lead_id, deal_data)
                    st.success(result["message"])
                    st.info(f"ID de oportunidad: {result['deal_id']}")

def render_config():
    """Configuración"""
    st.title("⚙️ Configuración")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Configuración General")
        
        st.selectbox("Tema", ["Claro", "Oscuro"], key="theme")
        st.selectbox("Idioma", ["Español", "Inglés"], key="language")
        st.slider("Intervalo de actualización (segundos)", 10, 300, 30, key="refresh")
        
        st.text_input("URL de FastAPI", "http://localhost:8000", key="api_url")
        st.text_input("Token de HubSpot", "demo-token-********", type="password")
    
    with col2:
        st.subheader("Automatización")
        
        st.number_input("Timeout máximo (segundos)", 10, 120, 30, key="timeout")
        st.number_input("Máximo de reintentos", 1, 10, 3, key="retries")
        st.checkbox("Modo headless", True, key="headless")
        st.checkbox("Notificaciones", True, key="notifications")
        
        st.markdown("---")
        if st.button("💾 Guardar Configuración", use_container_width=True):
            st.success("Configuración guardada exitosamente")

# =============================================================================
# APLICACIÓN PRINCIPAL
# =============================================================================
def main():
    """Función principal de la aplicación"""
    
    # Barra lateral
    current_page = render_sidebar()
    
    # Navegación de páginas
    if current_page == "📊 Dashboard":
        render_dashboard()
    elif current_page == "👥 Gestión de Leads":
        render_lead_management()
    elif current_page == "💬 Chat con Leads":
        render_chat()
    elif current_page == "🔄 Sincronización":
        render_sync()
    elif current_page == "⚙️ Configuración":
        render_config()

if __name__ == "__main__":
    main()