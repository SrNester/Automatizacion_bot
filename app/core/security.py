import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets

# Nuestra configuración
from .config import settings

# Logger
logger = logging.getLogger("security")

# Contexto para hashing de passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de autenticación HTTP Bearer
oauth2_scheme = HTTPBearer(auto_error=False)

class SecurityManager:
    """
    Gestor centralizado de seguridad y autenticación
    """
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        logger.info("SecurityManager inicializado")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifica si un password plano coincide con el hash
        """
        
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Error verificando password: {str(e)}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """
        Genera hash de un password
        """
        
        return pwd_context.hash(password)
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crea un JWT access token
        """
        
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + self.access_token_expire
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verifica y decodifica un JWT token
        """
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"Token JWT inválido: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error decodificando token: {str(e)}")
            return None
    
    def create_api_key(self, user_id: int, permissions: list = None) -> str:
        """
        Crea una API key para integraciones
        """
        
        api_key_data = {
            "sub": f"api_{user_id}",
            "user_id": user_id,
            "type": "api_key",
            "permissions": permissions or ["read"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        api_key = self.create_access_token(api_key_data, timedelta(days=365))  # 1 año
        return api_key
    
    def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verifica una API key
        """
        
        payload = self.verify_access_token(api_key)
        if payload and payload.get("type") == "api_key":
            return payload
        return None
    
    def generate_reset_token(self, email: str) -> str:
        """
        Genera token para reset de password
        """
        
        reset_data = {
            "sub": email,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)  # 1 hora de expiración
        }
        
        return jwt.encode(reset_data, self.secret_key, algorithm=self.algorithm)
    
    def verify_reset_token(self, token: str) -> Optional[str]:
        """
        Verifica token de reset de password
        """
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") == "password_reset":
                return payload.get("sub")  # Retorna el email
        except JWTError:
            pass
        
        return None
    
    def generate_csrf_token(self) -> str:
        """
        Genera token CSRF
        """
        
        return secrets.token_urlsafe(32)
    
    def validate_csrf_token(self, token: str, expected_token: str) -> bool:
        """
        Valida token CSRF
        """
        
        return secrets.compare_digest(token, expected_token)

# Instancia global
security_manager = SecurityManager()

# Dependencies para FastAPI
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Dependency para obtener el usuario actual desde el JWT token
    """
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación requeridas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = security_manager.verify_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload

async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency para verificar que el usuario está activo
    """
    
    # Aquí podrías verificar en la base de datos si el usuario está activo
    # Por ahora, asumimos que todos los usuarios del token están activos
    
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    return current_user

async def get_current_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency para verificar que el usuario es administrador
    """
    
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador"
        )
    
    return current_user

async def get_api_key_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Dependency para autenticación via API Key
    """
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida"
        )
    
    api_key = credentials.credentials
    payload = security_manager.verify_api_key(api_key)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o expirada"
        )
    
    return payload

# Funciones de utilidad para permisos
def has_permission(required_permission: str):
    """
    Decorator para verificar permisos específicos
    """
    
    def permission_dependency(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        
        user_permissions = current_user.get("permissions", [])
        
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {required_permission}"
            )
        
        return current_user
    
    return permission_dependency

# Permisos predefinidos
PERMISSIONS = {
    "leads:read": "Leer leads",
    "leads:write": "Crear/editar leads",
    "leads:delete": "Eliminar leads",
    "workflows:read": "Leer workflows",
    "workflows:write": "Crear/editar workflows",
    "workflows:execute": "Ejecutar workflows",
    "reports:read": "Ver reportes",
    "reports:generate": "Generar reportes",
    "integrations:manage": "Gestionar integraciones",
    "users:manage": "Gestionar usuarios",
    "system:admin": "Acceso administrativo completo"
}

# Rate limiting simple
class RateLimiter:
    """
    Limitador de tasa simple (para endpoints sensibles)
    """
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}
    
    def is_rate_limited(self, identifier: str) -> bool:
        """
        Verifica si un identificador ha excedido el límite de tasa
        """
        
        now = datetime.utcnow()
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        key = f"{identifier}:{minute_key}"
        
        if key not in self.requests:
            self.requests[key] = 0
        
        self.requests[key] += 1
        
        # Limpiar entradas antiguas (más de 2 minutos)
        old_keys = [
            k for k in self.requests.keys() 
            if k.split(":")[1] < (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
        ]
        for old_key in old_keys:
            del self.requests[old_key]
        
        return self.requests[key] > self.requests_per_minute

# Instancias globales de rate limiters
api_rate_limiter = RateLimiter(requests_per_minute=100)  # 100 requests por minuto
auth_rate_limiter = RateLimiter(requests_per_minute=10)   # 10 auth attempts por minuto

# Dependency para rate limiting
async def check_rate_limit(
    identifier: str,
    rate_limiter: RateLimiter = api_rate_limiter
):
    """
    Dependency para verificar rate limiting
    """
    
    if rate_limiter.is_rate_limited(identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Límite de tasa excedido"
        )

# Funciones de sanitización
def sanitize_input(input_string: str) -> str:
    """
    Sanitiza entrada de usuario para prevenir inyecciones básicas
    """
    
    if not input_string:
        return ""
    
    # Remover caracteres potencialmente peligrosos
    dangerous_chars = ["<", ">", "'", '"', "&", ";", "|"]
    sanitized = input_string
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    
    return sanitized.strip()

def validate_email(email: str) -> bool:
    """
    Valida formato de email
    """
    
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Inicialización
logger.info("Módulo de seguridad cargado exitosamente")