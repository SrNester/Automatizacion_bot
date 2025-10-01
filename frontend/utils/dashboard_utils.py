import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import streamlit as st
import os
from pathlib import Path

def setup_logging():
    """Configurar sistema de logging para el dashboard"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/dashboard.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def validate_credentials(platform: str, username: str, password: str) -> bool:
    """Validar credenciales básicas"""
    if not username or not password:
        return False
    if len(username) < 3 or len(password) < 6:
        return False
    return True

def generate_report(session_data: Dict[str, Any]) -> str:
    """Generar reporte de sesión en formato legible"""
    return f"""
    Reporte de Automatización - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    =============================================
    Plataforma: {session_data.get('platform', 'N/A')}
    Acción: {session_data.get('action', 'N/A')}
    Estado: {session_data.get('status', 'N/A')}
    Productos procesados: {session_data.get('products_processed', 0)}
    Duración: {session_data.get('duration', 0):.2f} segundos
    Errores: {session_data.get('errors', 0)}
    =============================================
    """

def format_duration(seconds: float) -> str:
    """Formatear duración en segundos a formato legible"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def format_number(number: int) -> str:
    """Formatear número para visualización"""
    if number >= 1_000_000:
        return f"{number/1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number/1_000:.1f}K"
    else:
        return str(number)

def get_color_by_status(status: str) -> str:
    """Obtener color basado en estado"""
    colors = {
        "completed": "#28a745",
        "failed": "#dc3545",
        "running": "#17a2b8", 
        "pending": "#ffc107",
        "cancelled": "#6c757d"
    }
    return colors.get(status, "#6c757d")

def create_sample_data() -> Dict[str, Any]:
    """Crear datos de ejemplo para demo"""
    return {
        "sessions": [
            {
                "id": 1,
                "session_id": "SESSION_0001",
                "platform": "Mercado Libre",
                "action": "Monitorear Precios",
                "status": "completed",
                "products_processed": 25,
                "duration": 45.2,
                "errors": 0,
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()
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
                "timestamp": (datetime.now() - timedelta(hours=4)).isoformat()
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
                "timestamp": (datetime.now() - timedelta(hours=6)).isoformat()
            }
        ],
        "metrics": {
            "total_sessions": 156,
            "success_rate": 92.5,
            "total_products": 2845,
            "avg_duration": 38.2,
            "sessions_today": 15
        }
    }

def export_to_excel(data: Dict[str, Any], filename: str) -> bool:
    """Exportar datos a archivo Excel"""
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Exportar sesiones
            if 'sessions' in data:
                df_sessions = pd.DataFrame(data['sessions'])
                df_sessions.to_excel(writer, sheet_name='Sesiones', index=False)
            
            # Exportar métricas
            if 'metrics' in data:
                df_metrics = pd.DataFrame([data['metrics']])
                df_metrics.to_excel(writer, sheet_name='Métricas', index=False)
        
        return True
    except Exception as e:
        st.error(f"Error exportando a Excel: {e}")
        return False

def load_config_file(file_path: str) -> Dict[str, Any]:
    """Cargar archivo de configuración"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_config_file(file_path: str, config: Dict[str, Any]):
    """Guardar archivo de configuración"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error guardando configuración: {e}")
        return False

def calculate_efficiency(products_processed: int, duration: float, errors: int) -> float:
    """Calcular eficiencia de sesión"""
    if products_processed == 0:
        return 0
    
    accuracy = (products_processed - errors) / products_processed * 100
    speed = min(products_processed / duration * 10, 100)  # Normalizar velocidad
    
    return (accuracy + speed) / 2

def get_platform_icon(platform: str) -> str:
    """Obtener icono para plataforma"""
    icons = {
        "Mercado Libre": "🟡",
        "Amazon": "📦", 
        "Shopify": "🛍️",
        "Woocommerce": "🔵",
        "Aliexpress": "🚢"
    }
    return icons.get(platform, "🌐")

def get_action_icon(action: str) -> str:
    """Obtener icono para acción"""
    icons = {
        "Monitorear Precios": "💰",
        "Actualizar Inventario": "📊",
        "Buscar Productos": "🔍",
        "Analizar Competencia": "📈",
        "Extraer Reviews": "⭐",
        "Procesar Pedidos": "📦",
        "Actualizar Listados": "🔄"
    }
    return icons.get(action, "🎯")

def validate_email(email: str) -> bool:
    """Validar formato de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def send_notification(title: str, message: str, notification_type: str = "info"):
    """Enviar notificación al usuario"""
    if notification_type == "success":
        st.success(f"✅ {title}: {message}")
    elif notification_type == "error":
        st.error(f"❌ {title}: {message}")
    elif notification_type == "warning":
        st.warning(f"⚠️ {title}: {message}")
    else:
        st.info(f"ℹ️ {title}: {message}")

def backup_data(backup_dir: str = "backups") -> str:
    """Crear backup de datos"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(backup_dir) / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Copiar archivos de datos
        data_files = ["data/sessions.json", "data/user_preferences.json", "data/products_data.json"]
        config_files = ["config/dashboard_config.json", "config/platforms_config.json", "config/automation_settings.json"]
        
        for file_list, file_type in [(data_files, "data"), (config_files, "config")]:
            for file_path in file_list:
                if os.path.exists(file_path):
                    dest_path = backup_path / file_type / Path(file_path).name
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    import shutil
                    shutil.copy2(file_path, dest_path)
        
        return f"Backup creado en: {backup_path}"
    
    except Exception as e:
        return f"Error creando backup: {e}"

def restore_data(backup_path: str) -> bool:
    """Restaurar datos desde backup"""
    try:
        if not os.path.exists(backup_path):
            return False
        
        # Restaurar archivos
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                source_path = Path(root) / file
                relative_path = source_path.relative_to(backup_path)
                dest_path = Path.cwd() / relative_path
                
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(source_path, dest_path)
        
        return True
    
    except Exception as e:
        st.error(f"Error restaurando backup: {e}")
        return False

def get_system_info() -> Dict[str, Any]:
    """Obtener información del sistema"""
    import platform
    import psutil
    
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    }

def format_bytes(size: float) -> str:
    """Formatear bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def create_chart_data(timeframe: str = "7d") -> Dict[str, Any]:
    """Crear datos para gráficos basados en timeframe"""
    now = datetime.now()
    
    if timeframe == "24h":
        dates = [now - timedelta(hours=i) for i in range(23, -1, -1)]
        date_format = "%H:%M"
    elif timeframe == "7d":
        dates = [now - timedelta(days=i) for i in range(6, -1, -1)]
        date_format = "%a"
    elif timeframe == "30d":
        dates = [now - timedelta(days=i) for i in range(29, -1, -1)]
        date_format = "%d/%m"
    else:  # 12m
        dates = [now - timedelta(days=30*i) for i in range(11, -1, -1)]
        date_format = "%b"
    
    # Datos de ejemplo
    sessions = [max(10, min(25, 15 + i)) for i in range(len(dates))]
    success_rates = [max(85, min(98, 90 + i)) for i in range(len(dates))]
    
    return {
        "dates": [date.strftime(date_format) for date in dates],
        "sessions": sessions,
        "success_rates": success_rates
    }

def calculate_roi(investment: float, return_value: float) -> Dict[str, Any]:
    """Calcular ROI"""
    if investment == 0:
        return {"roi": 0, "percentage": "0%", "net_gain": return_value}
    
    roi = (return_value - investment) / investment * 100
    net_gain = return_value - investment
    
    return {
        "roi": roi,
        "percentage": f"{roi:.1f}%",
        "net_gain": net_gain,
        "is_profitable": net_gain > 0
    }