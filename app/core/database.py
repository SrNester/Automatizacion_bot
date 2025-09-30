import logging
from typing import AsyncGenerator, Optional, Generator
from contextlib import asynccontextmanager

# SQLAlchemy
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from database import SessionLocal

# Async
import asyncio
from asyncio import current_task

# Nuestra configuración
from .config import settings

# Logger
logger = logging.getLogger("database")

# Configuración de metadatos para convenciones de nombres
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

class Database:
    """
    Clase de gestión de base de datos con soporte para conexiones síncronas y asíncronas
    """
    
    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._async_engine = None
        self._async_session_factory = None
        
        self._setup_database()
        logger.info("Database manager inicializado")
    
    def _setup_database(self):
        """Configura las conexiones de base de datos"""
        
        # Configuración de la base de datos síncrona (para Celery, scripts, etc.)
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        
        self._engine = create_engine(
            sync_db_url,
            poolclass=QueuePool,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            echo=settings.DATABASE_ECHO,
            connect_args={
                "connect_timeout": 10,
                "application_name": f"{settings.APP_NAME}_{settings.ENVIRONMENT}"
            }
        )
        
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
            class_=Session,
            expire_on_commit=False
        )
        
        logger.info(f"Base de datos síncrona configurada: {sync_db_url}")
    
    def get_session(self) -> Session:
        """
        Obtiene una sesión síncrona de base de datos
        Útil para Celery tasks, scripts, etc.
        """
        
        session = self._session_factory()
        try:
            return session
        except Exception as e:
            session.close()
            raise e
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[Session, None]:
        """
        Context manager para sesiones asíncronas
        Uso: async with database.get_async_session() as session:
        """
        
        session = self._session_factory()
        try:
            yield session
            await asyncio.get_event_loop().run_in_executor(None, session.commit)
        except Exception as e:
            await asyncio.get_event_loop().run_in_executor(None, session.rollback)
            logger.error(f"Error en sesión de base de datos: {str(e)}")
            raise e
        finally:
            await asyncio.get_event_loop().run_in_executor(None, session.close)
    
    def health_check(self) -> bool:
        """
        Verifica la salud de la conexión a la base de datos
        """
        
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except (SQLAlchemyError, OperationalError) as e:
            logger.error(f"Health check de base de datos falló: {str(e)}")
            return False
    
    def create_tables(self):
        """
        Crea todas las tablas en la base de datos
        Solo para desarrollo/testing
        """
        
        if settings.is_production:
            logger.warning("Creación de tablas deshabilitada en producción")
            return
        
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("Tablas de base de datos creadas exitosamente")
        except Exception as e:
            logger.error(f"Error creando tablas: {str(e)}")
            raise
    
    def drop_tables(self):
        """
        Elimina todas las tablas (PELIGROSO - solo para testing)
        """
        
        if settings.is_production:
            logger.error("DROP de tablas deshabilitado en producción")
            return
        
        try:
            Base.metadata.drop_all(bind=self._engine)
            logger.warning("Todas las tablas eliminadas")
        except Exception as e:
            logger.error(f"Error eliminando tablas: {str(e)}")
            raise
    
    def get_table_names(self) -> list:
        """Obtiene lista de nombres de tablas"""
        
        return Base.metadata.tables.keys()
    
    def get_engine_stats(self) -> dict:
        """Obtiene estadísticas del engine de base de datos"""
        
        if not self._engine:
            return {}
        
        return {
            "pool_size": self._engine.pool.size(),
            "checked_in": self._engine.pool.checkedin(),
            "checked_out": self._engine.pool.checkedout(),
            "overflow": self._engine.pool.overflow(),
            "connections": self._engine.pool.checkedin() + self._engine.pool.checkedout()
        }

# Instancia global de la base de datos
database = Database()

# Dependency para FastAPI
def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obtener sesión de base de datos en endpoints de FastAPI
    """
    
    db = database.get_session()
    try:
        yield db
    finally:
        db.close()

# Dependency async para FastAPI
async def get_async_db() -> AsyncGenerator[Session, None]:
    """
    Dependency async para obtener sesión de base de datos
    """
    
    async with database.get_async_session() as session:
        yield session

# Funciones de utilidad para transacciones
@asynccontextmanager
async def transaction_context(db: Session):
    """
    Context manager para transacciones explícitas
    """
    
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transacción falló: {str(e)}")
        raise e

def execute_raw_sql(query: str, params: dict = None) -> list:
    """
    Ejecuta SQL raw de forma segura
    """
    
    with database.get_session() as session:
        try:
            result = session.execute(query, params or {})
            return result.fetchall()
        except Exception as e:
            logger.error(f"Error ejecutando SQL raw: {str(e)}")
            raise e

# Inicialización de la base de datos al importar
def init_database():
    """Inicializa la base de datos (crear tablas si es necesario)"""
    
    if settings.is_development:
        logger.info("Modo desarrollo - verificando tablas...")
        database.create_tables()
    
    # Verificar conexión
    if database.health_check():
        logger.info("✅ Conexión a base de datos establecida")
    else:
        logger.error("❌ No se pudo conectar a la base de datos")

# Inicializar al importar el módulo
init_database()