import json
import os
import streamlit as st
from typing import Dict, Any, Optional
from pathlib import Path
import logging
from datetime import datetime

class ConfigManager:
    def __init__(self):
        self.config_files = {
            'dashboard': 'config/dashboard_config.json',
            'platforms': 'config/platforms_config.json',
            'automation': 'config/automation_settings.json',
            'user_preferences': 'data/user_preferences.json'
        }
        self.logger = self.setup_logger()
        self.load_all_configs()
    
    def setup_logger(self):
        """Configurar logger para ConfigManager"""
        logger = logging.getLogger('ConfigManager')
        if not logger.handlers:
            handler = logging.FileHandler('logs/config_manager.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def load_all_configs(self):
        """Cargar todas las configuraciones"""
        self.configs = {}
        for key, file_path in self.config_files.items():
            self.configs[key] = self.load_config(file_path)
        self.logger.info("Todas las configuraciones cargadas exitosamente")
    
    def load_config(self, file_path: str) -> Dict[str, Any]:
        """Cargar configuración desde archivo"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.debug(f"Configuración cargada: {file_path}")
                return config
            else:
                self.logger.warning(f"Archivo de configuración no encontrado: {file_path}")
                return self.get_default_config(file_path)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decodificando JSON en {file_path}: {e}")
            return self.get_default_config(file_path)
        except Exception as e:
            self.logger.error(f"Error cargando configuración {file_path}: {e}")
            return self.get_default_config(file_path)
    
    def get_default_config(self, file_path: str) -> Dict[str, Any]:
        """Obtener configuración por defecto"""
        if 'dashboard' in file_path:
            return {
                "ui": {
                    "theme": "light",
                    "language": "es",
                    "refresh_interval": 30,
                    "default_view": "dashboard",
                    "animations": True,
                    "compact_mode": False
                },
                "automation": {
                    "default_timeout": 30,
                    "max_retries": 3,
                    "headless_mode": True,
                    "screenshot_on_error": True,
                    "notifications": True,
                    "auto_restart": False
                },
                "performance": {
                    "max_concurrent_sessions": 5,
                    "session_timeout": 3600,
                    "data_retention_days": 30,
                    "cache_enabled": True
                },
                "security": {
                    "encrypt_credentials": True,
                    "session_timeout_minutes": 60,
                    "log_automation_actions": True,
                    "two_factor_auth": False
                }
            }
        elif 'platforms' in file_path:
            return {
                "mercado_libre": {
                    "enabled": True,
                    "timeout": 30,
                    "api_key": "",
                    "api_secret": "",
                    "rate_limit": 10,
                    "auto_login": True,
                    "notifications": True
                },
                "amazon": {
                    "enabled": False,
                    "timeout": 45,
                    "access_key": "",
                    "secret_key": "",
                    "region": "us-east-1",
                    "marketplace": "US",
                    "notifications": True
                },
                "shopify": {
                    "enabled": False,
                    "timeout": 30,
                    "store_url": "",
                    "access_token": "",
                    "api_version": "2024-01",
                    "notifications": True
                },
                "woocommerce": {
                    "enabled": False,
                    "timeout": 30,
                    "store_url": "",
                    "consumer_key": "",
                    "consumer_secret": "",
                    "version": "wc/v3",
                    "notifications": True
                },
                "aliexpress": {
                    "enabled": False,
                    "timeout": 40,
                    "api_key": "",
                    "tracking_enabled": False,
                    "notifications": False
                }
            }
        elif 'automation' in file_path:
            return {
                "browser": {
                    "type": "chrome",
                    "headless": True,
                    "window_size": "1920,1080",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "download_path": "./downloads",
                    "block_images": False
                },
                "actions": {
                    "monitor_prices": {
                        "enabled": True,
                        "interval": 3600,
                        "max_products": 100,
                        "price_threshold": 10,
                        "notify_changes": True
                    },
                    "update_inventory": {
                        "enabled": True,
                        "interval": 1800,
                        "sync_prices": False,
                        "update_descriptions": False
                    },
                    "search_products": {
                        "enabled": True,
                        "max_results": 50,
                        "save_results": True,
                        "categorize_results": True
                    },
                    "analyze_competition": {
                        "enabled": True,
                        "interval": 86400,
                        "track_competitors": 5,
                        "generate_reports": True
                    }
                },
                "notifications": {
                    "email": {
                        "enabled": False,
                        "smtp_server": "",
                        "port": 587,
                        "sender_email": "",
                        "sender_password": "",
                        "recipients": []
                    },
                    "telegram": {
                        "enabled": False,
                        "bot_token": "",
                        "chat_id": "",
                        "notify_errors": True,
                        "notify_success": False
                    },
                    "webhook": {
                        "enabled": False,
                        "url": "",
                        "secret": "",
                        "events": ["error", "completion"]
                    }
                }
            }
        else:
            return {}
    
    def save_config(self, key: str):
        """Guardar configuración en archivo"""
        try:
            file_path = self.config_files.get(key)
            if file_path:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.configs[key], f, indent=2, ensure_ascii=False)
                self.logger.info(f"Configuración guardada: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error guardando configuración {key}: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Obtener estado del sistema"""
        return {
            "status": "online",
            "sessions_today": 15,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resource_usage": 65,
            "active_connections": 3
        }
    
    def get_current_user(self) -> str:
        """Obtener usuario actual"""
        return st.session_state.get('user', 'admin@empresa.com')
    
    def get_current_user_info(self) -> Dict[str, Any]:
        """Obtener información del usuario actual"""
        return {
            "username": self.get_current_user(),
            "role": "Administrador",
            "login_time": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "session_duration": "2h 15m",
            "permissions": ["full_access"]
        }
    
    def render_general_settings(self):
        """Renderizar configuración general en Streamlit"""
        config = self.configs['dashboard']
        
        with st.form("general_settings_form"):
            st.subheader("🎨 Interfaz de Usuario")
            
            col1, col2 = st.columns(2)
            
            with col1:
                theme = st.selectbox(
                    "Tema de la Interfaz",
                    options=["light", "dark", "system"],
                    index=["light", "dark", "system"].index(config['ui']['theme'])
                )
                config['ui']['theme'] = theme
                
                language = st.selectbox(
                    "Idioma",
                    options=["es", "en", "pt"],
                    index=["es", "en", "pt"].index(config['ui']['language'])
                )
                config['ui']['language'] = language
            
            with col2:
                refresh_interval = st.slider(
                    "Intervalo de Actualización (segundos)",
                    min_value=5,
                    max_value=120,
                    value=config['ui']['refresh_interval']
                )
                config['ui']['refresh_interval'] = refresh_interval
                
                default_view = st.selectbox(
                    "Vista por Defecto",
                    options=["dashboard", "control", "analytics", "history"],
                    index=["dashboard", "control", "analytics", "history"].index(config['ui']['default_view'])
                )
                config['ui']['default_view'] = default_view
            
            st.subheader("🤖 Configuración de Automatización")
            
            col1, col2 = st.columns(2)
            
            with col1:
                default_timeout = st.number_input(
                    "Timeout por Defecto (segundos)",
                    min_value=10,
                    max_value=300,
                    value=config['automation']['default_timeout']
                )
                config['automation']['default_timeout'] = default_timeout
                
                max_retries = st.number_input(
                    "Máximo de Reintentos",
                    min_value=0,
                    max_value=10,
                    value=config['automation']['max_retries']
                )
                config['automation']['max_retries'] = max_retries
            
            with col2:
                headless_mode = st.checkbox(
                    "Modo Headless",
                    value=config['automation']['headless_mode']
                )
                config['automation']['headless_mode'] = headless_mode
                
                screenshot_on_error = st.checkbox(
                    "Capturar Pantalla en Errores",
                    value=config['automation']['screenshot_on_error']
                )
                config['automation']['screenshot_on_error'] = screenshot_on_error
            
            if st.form_submit_button("💾 Guardar Configuración General"):
                if self.save_config('dashboard'):
                    st.success("✅ Configuración general guardada exitosamente!")
                else:
                    st.error("❌ Error guardando la configuración")
    
    def render_platforms_settings(self):
        """Renderizar configuración de plataformas"""
        config = self.configs['platforms']
        
        with st.form("platforms_settings_form"):
            st.write("Configuración de Plataformas de E-commerce:")
            
            for platform, settings in config.items():
                st.markdown("---")
                st.subheader(f"🌐 {platform.replace('_', ' ').title()}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    enabled = st.checkbox(
                        f"Habilitar {platform}",
                        value=settings.get('enabled', False),
                        key=f"enabled_{platform}"
                    )
                    settings['enabled'] = enabled
                    
                    if enabled:
                        timeout = st.number_input(
                            f"Timeout {platform}",
                            min_value=10,
                            max_value=120,
                            value=settings.get('timeout', 30),
                            key=f"timeout_{platform}"
                        )
                        settings['timeout'] = timeout
                
                with col2:
                    if enabled:
                        auto_login = st.checkbox(
                            "Login Automático",
                            value=settings.get('auto_login', True),
                            key=f"auto_login_{platform}"
                        )
                        settings['auto_login'] = auto_login
                        
                        notifications = st.checkbox(
                            "Notificaciones",
                            value=settings.get('notifications', True),
                            key=f"notifications_{platform}"
                        )
                        settings['notifications'] = notifications
                
                # Campos de API (solo mostrar si la plataforma está habilitada)
                if enabled:
                    with st.expander("🔑 Configuración de API", expanded=False):
                        if platform == "mercado_libre":
                            settings['api_key'] = st.text_input("API Key", value=settings.get('api_key', ''), type="password", key=f"api_key_{platform}")
                            settings['api_secret'] = st.text_input("API Secret", value=settings.get('api_secret', ''), type="password", key=f"api_secret_{platform}")
                        
                        elif platform == "amazon":
                            settings['access_key'] = st.text_input("Access Key", value=settings.get('access_key', ''), type="password", key=f"access_key_{platform}")
                            settings['secret_key'] = st.text_input("Secret Key", value=settings.get('secret_key', ''), type="password", key=f"secret_key_{platform}")
                            settings['region'] = st.selectbox("Región", ["us-east-1", "eu-west-1", "ap-southeast-1"], index=0, key=f"region_{platform}")
            
            if st.form_submit_button("💾 Guardar Configuración de Plataformas"):
                if self.save_config('platforms'):
                    st.success("✅ Configuración de plataformas guardada exitosamente!")
                else:
                    st.error("❌ Error guardando la configuración")
    
    def render_ui_settings(self):
        """Renderizar configuración de UI"""
        config = self.configs['dashboard']['ui']
        
        with st.form("ui_settings_form"):
            st.subheader("🎛️ Preferencias de UI")
            
            col1, col2 = st.columns(2)
            
            with col1:
                animations = st.checkbox(
                    "Animaciones",
                    value=config.get('animations', True),
                    help="Habilitar animaciones en la interfaz"
                )
                config['animations'] = animations
                
                compact_mode = st.checkbox(
                    "Modo Compacto",
                    value=config.get('compact_mode', False),
                    help="Reducir espaciado para más contenido visible"
                )
                config['compact_mode'] = compact_mode
            
            with col2:
                # Configuraciones adicionales de UI
                font_size = st.select_slider(
                    "Tamaño de Fuente",
                    options=["Pequeño", "Mediano", "Grande"],
                    value="Mediano"
                )
                
                density = st.select_slider(
                    "Densidad de Información",
                    options=["Mínima", "Moderada", "Máxima"],
                    value="Moderada"
                )
            
            if st.form_submit_button("💾 Guardar Preferencias de UI"):
                if self.save_config('dashboard'):
                    st.success("✅ Preferencias de UI guardadas exitosamente!")
                else:
                    st.error("❌ Error guardando las preferencias")
    
    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """Obtener configuración específica de plataforma"""
        return self.configs['platforms'].get(platform, {})
    
    def update_platform_config(self, platform: str, updates: Dict[str, Any]):
        """Actualizar configuración de plataforma"""
        if platform in self.configs['platforms']:
            self.configs['platforms'][platform].update(updates)
            self.save_config('platforms')
    
    def validate_config(self) -> Dict[str, Any]:
        """Validar todas las configuraciones"""
        errors = []
        warnings = []
        
        # Validar configuraciones requeridas
        dashboard_config = self.configs['dashboard']
        if not dashboard_config.get('ui', {}).get('theme'):
            errors.append("Tema de UI no configurado")
        
        # Validar plataformas habilitadas
        enabled_platforms = [
            platform for platform, config in self.configs['platforms'].items() 
            if config.get('enabled')
        ]
        
        if not enabled_platforms:
            warnings.append("No hay plataformas habilitadas")
        
        # Validar configuraciones de API para plataformas habilitadas
        for platform in enabled_platforms:
            platform_config = self.configs['platforms'][platform]
            if platform == "mercado_libre" and not platform_config.get('api_key'):
                warnings.append(f"API Key no configurada para {platform}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "enabled_platforms": enabled_platforms
        }
    
    def export_config(self, file_path: str):
        """Exportar todas las configuraciones"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Configuraciones exportadas a {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error exportando configuraciones: {e}")
            return False
    
    def import_config(self, file_path: str):
        """Importar configuraciones desde archivo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_configs = json.load(f)
            
            # Validar estructura básica
            required_keys = ['dashboard', 'platforms', 'automation']
            if all(key in imported_configs for key in required_keys):
                self.configs = imported_configs
                for key in self.configs.keys():
                    self.save_config(key)
                self.logger.info("Configuraciones importadas exitosamente")
                return True
            else:
                self.logger.error("Archivo de configuración inválido")
                return False
        except Exception as e:
            self.logger.error(f"Error importando configuraciones: {e}")
            return False
    
    def reset_to_defaults(self, config_key: str):
        """Restablecer configuración a valores por defecto"""
        if config_key in self.config_files:
            self.configs[config_key] = self.get_default_config(self.config_files[config_key])
            self.save_config(config_key)
            self.logger.info(f"Configuración {config_key} restablecida a valores por defecto")
            return True
        return False