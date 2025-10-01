import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

class SessionManager:
    def __init__(self, data_file: str = "data/sessions.json"):
        self.data_file = data_file
        self.logger = self.setup_logger()
        self.sessions = self.load_sessions()
    
    def setup_logger(self):
        """Configurar logger para SessionManager"""
        logger = logging.getLogger('SessionManager')
        if not logger.handlers:
            handler = logging.FileHandler('logs/session_manager.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def load_sessions(self) -> List[Dict[str, Any]]:
        """Cargar sesiones desde archivo JSON"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                sessions = json.load(f)
                self.logger.info(f"Cargadas {len(sessions)} sesiones desde {self.data_file}")
                return sessions
        except FileNotFoundError:
            self.logger.warning(f"Archivo {self.data_file} no encontrado, creando nuevo")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decodificando JSON: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error inesperado cargando sesiones: {e}")
            return []
    
    def save_sessions(self):
        """Guardar sesiones en archivo JSON"""
        try:
            Path(self.data_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sesiones guardadas en {self.data_file}")
        except Exception as e:
            self.logger.error(f"Error guardando sesiones: {e}")
            raise
    
    def add_session(self, session_data: Dict[str, Any]):
        """Agregar una nueva sesión"""
        try:
            session_data['id'] = len(self.sessions) + 1
            session_data['session_id'] = f"SESSION_{session_data['id']:04d}"
            session_data['timestamp'] = datetime.now().isoformat()
            session_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Validar datos requeridos
            required_fields = ['platform', 'action', 'status']
            for field in required_fields:
                if field not in session_data:
                    raise ValueError(f"Campo requerido faltante: {field}")
            
            self.sessions.append(session_data)
            self.save_sessions()
            
            self.logger.info(f"Nueva sesión agregada: {session_data['session_id']}")
            
        except Exception as e:
            self.logger.error(f"Error agregando sesión: {e}")
            raise
    
    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Actualizar una sesión existente"""
        for session in self.sessions:
            if session.get('session_id') == session_id:
                session.update(updates)
                session['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.save_sessions()
                self.logger.info(f"Sesión actualizada: {session_id}")
                return True
        self.logger.warning(f"Sesión no encontrada para actualizar: {session_id}")
        return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtener una sesión específica por ID"""
        for session in self.sessions:
            if session.get('session_id') == session_id:
                return session
        return None
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener sesiones recientes"""
        sorted_sessions = sorted(
            self.sessions, 
            key=lambda x: x.get('timestamp', ''), 
            reverse=True
        )
        return sorted_sessions[:limit]
    
    def get_sessions_by_platform(self, platform: str) -> List[Dict[str, Any]]:
        """Obtener sesiones por plataforma"""
        return [s for s in self.sessions if s.get('platform') == platform]
    
    def get_sessions_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Obtener sesiones por estado"""
        return [s for s in self.sessions if s.get('status') == status]
    
    def get_sessions_in_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Obtener sesiones en un rango de fechas"""
        result = []
        for session in self.sessions:
            try:
                session_date = datetime.fromisoformat(session.get('timestamp', '').replace('Z', '+00:00'))
                if start_date <= session_date <= end_date:
                    result.append(session)
            except (ValueError, TypeError):
                continue
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas completas de las sesiones"""
        if not self.sessions:
            return self.get_empty_statistics()
        
        try:
            df = pd.DataFrame(self.sessions)
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Filtrar fechas válidas
            df = df[df['timestamp'].notna()]
            
            # Estadísticas generales
            total_sessions = len(df)
            successful_sessions = len(df[df['status'] == 'completed'])
            failed_sessions = len(df[df['status'] == 'failed'])
            success_rate = (successful_sessions / total_sessions) * 100 if total_sessions > 0 else 0
            
            # Productos procesados
            total_products = df['products_processed'].sum() if 'products_processed' in df.columns else 0
            
            # Tiempos
            avg_duration = df['duration'].mean() if 'duration' in df.columns else 0
            
            # Sesiones de hoy
            today = datetime.now().date()
            sessions_today = len(df[df['timestamp'].dt.date == today])
            
            # Por plataforma
            platform_stats = {}
            if 'platform' in df.columns:
                platform_stats = df['platform'].value_counts().to_dict()
            
            # Por acción
            action_stats = {}
            if 'action' in df.columns:
                action_stats = df['action'].value_counts().to_dict()
            
            # Tendencias (últimos 7 días)
            last_week = datetime.now() - timedelta(days=7)
            recent_sessions = df[df['timestamp'] >= last_week]
            sessions_last_week = len(recent_sessions)
            
            return {
                "total_sessions": total_sessions,
                "successful_sessions": successful_sessions,
                "failed_sessions": failed_sessions,
                "success_rate": success_rate,
                "total_products": total_products,
                "avg_duration": avg_duration,
                "sessions_today": sessions_today,
                "sessions_last_week": sessions_last_week,
                "platform_stats": platform_stats,
                "action_stats": action_stats,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculando estadísticas: {e}")
            return self.get_empty_statistics()
    
    def get_empty_statistics(self):
        """Obtener estadísticas vacías"""
        return {
            "total_sessions": 0,
            "successful_sessions": 0,
            "failed_sessions": 0,
            "success_rate": 0,
            "total_products": 0,
            "avg_duration": 0,
            "sessions_today": 0,
            "sessions_last_week": 0,
            "platform_stats": {},
            "action_stats": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def clear_old_sessions(self, days: int = 30):
        """Eliminar sesiones antiguas"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            initial_count = len(self.sessions)
            
            self.sessions = [
                s for s in self.sessions 
                if datetime.fromisoformat(s['timestamp'].replace('Z', '+00:00')) > cutoff_date
            ]
            
            removed_count = initial_count - len(self.sessions)
            self.save_sessions()
            
            self.logger.info(f"Eliminadas {removed_count} sesiones antiguas (>{days} días)")
            
        except Exception as e:
            self.logger.error(f"Error limpiando sesiones antiguas: {e}")
    
    def export_to_csv(self, file_path: str):
        """Exportar sesiones a CSV"""
        try:
            df = pd.DataFrame(self.sessions)
            df.to_csv(file_path, index=False, encoding='utf-8')
            self.logger.info(f"Sesiones exportadas a {file_path}")
        except Exception as e:
            self.logger.error(f"Error exportando a CSV: {e}")
            raise
    
    def get_session_timeline(self, days: int = 7) -> List[Dict[str, Any]]:
        """Obtener línea de tiempo de sesiones"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        sessions_in_range = self.get_sessions_in_date_range(start_date, end_date)
        
        timeline = []
        for session in sessions_in_range:
            timeline.append({
                'session_id': session.get('session_id'),
                'platform': session.get('platform'),
                'action': session.get('action'),
                'status': session.get('status'),
                'timestamp': session.get('timestamp'),
                'duration': session.get('duration', 0),
                'products_processed': session.get('products_processed', 0)
            })
        
        return sorted(timeline, key=lambda x: x['timestamp'], reverse=True)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance"""
        stats = self.get_statistics()
        
        return {
            "overall_performance": stats["success_rate"],
            "throughput": stats["total_products"] / max(stats["total_sessions"], 1),
            "reliability": 100 - (stats["failed_sessions"] / max(stats["total_sessions"], 1) * 100),
            "efficiency": min(stats["success_rate"] * (100 / max(stats["avg_duration"], 1)), 100),
            "availability": "99.8%",  # Esto vendría de monitoreo en tiempo real
            "last_calculation": datetime.now().isoformat()
        }