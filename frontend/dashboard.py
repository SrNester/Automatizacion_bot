# run_dashboard.py - VERSIÓN ACTUALIZADA
import os
import sys
import subprocess
import webbrowser
import time
import json
from pathlib import Path

def check_python_version():
    """Verificar versión de Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Se requiere Python 3.8 o superior")
        print(f"   Versión actual: {sys.version}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True

def create_directory_structure():
    """Crear estructura completa de directorios"""
    print("\n📁 Creando estructura de directorios...")
    
    directories = [
        'config',
        'components', 
        'core',
        'utils',
        'data',
        'logs',
        'static/css',
        'static/images',
        'static/js',
        'tests',
        'exports',
        'backups'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {directory}/")

def create_default_configs():
    """Crear archivos de configuración por defecto"""
    print("\n⚙️ Creando configuraciones por defecto...")
    
    # Configuración del dashboard
    dashboard_config = {
        "ui": {
            "theme": "light",
            "language": "es",
            "refresh_interval": 30,
            "default_view": "dashboard"
        },
        "automation": {
            "default_timeout": 30,
            "max_retries": 3,
            "headless_mode": True,
            "screenshot_on_error": True,
            "notifications": True
        },
        "backend": {
            "fastapi_url": "http://localhost:8000",
            "timeout": 10,
            "auto_retry": True
        },
        "performance": {
            "max_concurrent_sessions": 5,
            "session_timeout": 3600,
            "data_retention_days": 30
        }
    }
    
    config_files = {
        'config/dashboard_config.json': dashboard_config,
        'data/sessions.json': [],
        'data/user_preferences.json': {
            "notifications": True,
            "auto_save": True,
            "default_platform": "Sales Automation",
            "timezone": "America/Mexico_City"
        }
    }
    
    for file_path, config in config_files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"   ✅ {file_path}")

def check_backend_availability():
    """Verificar disponibilidad del backend FastAPI"""
    print("\n🔗 Verificando backend FastAPI...")
    
    try:
        import requests
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend FastAPI detectado y funcionando")
            return True
        else:
            print(f"   ⚠️ Backend respondió con código: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Backend FastAPI no disponible")
        print("   💡 Ejecuta: python main.py (en tu proyecto FastAPI)")
        return False
    except Exception as e:
        print(f"   ⚠️ Error verificando backend: {e}")
        return False

def install_dependencies():
    """Instalar dependencias requeridas"""
    print("\n📦 Instalando dependencias...")
    
    try:
        # Verificar si requirements existe
        if not os.path.exists('requirements_frontend.txt'):
            print("   ❌ requirements_frontend.txt no encontrado")
            return False
        
        # Instalar dependencias
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements_frontend.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Dependencias instaladas exitosamente")
            return True
        else:
            print(f"   ❌ Error instalando dependencias: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error durante instalación: {e}")
        return False

def setup_environment():
    """Configurar el entorno completo"""
    print("🚀 CONFIGURACIÓN DEL SALES AUTOMATION DASHBOARD")
    print("=" * 60)
    
    # Verificar Python
    if not check_python_version():
        return False
    
    # Crear directorios
    create_directory_structure()
    
    # Crear configuraciones
    create_default_configs()
    
    # Verificar backend
    backend_available = check_backend_availability()
    
    if not backend_available:
        print("\n⚠️  El backend FastAPI no está disponible")
        print("   El dashboard funcionará en modo demostración")
    
    # Instalar dependencias
    if not install_dependencies():
        print("\n⚠️  Algunas dependencias fallaron. Continuando...")
    
    return True

def start_dashboard():
    """Iniciar el dashboard de Streamlit"""
    print("\n🌐 INICIANDO DASHBOARD...")
    print("=" * 60)
    
    # Información para el usuario
    print("""
    📍 El dashboard estará disponible en:
       http://localhost:8501
    
    🔗 Estado del Backend:
       - FastAPI: {} 
    
    ⚠️  IMPORTANTE:
       - Mantén esta terminal abierta
       - Presiona Ctrl+C para detener el servidor
       - La página se abrirá automáticamente en tu navegador
    
    🕐 Iniciando en 3 segundos...
    """.format("✅ Conectado" if check_backend_availability() else "❌ No conectado"))
    
    # Esperar antes de abrir navegador
    time.sleep(3)
    
    # Abrir navegador automáticamente
    try:
        webbrowser.open("http://localhost:8501")
    except Exception as e:
        print(f"   ⚠️  No se pudo abrir el navegador automáticamente: {e}")
        print("   📱 Por favor abre manualmente: http://localhost:8501")
    
    # Ejecutar Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port=8501", 
            "--server.address=localhost",
            "--browser.serverAddress=localhost",
            "--server.headless=true",
            "--theme.primaryColor=#1f77b4",
            "--theme.backgroundColor=#ffffff",
            "--theme.secondaryBackgroundColor=#f0f2f6",
            "--theme.textColor=#31333f"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Dashboard detenido por el usuario")
    except Exception as e:
        print(f"❌ Error al iniciar el dashboard: {e}")
        return False
    
    return True

def main():
    """Función principal"""
    try:
        # Configurar entorno
        if not setup_environment():
            print("\n❌ La configuración falló. Por favor revisa los errores.")
            return
        
        # Iniciar dashboard
        start_dashboard()
        
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")
        print("\n🔧 Solución de problemas:")
        print("   1. Verifica que Python 3.8+ esté instalado")
        print("   2. Asegúrate de tener permisos de escritura")
        print("   3. Para backend real: ejecuta tu FastAPI en puerto 8000")
        print("   4. Ejecuta como administrador si es necesario")

if __name__ == "__main__":
    main()