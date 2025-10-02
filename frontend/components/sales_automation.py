# components/sales_automation.py - VERSIÓN COMPLETA
import streamlit as st
import pandas as pd
import json
from datetime import datetime

def render_sales_automation(automation_bot, session_manager):
    """Componente específico para automatización de ventas"""
    
    st.header("🤖 Automatización de Ventas")
    
    # Estado de conexión
    connection_status = automation_bot.get_connection_status()
    
    if connection_status["is_connected"]:
        st.success(f"✅ Conectado a: {connection_status['base_url']}")
        
        # Mostrar endpoints disponibles
        with st.expander("🔗 Endpoints Disponibles", expanded=False):
            for endpoint in connection_status["available_endpoints"]:
                st.write(f"🌐 `{endpoint}`")
    else:
        st.error(f"❌ No conectado a: {connection_status['base_url']}")
        st.info("""
        💡 **Para conectar el backend:**
        1. Asegúrate de que tu servidor FastAPI esté ejecutándose
        2. Verifica que esté en `http://localhost:8000`
        3. Ejecuta: `python backend_fix.py` en el directorio principal
        """)
    
    # Pestañas para diferentes funcionalidades
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard", "👥 Capturar Leads", "💬 Chat IA", "🔄 HubSpot", "🎯 Oportunidades", "📈 Analytics"
    ])
    
    with tab1:
        render_sales_dashboard(automation_bot, connection_status)
    
    with tab2:
        render_lead_capture(automation_bot, session_manager, connection_status)
    
    with tab3:
        render_chat_interface(automation_bot, session_manager, connection_status)
    
    with tab4:
        render_hubspot_integration(automation_bot, session_manager, connection_status)
    
    with tab5:
        render_opportunity_management(automation_bot, session_manager, connection_status)
    
    with tab6:
        render_sales_analytics(automation_bot, session_manager, connection_status)

def render_sales_dashboard(automation_bot, connection_status):
    """Dashboard de ventas en tiempo real"""
    st.subheader("📊 Dashboard de Ventas")
    
    # Indicador de modo
    if connection_status.get("mode") == "demo":
        st.info("📱 **Modo Demostración**: Mostrando datos de ejemplo")
    
    # Obtener analytics
    try:
        from core.fastapi_client import FastAPIClient
        api_client = FastAPIClient()
        
        with st.spinner("Cargando analytics..."):
            analytics = api_client.get_dashboard_analytics()
        
        # Mostrar métricas clave
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            delta = analytics["total_leads"] - 40 if analytics["total_leads"] > 40 else None
            st.metric("Total Leads", analytics["total_leads"], delta=delta)
        
        with col2:
            delta = analytics["hot_leads"] - 8 if analytics["hot_leads"] > 8 else None
            st.metric("Hot Leads", analytics["hot_leads"], delta=delta)
        
        with col3:
            delta = f"+{analytics['conversion_rate'] - 12.0:.1f}%" if analytics['conversion_rate'] > 12.0 else None
            st.metric("Tasa Conversión", f"{analytics['conversion_rate']:.1f}%", delta=delta)
        
        with col4:
            delta = analytics['average_score'] - 65 if analytics['average_score'] > 65 else None
            st.metric("Score Promedio", f"{analytics['average_score']:.0f}", delta=delta)
        
        # Fuentes de leads
        if analytics.get("top_sources"):
            st.subheader("🔝 Fuentes de Leads")
            sources_data = []
            for source in analytics["top_sources"][:5]:
                sources_data.append({
                    "Fuente": source.get('source', 'N/A'),
                    "Cantidad": source.get('count', 0),
                    "Porcentaje": f"{(source.get('count', 0) / analytics['total_leads'] * 100):.1f}%"
                })
            
            if sources_data:
                sources_df = pd.DataFrame(sources_data)
                st.dataframe(sources_df, use_container_width=True, hide_index=True)
        
        # Indicador de datos reales vs demo
        if analytics.get("is_fallback"):
            st.caption("🎯 **Datos de demostración** - Conecta el backend para datos en tiempo real")
        else:
            st.caption("✅ **Datos en tiempo real** del backend")
            
    except Exception as e:
        st.error(f"Error cargando dashboard: {e}")

def render_lead_capture(automation_bot, session_manager, connection_status):
    """Captura de nuevos leads"""
    st.subheader("👥 Capturar Nuevo Lead")
    
    with st.form("lead_capture_form"):
        st.write("Complete la información del lead:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Nombre completo*", placeholder="Juan Pérez")
            email = st.text_input("Email*", placeholder="juan@empresa.com")
            company = st.text_input("Empresa", placeholder="Mi Empresa SA")
        
        with col2:
            phone = st.text_input("Teléfono", placeholder="+1234567890")
            source = st.selectbox("Fuente", [
                "website", "referral", "social_media", "event", "cold_call", "dashboard", "other"
            ])
            tags = st.text_input("Etiquetas (separar por coma)", placeholder="potencial,tech,b2b")
        
        metadata = st.text_area("Metadatos adicionales (JSON)", 
                               placeholder='{"interes": "software", "tamaño_empresa": "mediana"}',
                               height=100)
        
        submitted = st.form_submit_button("🎯 Capturar Lead", use_container_width=True)
        
        if submitted:
            if not name or not email:
                st.error("❌ Nombre y email son requeridos")
                return
            
            # Preparar datos del lead
            lead_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
                "source": source,
                "tags": [tag.strip() for tag in tags.split(",")] if tags else [],
            }
            
            if metadata:
                try:
                    lead_data["metadata"] = json.loads(metadata)
                except:
                    lead_data["metadata"] = {"raw_metadata": metadata}
            
            # Ejecutar captura
            config = {
                "platform": "Sales Automation",
                "action": "Capturar Lead",
                **lead_data
            }
            
            execute_sales_automation(automation_bot, session_manager, config, connection_status)

def render_chat_interface(automation_bot, session_manager, connection_status):
    """Interfaz de chat con IA"""
    st.subheader("💬 Asistente IA para Leads")
    
    # Seleccionar lead
    col1, col2 = st.columns([2, 1])
    
    with col1:
        lead_id = st.number_input("ID del Lead", min_value=1, value=1, 
                                 help="ID del lead existente en la base de datos")
    
    with col2:
        if st.button("🔍 Cargar Lead", use_container_width=True):
            try:
                from core.fastapi_client import FastAPIClient
                api_client = FastAPIClient()
                lead_info = api_client.get_lead_details(lead_id)
                
                if lead_info and lead_info.get('lead'):
                    st.success(f"✅ Lead encontrado: {lead_info['lead']['name']}")
                    
                    with st.expander("📋 Ver detalles del lead", expanded=False):
                        st.json(lead_info)
                else:
                    st.warning("⚠️ Lead no encontrado")
            except Exception as e:
                st.error(f"❌ Error cargando lead: {e}")
    
    # Historial de conversación (simulado)
    st.subheader("💭 Conversación")
    
    # Mostrar historial de conversación si existe
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Mostrar mensajes anteriores
    for msg in st.session_state.chat_history[-5:]:  # Mostrar últimos 5 mensajes
        if msg['type'] == 'user':
            st.markdown(f"**Tú:** {msg['message']}")
        else:
            st.markdown(f"**Asistente:** {msg['message']}")
    
    # Área de mensajes
    message = st.text_area("Escribe tu mensaje...", 
                          placeholder="Hola, me gustaría saber más sobre sus servicios...",
                          height=100,
                          key="chat_message")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🚀 Enviar Mensaje", use_container_width=True):
            if not message:
                st.error("❌ Por favor ingresa un mensaje")
                return
            
            # Agregar mensaje al historial
            st.session_state.chat_history.append({
                'type': 'user',
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
            config = {
                "platform": "Sales Automation", 
                "action": "Chat con Lead",
                "lead_id": lead_id,
                "message": message
            }
            
            execute_sales_automation(automation_bot, session_manager, config, connection_status)

def render_hubspot_integration(automation_bot, session_manager, connection_status):
    """Integración con HubSpot"""
    st.subheader("🔄 Integración HubSpot")
    
    # Estado de sincronización
    try:
        from core.fastapi_client import FastAPIClient
        api_client = FastAPIClient()
        
        with st.spinner("Cargando estado de sincronización..."):
            sync_status = api_client.get_hubspot_sync_status()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Leads", sync_status["total_leads"])
        
        with col2:
            st.metric("Sincronizados", sync_status["synced_to_hubspot"])
        
        with col3:
            st.metric("Pendientes", sync_status["pending_sync"])
        
        with col4:
            st.metric("Porcentaje", f"{sync_status['sync_percentage']}%")
        
        # Configuración de HubSpot
        st.subheader("⚙️ Configuración")
        st.write(f"HubSpot Configurado: **{'✅ Sí' if sync_status['hubspot_configured'] else '❌ No'}**")
        
        # Acciones de sincronización
        st.subheader("🚀 Acciones")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Sincronización Individual**")
            sync_lead_id = st.number_input("ID Lead para sync", min_value=1, value=1, key="sync_lead")
            
            if st.button("🔄 Sincronizar Lead", use_container_width=True, key="sync_single"):
                config = {
                    "platform": "Sales Automation",
                    "action": "Sincronizar HubSpot", 
                    "lead_id": sync_lead_id
                }
                execute_sales_automation(automation_bot, session_manager, config, connection_status)
        
        with col2:
            st.write("**Sincronización Masiva**")
            st.info("Sincronizar todos los leads pendientes")
            
            if st.button("⚡ Sincronización Masiva", use_container_width=True, key="sync_bulk"):
                config = {
                    "platform": "Sales Automation",
                    "action": "Sincronizar HubSpot"
                    # Sin lead_id = sincronización masiva
                }
                execute_sales_automation(automation_bot, session_manager, config, connection_status)
                
    except Exception as e:
        st.error(f"❌ Error cargando estado HubSpot: {e}")
        st.info("⚠️ Mostrando datos de demostración")
        
        # Datos de demostración
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Total Leads", 45)
        with col2: st.metric("Sincronizados", 32)
        with col3: st.metric("Pendientes", 13)
        with col4: st.metric("Porcentaje", "71.1%")

def render_opportunity_management(automation_bot, session_manager, connection_status):
    """Gestión de oportunidades"""
    st.subheader("🎯 Gestión de Oportunidades")
    
    with st.form("opportunity_form"):
        st.write("Crear nueva oportunidad en HubSpot:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            lead_id = st.number_input("ID del Lead", min_value=1, value=1, key="deal_lead")
            deal_name = st.text_input("Nombre de la Oportunidad*", placeholder="Venta de Software Empresarial")
            amount = st.number_input("Monto", min_value=0, value=5000)
        
        with col2:
            stage = st.selectbox("Etapa", [
                "appointmentscheduled",
                "qualifiedtobuy", 
                "presentationscheduled",
                "decisionmakerboughtin",
                "contractsent",
                "closedwon",
                "closedlost"
            ])
            priority = st.selectbox("Prioridad", ["low", "medium", "high"])
            close_date = st.date_input("Fecha de cierre estimada")
        
        if st.form_submit_button("💰 Crear Oportunidad", use_container_width=True):
            if not deal_name:
                st.error("❌ El nombre de la oportunidad es requerido")
                return
            
            config = {
                "platform": "Sales Automation",
                "action": "Crear Oportunidad",
                "lead_id": lead_id,
                "deal_name": deal_name,
                "amount": amount,
                "stage": stage,
                "priority": priority,
                "close_date": close_date.isoformat()
            }
            
            execute_sales_automation(automation_bot, session_manager, config, connection_status)

def render_sales_analytics(automation_bot, session_manager, connection_status):
    """Analytics avanzados"""
    st.subheader("📈 Analytics Avanzados")
    
    if st.button("🔄 Actualizar Analytics", use_container_width=True, key="refresh_analytics"):
        config = {
            "platform": "Sales Automation",
            "action": "Analizar Leads"
        }
        execute_sales_automation(automation_bot, session_manager, config, connection_status)
    
    # Métricas avanzadas
    st.subheader("📊 Métricas de Rendimiento")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Tiempo Respuesta Promedio", "2.3h")
        st.metric("Tasa de Engagement", "34%")
    
    with col2:
        st.metric("Costo por Lead", "₡1,250")
        st.metric("LTV Promedio", "₡45,000")
    
    with col3:
        st.metric("Satisfacción Cliente", "4.5/5")
        st.metric("Tasa de Retención", "78%")
    
    # Análisis predictivo
    st.subheader("🔮 Análisis Predictivo")
    
    with st.expander("📈 Proyección de Ventas", expanded=True):
        st.info("""
        **Próximos 30 días:**
        - Leads esperados: **45-55**
        - Conversiones estimadas: **8-12** 
        - Ingreso proyectado: **₡350,000 - ₡450,000**
        - Leads calientes: **15-20**
        """)
    
    with st.expander("🎯 Recomendaciones", expanded=True):
        st.success("""
        **Recomendaciones basadas en datos:**
        - 🎯 Enfocar esfuerzos en leads de **website** (mayor conversión)
        - 💬 Mejorar tiempos de respuesta en **chat** (actual: 2.3h)
        - 🔄 Automatizar nurturing para leads con **score 50-70**
        - 📧 Implementar secuencia de emails para leads **inactivos 7+ días**
        """)

def execute_sales_automation(automation_bot, session_manager, config, connection_status=None):
    """Ejecutar automatización de ventas"""
    try:
        with st.spinner(f"Ejecutando {config['action']}..."):
            result = automation_bot.execute_automation(config)
        
        if result["success"]:
            st.success(f"✅ {result['message']}")
            
            # Mostrar detalles específicos para cada acción
            if result.get('lead_id'):
                st.info(f"📋 ID Lead asignado: **{result['lead_id']}**")
            
            if result.get('score'):
                st.info(f"🎯 Score del lead: **{result['score']}**")
            
            if result.get('response'):
                st.markdown("---")
                st.subheader("🤖 Respuesta del Asistente IA:")
                st.write(result['response'])
                
                # Agregar respuesta al historial de chat
                if 'chat_history' in st.session_state and config.get('action') == 'Chat con Lead':
                    st.session_state.chat_history.append({
                        'type': 'assistant',
                        'message': result['response'],
                        'timestamp': datetime.now().isoformat()
                    })
            
            if result.get('deal_id'):
                st.info(f"💰 Oportunidad creada: **{result['deal_id']}**")
            
            if result.get('analytics'):
                st.markdown("---")
                st.subheader("📊 Resultados del Análisis:")
                st.json(result['analytics'])
            
            # Indicar si son datos reales o simulados
            if result.get('is_real_data'):
                st.success("🎉 **Datos en tiempo real del backend**")
            else:
                st.warning("⚠️ **Modo demostración - datos simulados**")
            
            # Guardar en sesiones
            session_data = {
                "platform": config["platform"],
                "action": config["action"], 
                "status": "completed",
                "products_processed": result.get("products_processed", 1),
                "duration": result.get("duration", 0),
                "errors": result.get("errors", 0),
                "config": config,
                "is_real_data": result.get("is_real_data", False),
                "timestamp": datetime.now().isoformat()
            }
            session_manager.add_session(session_data)
            
        else:
            st.error(f"❌ {result.get('error', 'Error en la ejecución')}")
            
    except Exception as e:
        st.error(f"💥 Error inesperado: {str(e)}")