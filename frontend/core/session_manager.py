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
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas para las métricas del dashboard"""
        try:
            if not self.sessions:
                return self._get_empty_statistics()
            
            total_sessions = len(self.sessions)
            successful_sessions = len([s for s in self.sessions if s.get('status') == 'completed'])
            failed_sessions = len([s for s in self.sessions if s.get('status') == 'failed'])
            pending_sessions = len([s for s in self.sessions if s.get('status') == 'pending'])
            
            # Calcular tasa de éxito
            success_rate = (successful_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            # Calcular productos procesados totales
            total_products = sum(s.get('products_processed', 0) for s in self.sessions)
            
            # Calcular duración promedio
            durations = [s.get('duration', 0) for s in self.sessions if s.get('duration')]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Sesiones por plataforma
            platforms = {}
            for session in self.sessions:
                platform = session.get('platform', 'unknown')
                platforms[platform] = platforms.get(platform, 0) + 1
            
            # Sesiones de hoy
            today = datetime.now().date()
            sessions_today = 0
            for session in self.sessions:
                try:
                    if 'timestamp' in session:
                        timestamp_str = session['timestamp'].replace('Z', '+00:00')
                        session_date = datetime.fromisoformat(timestamp_str).date()
                        if session_date == today:
                            sessions_today += 1
                except (ValueError, KeyError, AttributeError):
                    continue
            
            return {
                'total_sessions': total_sessions,
                'successful_sessions': successful_sessions,
                'failed_sessions': failed_sessions,
                'pending_sessions': pending_sessions,
                'success_rate': round(success_rate, 2),
                'total_products': total_products,
                'avg_duration': round(avg_duration, 2),
                'avg_time': round(avg_duration, 2),
                'sessions_today': sessions_today,
                'platforms_distribution': platforms,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculando estadísticas: {str(e)}")
            return self._get_empty_statistics()
    
    def _get_empty_statistics(self) -> Dict[str, Any]:
        """Retornar estadísticas vacías cuando no hay datos"""
        return {
            'total_sessions': 0,
            'successful_sessions': 0,
            'failed_sessions': 0,
            'pending_sessions': 0,
            'success_rate': 0,
            'total_products': 0,
            'avg_duration': 0,
            'avg_time': 0.0,
            'sessions_today': 0,
            'platforms_distribution': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance"""
        stats = self.get_statistics()
        
        # Calcular métricas de performance basadas en las estadísticas
        throughput = stats["total_products"] / max(stats["total_sessions"], 1)
        reliability = 100 - (stats["failed_sessions"] / max(stats["total_sessions"], 1) * 100)
        efficiency = min(stats["success_rate"] * (100 / max(stats["avg_duration"], 1)), 100)
        
        return {
            "overall_performance": stats["success_rate"],
            "throughput": round(throughput, 2),
            "reliability": round(reliability, 2),
            "efficiency": round(efficiency, 2),
            "availability": "99.8%",
            "last_calculation": datetime.now().isoformat(),
            "data_points": stats["total_sessions"]
        }
    
    def get_daily_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Obtener estadísticas diarias para los últimos N días"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        daily_stats = {}
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            sessions_on_date = [
                s for s in self.sessions 
                if datetime.fromisoformat(s['timestamp'].replace('Z', '+00:00')).date() == current_date.date()
            ]
            
            successful = len([s for s in sessions_on_date if s.get('status') == 'completed'])
            failed = len([s for s in sessions_on_date if s.get('status') == 'failed'])
            
            daily_stats[date_str] = {
                'total': len(sessions_on_date),
                'successful': successful,
                'failed': failed,
                'success_rate': round((successful / len(sessions_on_date) * 100) if sessions_on_date else 0, 2)
            }
            
            current_date += timedelta(days=1)
        
        return daily_stats
    
    def get_platform_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas detalladas por plataforma"""
        platforms = {}
        
        for session in self.sessions:
            platform = session.get('platform', 'unknown')
            if platform not in platforms:
                platforms[platform] = {
                    'total_sessions': 0,
                    'successful_sessions': 0,
                    'failed_sessions': 0,
                    'total_products': 0,
                    'total_duration': 0
                }
            
            platforms[platform]['total_sessions'] += 1
            platforms[platform]['total_products'] += session.get('products_processed', 0)
            platforms[platform]['total_duration'] += session.get('duration', 0)
            
            if session.get('status') == 'completed':
                platforms[platform]['successful_sessions'] += 1
            elif session.get('status') == 'failed':
                platforms[platform]['failed_sessions'] += 1
        
        # Calcular métricas derivadas
        for platform, data in platforms.items():
            data['success_rate'] = round(
                (data['successful_sessions'] / data['total_sessions'] * 100) if data['total_sessions'] > 0 else 0, 
                2
            )
            data['avg_duration'] = round(
                data['total_duration'] / data['total_sessions'] if data['total_sessions'] > 0 else 0, 
                2
            )
            data['products_per_session'] = round(
                data['total_products'] / data['total_sessions'] if data['total_sessions'] > 0 else 0, 
                2
            )
        
        return platforms
    
    def add_sample_data(self):
        """Agregar datos de ejemplo para testing"""
        sample_sessions = [
            {
                'platform': 'whatsapp',
                'action': 'send_message',
                'status': 'completed',
                'products_processed': 15,
                'duration': 120,
                'message': 'Promoción enviada exitosamente'
            },
            {
                'platform': 'email',
                'action': 'campaign',
                'status': 'completed',
                'products_processed': 50,
                'duration': 300,
                'message': 'Campaña de email completada'
            },
            {
                'platform': 'whatsapp',
                'action': 'send_message',
                'status': 'failed',
                'products_processed': 0,
                'duration': 30,
                'message': 'Error de conexión',
                'error': 'Timeout exception'
            },
            {
                'platform': 'instagram',
                'action': 'auto_reply',
                'status': 'completed',
                'products_processed': 8,
                'duration': 60,
                'message': 'Respuestas automáticas enviadas'
            }
        ]
        
        for session_data in sample_sessions:
            self.add_session(session_data)
        
        self.logger.info("Datos de ejemplo agregados exitosamente")