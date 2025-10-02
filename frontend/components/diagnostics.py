# components/diagnostics.py
import streamlit as st
import os
import requests
from pathlib import Path

def render_diagnostics_panel(automation_bot):
    """Panel de diagnóstico para la integración"""
    st.header("🔧 Diagnóstico del Sistema")
    
    connection_status = automation_bot.get_connection_status()
    
    # Estado general
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Estado de Conexión")
        if connection_status["is_connected"]:
            st.success("✅ BACKEND FASTAPI CONECTADO")
            st.metric("Tipo de Backend", connection_status["backend_type"])
            st.metric("URL", connection_status["base_url"])
        else:
            st.error("❌ BACKEND NO CONECTADO")
            st.metric("Tipo de Backend", connection_status["backend_type"])
            st.metric("URL", connection_status["base_url"])
    
    with col2:
        st.subheader("Archivos del Sistema")
        automation_files = find_automation_files()
        st.metric("Archivos .py Encontrados", len(automation_files))
        st.metric("Backend Disponible", "FastAPI" if is_fastapi_available() else "No")
    
    # Archivos detectados
    with st.expander("📁 Estructura del Proyecto", expanded=True):
        if automation_files:
            st.success("✅ Archivos de automatización detectados:")
            for file in sorted(automation_files):
                st.write(f"📄 `{file}`")
        else:
            st.error("❌ No se encontraron archivos de automatización")
    
    # Pruebas de conexión
    st.subheader("🧪 Pruebas de Conexión")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Probar Conexión", use_container_width=True):
            test_connection(automation_bot)
    
    with col2:
        if st.button("📋 Ver Logs", use_container_width=True):
            show_connection_logs()
    
    with col3:
        if st.button("🔍 Escanear APIs", use_container_width=True):
            scan_available_apis()
    
    # Información del sistema
    st.subheader("💻 Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Variables de Entorno:**")
        env_vars = {
            "Python Path": os.environ.get('PYTHONPATH', 'No configurado'),
            "Directorio Actual": os.getcwd(),
            "Usuario": os.environ.get('USER', os.environ.get('USERNAME', 'Desconocido'))
        }
        for key, value in env_vars.items():
            st.write(f"- **{key}:** `{value}`")
    
    with col2:
        st.write("**Rutas Importantes:**")
        important_paths = [
            "./core", "./components", "./config", 
            "./data", "./logs", "./static"
        ]
        for path in important_paths:
            exists = "✅" if os.path.exists(path) else "❌"
            st.write(f"- {exists} `{path}`")

def find_automation_files():
    """Encontrar archivos de automatización en el proyecto"""
    automation_files = []
    
    # Buscar archivos .py en el directorio raíz
    python_files = list(Path('.').glob('*.py'))
    for file in python_files:
        if file.name not in ['app.py', 'run_dashboard.py']:
            automation_files.append(file.name)
    
    # Buscar en subdirectorios importantes
    for subdir in ['core', 'components', 'utils', 'services']:
        if os.path.exists(subdir):
            subdir_files = list(Path(subdir).glob('*.py'))
            automation_files.extend([f"{subdir}/{f.name}" for f in subdir_files])
    
    return automation_files

def is_fastapi_available():
    """Verificar si FastAPI está disponible"""
    try:
        response = requests.get('http://localhost:8000/health', timeout=3)
        return response.status_code == 200
    except:
        return False

def test_connection(automation_bot):
    """Probar conexión con el backend"""
    try:
        status = automation_bot.get_connection_status()
        
        if status["is_connected"]:
            st.success("✅ Conexión exitosa con el backend FastAPI")
            
            # Probar endpoints específicos
            from core.fastapi_client import FastAPIClient
            client = FastAPIClient()
            
            # Probar health endpoint
            try:
                health_response = requests.get(f"{status['base_url']}/health", timeout=5)
                if health_response.status_code == 200:
                    st.success("✅ Endpoint /health: Funcionando")
                else:
                    st.error(f"❌ Endpoint /health: Error {health_response.status_code}")
            except Exception as e:
                st.error(f"❌ Endpoint /health: {e}")
            
            # Probar analytics endpoint
            try:
                analytics = client.get_dashboard_analytics()
                if analytics:
                    st.success("✅ Endpoint /dashboard/analytics: Funcionando")
                else:
                    st.warning("⚠️ Endpoint /dashboard/analytics: Sin datos")
            except Exception as e:
                st.error(f"❌ Endpoint /dashboard/analytics: {e}")
                
        else:
            st.error("❌ No hay conexión con el backend")
            
    except Exception as e:
        st.error(f"❌ Error en prueba de conexión: {e}")

def show_connection_logs():
    """Mostrar logs de conexión"""
    try:
        log_files = [
            'logs/fastapi_client.log',
            'logs/automation_bot.log',
            'logs/dashboard.log'
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                st.subheader(f"📝 {log_file}")
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Mostrar últimas 20 líneas
                    for line in lines[-20:]:
                        st.text(line.strip())
                st.markdown("---")
            else:
                st.info(f"Archivo de log no encontrado: {log_file}")
    except Exception as e:
        st.error(f"Error leyendo logs: {e}")

def scan_available_apis():
    """Escanear APIs disponibles"""
    st.subheader("🔍 Escaneo de APIs")
    
    apis_to_scan = [
        ("Backend FastAPI", "http://localhost:8000"),
        ("Health Check", "http://localhost:8000/health"),
        ("Docs API", "http://localhost:8000/docs"),
        ("Dashboard Analytics", "http://localhost:8000/dashboard/analytics"),
    ]
    
    for api_name, api_url in apis_to_scan:
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                st.success(f"✅ {api_name}: `{api_url}`")
            else:
                st.warning(f"⚠️ {api_name}: `{api_url}` (Código: {response.status_code})")
        except Exception as e:
            st.error(f"❌ {api_name}: `{api_url}` - {e}")