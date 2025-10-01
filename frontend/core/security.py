import hashlib
import secrets
import string
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime, timedelta
import streamlit as st

class SecurityManager:
    def __init__(self):
        self.logger = self.setup_logger()
        self.attempts = {}
        self.max_attempts = 5
        self.lockout_time = 900  # 15 minutos en segundos
        self.session_timeout = 3600  # 1 hora en segundos
        
    def setup_logger(self):
        """Configurar logger para SecurityManager"""
        logger = logging.getLogger('SecurityManager')
        if not logger.handlers:
            handler = logging.FileHandler('logs/security.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def authenticate(self, username: str, password: str) -> bool:
        """Autenticar usuario"""
        try:
            # Limpiar intentos expirados
            self._clean_expired_attempts()
            
            # Verificar si el usuario está bloqueado
            if self._is_user_locked(username):
                self.logger.warning(f"Intento de login para usuario bloqueado: {username}")
                return False
            
            # Verificar credenciales
            if self._verify_credentials(username, password):
                self._clear_attempts(username)
                self.logger.info(f"Login exitoso para usuario: {username}")
                return True
            else:
                self._record_failed_attempt(username)
                self.logger.warning(f"Login fallido para usuario: {username}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error en autenticación: {e}")
            return False

    def _verify_credentials(self, username: str, password: str) -> bool:
        """Verificar credenciales de usuario"""
        # En una aplicación real, esto verificaría contra una base de datos
        # Para demo, usamos credenciales hardcodeadas
        valid_users = {
            "admin": self._hash_password("admin"),
            "user": self._hash_password("user123"),
            "demo": self._hash_password("demo123")
        }
        
        hashed_password = self._hash_password(password)
        return username in valid_users and valid_users[username] == hashed_password

    def _hash_password(self, password: str) -> str:
        """Hashear contraseña"""
        return hashlib.sha256(password.encode()).hexdigest()

    def _record_failed_attempt(self, username: str):
        """Registrar intento fallido"""
        if username not in self.attempts:
            self.attempts[username] = []
        
        self.attempts[username].append(datetime.now())
        
        # Mantener solo los últimos intentos
        if len(self.attempts[username]) > self.max_attempts:
            self.attempts[username] = self.attempts[username][-self.max_attempts:]

    def _clear_attempts(self, username: str):
        """Limpiar intentos fallidos"""
        if username in self.attempts:
            del self.attempts[username]

    def _is_user_locked(self, username: str) -> bool:
        """Verificar si el usuario está bloqueado"""
        if username not in self.attempts:
            return False
        
        attempts = self.attempts[username]
        if len(attempts) < self.max_attempts:
            return False
        
        # Verificar si el último intento fue dentro del período de bloqueo
        last_attempt = max(attempts)
        time_since_last_attempt = (datetime.now() - last_attempt).total_seconds()
        
        return time_since_last_attempt < self.lockout_time

    def _clean_expired_attempts(self):
        """Limpiar intentos expirados"""
        current_time = datetime.now()
        expired_usernames = []
        
        for username, attempts in self.attempts.items():
            # Filtrar intentos expirados
            valid_attempts = [
                attempt for attempt in attempts
                if (current_time - attempt).total_seconds() < self.lockout_time
            ]
            
            if valid_attempts:
                self.attempts[username] = valid_attempts
            else:
                expired_usernames.append(username)
        
        # Eliminar usuarios sin intentos válidos
        for username in expired_usernames:
            del self.attempts[username]

    def generate_secure_password(self, length: int = 12) -> str:
        """Generar contraseña segura"""
        if length < 8:
            raise ValueError("La longitud mínima de contraseña es 8 caracteres")
        
        # Definir conjuntos de caracteres
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Asegurar al menos un carácter de cada tipo
        password = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]
        
        # Completar con caracteres aleatorios
        all_chars = uppercase + lowercase + digits + symbols
        password.extend(secrets.choice(all_chars) for _ in range(length - 4))
        
        # Mezclar la contraseña
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)

    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validar fortaleza de contraseña"""
        results = {
            "length_ok": len(password) >= 8,
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_symbol": any(not c.isalnum() for c in password),
            "score": 0
        }
        
        # Calcular score
        score = 0
        if results["length_ok"]:
            score += 1
        if results["has_uppercase"]:
            score += 1
        if results["has_lowercase"]:
            score += 1
        if results["has_digit"]:
            score += 1
        if results["has_symbol"]:
            score += 1
        
        results["score"] = score
        results["strength"] = self._get_strength_level(score)
        
        return results

    def _get_strength_level(self, score: int) -> str:
        """Obtener nivel de fortaleza basado en score"""
        if score >= 5:
            return "Muy Fuerte"
        elif score >= 4:
            return "Fuerte"
        elif score >= 3:
            return "Moderada"
        elif score >= 2:
            return "Débil"
        else:
            return "Muy Débil"

    def encrypt_sensitive_data(self, data: str, key: str) -> str:
        """Encriptar datos sensibles (simulado)"""
        # En una aplicación real, usarías una librería como cryptography
        # Esta es una implementación básica para demo
        import base64
        
        # Simular encriptación
        encoded = base64.b64encode(data.encode()).decode()
        return f"encrypted_{encoded}"

    def decrypt_sensitive_data(self, encrypted_data: str, key: str) -> str:
        """Desencriptar datos sensibles (simulado)"""
        # En una aplicación real, usarías una librería como cryptography
        import base64
        
        if encrypted_data.startswith("encrypted_"):
            encoded = encrypted_data[10:]  # Remover prefijo
            return base64.b64decode(encoded).decode()
        return encrypted_data

    def validate_session(self) -> bool:
        """Validar sesión de usuario"""
        if not hasattr(st.session_state, 'authenticated'):
            return False
        
        if not st.session_state.authenticated:
            return False
        
        # Verificar timeout de sesión
        if hasattr(st.session_state, 'login_time'):
            login_time = st.session_state.login_time
            if isinstance(login_time, str):
                login_time = datetime.fromisoformat(login_time)
            
            session_duration = (datetime.now() - login_time).total_seconds()
            if session_duration > self.session_timeout:
                self.logout()
                return False
        
        return True

    def logout(self):
        """Cerrar sesión de usuario"""
        if hasattr(st.session_state, 'authenticated'):
            st.session_state.authenticated = False
        if hasattr(st.session_state, 'user'):
            del st.session_state.user
        if hasattr(st.session_state, 'login_time'):
            del st.session_state.login_time
        
        self.logger.info("Sesión de usuario cerrada")

    def render_security_settings(self):
        """Renderizar configuración de seguridad en Streamlit"""
        st.subheader("🔐 Configuración de Seguridad")
        
        with st.form("security_settings_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                max_attempts = st.number_input(
                    "Máximo de Intentos de Login",
                    min_value=3,
                    max_value=10,
                    value=self.max_attempts,
                    help="Número máximo de intentos fallidos antes del bloqueo"
                )
                
                session_timeout = st.number_input(
                    "Timeout de Sesión (minutos)",
                    min_value=15,
                    max_value=480,
                    value=self.session_timeout // 60,
                    help="Tiempo de inactividad antes de cerrar sesión automáticamente"
                )
            
            with col2:
                lockout_time = st.number_input(
                    "Tiempo de Bloqueo (minutos)",
                    min_value=1,
                    max_value=60,
                    value=self.lockout_time // 60,
                    help="Tiempo que un usuario permanece bloqueado después de intentos fallidos"
                )
                
                require_2fa = st.checkbox(
                    "Requerir Autenticación de Dos Factores",
                    value=False,
                    help="Requerir verificación adicional para login"
                )
            
            if st.form_submit_button("💾 Guardar Configuración de Seguridad"):
                self.max_attempts = max_attempts
                self.session_timeout = session_timeout * 60  # Convertir a segundos
                self.lockout_time = lockout_time * 60  # Convertir a segundos
                
                st.success("✅ Configuración de seguridad guardada exitosamente!")

    def get_security_report(self) -> Dict[str, Any]:
        """Obtener reporte de seguridad"""
        return {
            "failed_attempts_count": sum(len(attempts) for attempts in self.attempts.values()),
            "locked_users_count": len([user for user in self.attempts if self._is_user_locked(user)]),
            "max_attempts": self.max_attempts,
            "lockout_time": self.lockout_time,
            "session_timeout": self.session_timeout,
            "last_cleanup": datetime.now().isoformat()
        }

    def audit_log(self, action: str, user: str, details: str = ""):
        """Registrar evento de auditoría"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user": user,
            "details": details,
            "ip_address": "127.0.0.1"  # En una app real, obtendrías la IP real
        }
        
        self.logger.info(f"AUDIT - {action} by {user}: {details}")
        
        # Guardar en archivo de auditoría
        try:
            with open('logs/security_audit.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Error guardando log de auditoría: {e}")

    def check_vulnerabilities(self) -> Dict[str, Any]:
        """Revisar vulnerabilidades de seguridad"""
        vulnerabilities = []
        recommendations = []
        
        # Verificar configuraciones inseguras
        if self.max_attempts > 10:
            vulnerabilities.append("Máximo de intentos muy alto")
            recommendations.append("Reducir máximo de intentos a 5 o menos")
        
        if self.session_timeout > 86400:  # Más de 24 horas
            vulnerabilities.append("Timeout de sesión muy largo")
            recommendations.append("Reducir timeout de sesión a 1-4 horas")
        
        # Verificar logs
        try:
            with open('logs/security.log', 'r') as f:
                logs = f.read()
                if "ERROR" in logs or "WARNING" in logs:
                    vulnerabilities.append("Errores o advertencias en logs de seguridad")
                    recommendations.append("Revisar logs de seguridad regularmente")
        except FileNotFoundError:
            vulnerabilities.append("Logs de seguridad no encontrados")
            recommendations.append("Configurar sistema de logging de seguridad")
        
        return {
            "vulnerabilities_found": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "recommendations": recommendations,
            "scan_date": datetime.now().isoformat()
        }