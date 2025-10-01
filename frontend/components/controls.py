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
    """Renderizar panel de estado del bot"""
    st.subheader("🤖 Estado del Bot")
    
    # Estado actual
    status = automation_bot.get_status()
    
    # Indicador de estado
    status_color = {
        "running": "🟢",
        "paused": "🟡", 
        "stopped": "🔴",
        "error": "🔴"
    }
    
    st.markdown(
        f"""
        <div style='
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid {"#28a745" if status["state"] == "running" else "#ffc107" if status["state"] == "paused" else "#dc3545"};
            margin-bottom: 1rem;
        '>
            <div style='font-size: 1.2rem; font-weight: bold;'>
                {status_color[status["state"]]} Estado: {status["state"].upper()}
            </div>
            <div style='font-size: 0.9rem; color: #666;'>
                📊 Sesiones activas: {status["active_sessions"]}<br>
                ⏰ Última ejecución: {status["last_execution"]}<br>
                🚦 Próxima ejecución: {status["next_execution"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Controles de estado
    col1, col2 = st.columns(2)
    
    with col1:
        if status["state"] == "running":
            if st.button("⏸️ Pausar", use_container_width=True):
                automation_bot.pause()
                st.success("Bot pausado")
                st.rerun()
        else:
            if st.button("▶️ Reanudar", use_container_width=True):
                automation_bot.resume()
                st.success("Bot reanudado")
                st.rerun()
    
    with col2:
        if st.button("🔄 Reiniciar", use_container_width=True, type="secondary"):
            automation_bot.restart()
            st.success("Bot reiniciado")
            st.rerun()

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
            
            # Simular ejecución (en una app real aquí se llamaría al bot real)
            time.sleep(2)
            
            # Resultado simulado
            result = {
                "success": True,
                "products_processed": 25,
                "duration": 45.2,
                "errors": 0,
                "message": "Automatización completada exitosamente"
            }
            
            if result["success"]:
                # Guardar sesión
                session_data = {
                    "platform": config["platform"],
                    "action": config["action"],
                    "status": "completed",
                    "products_processed": result["products_processed"],
                    "duration": result["duration"],
                    "errors": result["errors"],
                    "config": config
                }
                session_manager.add_session(session_data)
                
                st.success(f"✅ {result['message']}")
                st.balloons()
            else:
                st.error(f"❌ Error en la automatización: {result['message']}")
                
    except Exception as e:
        st.error(f"💥 Error crítico: {str(e)}")

def execute_quick_action(automation_bot, action):
    """Ejecutar acción rápida"""
    action_configs = {
        "quick_monitor": {"action": "Monitorear Precios", "limit": 50},
        "quick_analysis": {"action": "Analizar Competencia", "period": 1},
        "quick_inventory": {"action": "Actualizar Inventario", "sync": True},
        "quick_search": {"action": "Buscar Productos", "limit": 20}
    }
    
    config = action_configs.get(action, {})
    st.info(f"🚀 Ejecutando {config.get('action', 'acción rápida')}...")
    
    # Simular ejecución rápida
    time.sleep(1)
    st.success(f"✅ {config.get('action', 'Acción rápida')} completada")

def save_automation_config(config):
    """Guardar configuración de automatización"""
    try:
        with open('data/automation_presets.json', 'w') as f:
            json.dump(config, f, indent=2)
        st.success("💾 Configuración guardada exitosamente")
    except Exception as e:
        st.error(f"❌ Error guardando configuración: {str(e)}")