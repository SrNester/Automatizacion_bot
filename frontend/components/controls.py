import streamlit as st
import time
import json
from datetime import datetime

def render_controls(automation_bot, session_manager, config_data):
    """Renderizar controles de automatización"""
    st.header("🎮 Control de Automatización")
    
    # Panel de control principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_automation_panel(automation_bot, session_manager, config_data)
    
    with col2:
        render_quick_actions_panel(automation_bot)
        render_bot_status_panel(automation_bot)
    
    # Configuración avanzada
    render_advanced_settings()

def render_automation_panel(automation_bot, session_manager, config_data):
    """Renderizar panel principal de automatización"""
    st.subheader("⚡ Ejecutar Automatización")
    
    with st.form("automation_form"):
        # Configuración básica
        col1, col2 = st.columns(2)
        
        with col1:
            platform = st.selectbox(
                "🌐 Plataforma",
                options=["Mercado Libre", "Amazon", "Shopify", "Woocommerce", "Aliexpress"],
                index=0,
                key="control_platform"
            )
            
            action_type = st.selectbox(
                "🎯 Tipo de Acción",
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
                key="control_action"
            )
        
        with col2:
            execution_mode = st.selectbox(
                "⚡ Modo de Ejecución",
                options=["Normal", "Rápido", "Silencioso", "Debug"],
                index=0,
                key="control_mode"
            )
            
            priority = st.select_slider(
                "🎯 Prioridad",
                options=["Baja", "Media", "Alta", "Crítica"],
                value="Media",
                key="control_priority"
            )
        
        # Configuración específica por acción
        render_action_specific_settings(action_type)
        
        # Programación
        with st.expander("⏰ Programar Ejecución", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                schedule_type = st.radio(
                    "Tipo de programación",
                    ["Ejecución Inmediata", "Programar para más tarde"],
                    horizontal=True
                )
            with col2:
                if schedule_type == "Programar para más tarde":
                    scheduled_time = st.time_input("Hora de ejecución")
                    scheduled_date = st.date_input("Fecha de ejecución")
        
        # Botón de ejecución
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.form_submit_button("🚀 Ejecutar Automatización", type="primary", use_container_width=True):
                execute_automation(automation_bot, session_manager, {
                    "platform": platform,
                    "action": action_type,
                    "mode": execution_mode,
                    "priority": priority,
                    "scheduled": schedule_type == "Programar para más tarde",
                    **config_data
                })
        
        with col2:
            if st.form_submit_button("💾 Guardar Configuración", use_container_width=True):
                save_automation_config({
                    "platform": platform,
                    "action": action_type,
                    "mode": execution_mode,
                    "priority": priority
                })
        
        with col3:
            if st.form_submit_button("🔄 Reiniciar", use_container_width=True, type="secondary"):
                st.rerun()

def render_action_specific_settings(action_type):
    """Renderizar configuraciones específicas por tipo de acción"""
    
    if action_type == "Monitorear Precios":
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("🔍 Límite de productos", min_value=1, max_value=1000, value=100, key="price_limit")
            st.text_input("📌 Palabras clave", placeholder="ej: smartphone, laptop", key="price_keywords")
        with col2:
            st.number_input("💰 Umbral de alerta (%)", min_value=1, max_value=50, value=10, key="price_threshold")
            st.checkbox("📧 Notificar cambios", value=True, key="price_notify")
    
    elif action_type == "Actualizar Inventario":
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("📊 Fuente de inventario", ["API", "Archivo CSV", "Base de datos"], key="inventory_source")
            st.number_input("🔄 Intervalo (minutos)", min_value=5, max_value=1440, value=30, key="inventory_interval")
        with col2:
            st.checkbox("🔄 Sincronizar stock", value=True, key="inventory_sync")
            st.checkbox("📦 Actualizar precios", value=False, key="inventory_prices")
    
    elif action_type == "Buscar Productos":
        col1, col2 = st.columns(2)
        with col1:
            st.text_area("🔍 Términos de búsqueda", placeholder="Ingresa un término por línea", key="search_terms")
            st.number_input("📄 Resultados máximos", min_value=1, max_value=500, value=50, key="search_limit")
        with col2:
            st.multiselect("🏷️ Categorías", ["Electrónicos", "Hogar", "Ropa", "Deportes"], key="search_categories")
            st.checkbox("💾 Guardar resultados", value=True, key="search_save")
    
    elif action_type == "Analizar Competencia":
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("👥 Competidores", placeholder="usuarios o tiendas a analizar", key="competitors")
            st.selectbox("📊 Métrica principal", ["Precios", "Inventario", "Reviews", "Tiempo de envío"], key="competition_metric")
        with col2:
            st.number_input("📈 Período (días)", min_value=1, max_value=30, value=7, key="competition_period")
            st.checkbox("📊 Generar reporte", value=True, key="competition_report")

def render_quick_actions_panel(automation_bot):
    """Renderizar panel de acciones rápidas"""
    st.subheader("🚀 Acciones Rápidas")
    
    quick_actions = [
        {
            "name": "🔄 Monitoreo Rápido",
            "description": "Verificación rápida de precios",
            "action": "quick_monitor",
            "color": "#1f77b4"
        },
        {
            "name": "📊 Análisis Express", 
            "description": "Análisis rápido de competencia",
            "action": "quick_analysis",
            "color": "#ff7f0e"
        },
        {
            "name": "📦 Inventario Flash",
            "description": "Actualización rápida de stock",
            "action": "quick_inventory",
            "color": "#2ca02c"
        },
        {
            "name": "🔍 Búsqueda Instantánea",
            "description": "Búsqueda rápida de productos",
            "action": "quick_search",
            "color": "#d62728"
        }
    ]
    
    for action in quick_actions:
        if st.button(
            action["name"], 
            use_container_width=True,
            key=f"quick_{action['action']}",
            help=action["description"]
        ):
            execute_quick_action(automation_bot, action["action"])

def render_bot_status_panel(automation_bot):
    """Renderizar panel de estado del bot - VERSIÓN CORREGIDA"""
    st.subheader("🤖 Estado del Bot")
    
    try:
        # Obtener estado del bot
        status = automation_bot.get_status()
        
        # Usar las claves correctas del método get_status()
        active_sessions_count = status.get("active_sessions_count", 0)
        scheduled_tasks_count = status.get("scheduled_tasks_count", 0)
        state = status.get("state", "stopped")
        status_message = status.get("status_message", "Estado no disponible")
        last_activity = status.get("last_activity")
        start_time = status.get("start_time")
        
        # Formatear fechas
        last_activity_str = "Nunca"
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                last_activity_str = last_activity_dt.strftime('%H:%M:%S')
            except:
                last_activity_str = "Reciente"
        
        start_time_str = "No iniciado"
        if start_time:
            try:
                start_time_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                start_time_str = start_time_dt.strftime('%H:%M:%S')
            except:
                start_time_str = "Activo"
        
        # Indicador de estado
        status_color = {
            "running": "🟢",
            "paused": "🟡", 
            "stopped": "🔴",
            "error": "🔴"
        }.get(state, "⚪")
        
        st.markdown(
            f"""
            <div style='
                background: #f8f9fa;
                padding: 1rem;
                border-radius: 8px;
                border-left: 4px solid {"#28a745" if state == "running" else "#ffc107" if state == "paused" else "#dc3545"};
                margin-bottom: 1rem;
            '>
                <div style='font-size: 1.2rem; font-weight: bold;'>
                    {status_color} Estado: {state.upper()}
                </div>
                <div style='font-size: 0.9rem; color: #666;'>
                    📊 Sesiones activas: {active_sessions_count}<br>
                    ⏰ Última actividad: {last_activity_str}<br>
                    🚀 Iniciado: {start_time_str}<br>
                    📝 Mensaje: {status_message}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Mostrar información adicional si está disponible
        if status.get('current_platform') or status.get('current_action'):
            with st.expander("📋 Información Detallada"):
                col1, col2 = st.columns(2)
                with col1:
                    if status.get('current_platform'):
                        st.write(f"**Plataforma actual:** {status['current_platform']}")
                    if status.get('current_action'):
                        st.write(f"**Acción actual:** {status['current_action']}")
                    if status.get('progress', 0) > 0:
                        st.write(f"**Progreso:** {status['progress']:.1f}%")
                
                with col2:
                    if status.get('completed_tasks', 0) > 0:
                        st.write(f"**Tareas completadas:** {status['completed_tasks']}")
                    if status.get('failed_tasks', 0) > 0:
                        st.write(f"**Tareas fallidas:** {status['failed_tasks']}")
                    if status.get('uptime', 0) > 0:
                        uptime_minutes = status['uptime'] / 60
                        st.write(f"**Tiempo activo:** {uptime_minutes:.1f} min")
        
        # Controles de estado
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if state != "running":
                if st.button("▶️ Iniciar", use_container_width=True, type="primary"):
                    try:
                        automation_bot.start_automation({"platform": "Dashboard", "action": "Inicio manual"})
                        st.success("Bot iniciado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error iniciando bot: {e}")
            else:
                if st.button("⏸️ Pausar", use_container_width=True):
                    try:
                        automation_bot.pause_automation()
                        st.success("Bot pausado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error pausando bot: {e}")
        
        with col2:
            if state == "paused":
                if st.button("▶️ Reanudar", use_container_width=True):
                    try:
                        automation_bot.resume_automation()
                        st.success("Bot reanudado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error reanudando bot: {e}")
            else:
                if st.button("🔁 Reiniciar", use_container_width=True, type="secondary"):
                    try:
                        automation_bot.stop_automation()
                        time.sleep(0.5)
                        automation_bot.start_automation({"platform": "Dashboard", "action": "Reinicio manual"})
                        st.success("Bot reiniciado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error reiniciando bot: {e}")
        
        with col3:
            if state in ["running", "paused"]:
                if st.button("⏹️ Detener", use_container_width=True, type="secondary"):
                    try:
                        automation_bot.stop_automation()
                        st.success("Bot detenido")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deteniendo bot: {e}")
        
        # Mostrar información de conexión API
        api_status = status.get("api_connection_status", {})
        if api_status:
            with st.expander("🔗 Estado de Conexión API"):
                is_connected = api_status.get("is_connected", False)
                connection_status = "🟢 Conectado" if is_connected else "🔴 Desconectado"
                st.write(f"**Estado:** {connection_status}")
                st.write(f"**Backend:** {api_status.get('backend_type', 'N/A')}")
                st.write(f"**URL:** {api_status.get('base_url', 'N/A')}")
                
    except Exception as e:
        st.error(f"❌ Error obteniendo estado del bot: {str(e)}")
        st.info("El bot puede estar inicializándose o tener problemas de conexión...")

def render_advanced_settings():
    """Renderizar configuraciones avanzadas"""
    with st.expander("🔧 Configuración Avanzada", expanded=False):
        
        tab1, tab2, tab3 = st.tabs(["Navegador", "Rendimiento", "Seguridad"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.selectbox("🌐 Navegador", ["Chrome", "Firefox", "Edge"], key="browser_type")
                st.checkbox("🖥️ Modo headless", value=True, key="headless_mode")
                st.number_input("⏱️ Timeout (segundos)", min_value=10, max_value=300, value=30, key="browser_timeout")
            with col2:
                st.text_input("👤 User Agent", key="user_agent")
                st.checkbox("📸 Capturas de pantalla", value=True, key="screenshots")
                st.checkbox("📝 Logs detallados", value=True, key="detailed_logs")
        
        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("🔄 Reintentos máximos", min_value=0, max_value=10, value=3, key="max_retries")
                st.number_input("⏰ Delay entre acciones (ms)", min_value=0, max_value=5000, value=1000, key="action_delay")
                st.slider("🚀 Velocidad de ejecución", 1, 5, 3, key="execution_speed")
            with col2:
                st.number_input("📊 Límite de productos", min_value=10, max_value=1000, value=100, key="product_limit")
                st.number_input("💾 Tamaño de lote", min_value=1, max_value=100, value=10, key="batch_size")
                st.checkbox("🔄 Ejecución paralela", value=False, key="parallel_execution")
        
        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                st.checkbox("🔒 Validar SSL", value=True, key="ssl_verify")
                st.checkbox("🛡️ Usar proxy", value=False, key="use_proxy")
                st.text_input("🌐 Proxy URL", key="proxy_url", disabled=not st.session_state.get("use_proxy", False))
            with col2:
                st.checkbox("📧 Notificaciones por email", value=False, key="email_notifications")
                st.checkbox("📱 Notificaciones por Telegram", value=False, key="telegram_notifications")
                st.text_input("🔔 Webhook URL", key="webhook_url")

def execute_automation(automation_bot, session_manager, config):
    """Ejecutar automatización"""
    try:
        with st.spinner(f"🚀 Ejecutando {config['action']} en {config['platform']}..."):
            
            # Iniciar el bot si no está corriendo
            if not automation_bot.state == "running":
                automation_bot.start_automation(config)
            
            # Ejecutar la automatización
            result = automation_bot.execute_automation(config)
            
            if result.get("success", False):
                # Guardar sesión
                session_data = {
                    "platform": config["platform"],
                    "action": config["action"],
                    "status": "completed",
                    "products_processed": result.get("products_processed", 0),
                    "duration": result.get("duration", 0),
                    "errors": result.get("errors", 0),
                    "config": config,
                    "message": result.get("message", "Ejecución completada"),
                    "is_real_data": result.get("is_real_data", False)
                }
                session_manager.add_session(session_data)
                
                st.success(f"✅ {result.get('message', 'Automatización completada exitosamente')}")
                if result.get("is_real_data"):
                    st.info("📡 **Datos en tiempo real** desde el backend")
                else:
                    st.warning("🔄 **Datos simulados** - Backend no disponible")
                st.balloons()
            else:
                st.error(f"❌ Error en la automatización: {result.get('message', 'Error desconocido')}")
                
    except Exception as e:
        st.error(f"💥 Error crítico: {str(e)}")

def execute_quick_action(automation_bot, action):
    """Ejecutar acción rápida"""
    action_configs = {
        "quick_monitor": {
            "platform": "Mercado Libre", 
            "action": "Monitorear Precios", 
            "limit": 50
        },
        "quick_analysis": {
            "platform": "Amazon", 
            "action": "Analizar Competencia", 
            "period": 1
        },
        "quick_inventory": {
            "platform": "Shopify", 
            "action": "Actualizar Inventario", 
            "sync": True
        },
        "quick_search": {
            "platform": "Aliexpress", 
            "action": "Buscar Productos", 
            "limit": 20
        }
    }
    
    config = action_configs.get(action, {})
    
    try:
        with st.spinner(f"🚀 Ejecutando {config.get('action', 'acción rápida')}..."):
            # Iniciar bot si es necesario
            if not automation_bot.state == "running":
                automation_bot.start_automation(config)
            
            # Ejecutar acción
            result = automation_bot.execute_automation(config)
            
            if result.get("success", False):
                st.success(f"✅ {config.get('action', 'Acción rápida')} completada")
            else:
                st.error(f"❌ Error en acción rápida: {result.get('message', 'Error desconocido')}")
                
    except Exception as e:
        st.error(f"💥 Error en acción rápida: {str(e)}")

def save_automation_config(config):
    """Guardar configuración de automatización"""
    try:
        with open('data/automation_presets.json', 'w') as f:
            json.dump(config, f, indent=2)
        st.success("💾 Configuración guardada exitosamente")
    except Exception as e:
        st.error(f"❌ Error guardando configuración: {str(e)}")