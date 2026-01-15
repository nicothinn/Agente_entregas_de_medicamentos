"""
Servicio para manejo de tiempo y validaciones de horarios de atención
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from src.config import settings


class TimeService:
    """Servicio para manejo de tiempo y validaciones de horarios de atención"""
    
    @staticmethod
    def get_current_datetime() -> datetime:
        """Obtiene la fecha y hora actual"""
        return datetime.now()
    
    @staticmethod
    def get_current_date() -> str:
        """Obtiene la fecha actual en formato YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")
    
    @staticmethod
    def get_current_time() -> str:
        """Obtiene la hora actual en formato HH:MM"""
        return datetime.now().strftime("%H:%M")
    
    @staticmethod
    def get_business_hours(date_str: str) -> Optional[Tuple[str, str]]:
        """
        Obtiene el horario de atención para una fecha específica
        
        Args:
            date_str: Fecha en formato YYYY-MM-DD
            
        Returns:
            Tuple (hora_inicio, hora_fin) o None si está cerrado
        """
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            day_of_week = date_obj.weekday()  # 0=Lunes, 6=Domingo
            
            if day_of_week == 6:  # Domingo
                return None
            elif day_of_week == 5:  # Sábado
                return (settings.HORARIO_INICIO_SABADO, settings.HORARIO_FIN_SABADO)
            else:  # Lunes a Viernes
                return (settings.HORARIO_INICIO_LUNES_VIERNES, settings.HORARIO_FIN_LUNES_VIERNES)
        except ValueError:
            return None
    
    @staticmethod
    def is_lunch_time(hora: str) -> bool:
        """
        Verifica si una hora está en el horario de almuerzo
        
        Args:
            hora: Hora en formato HH:MM
            
        Returns:
            True si está en horario de almuerzo
        """
        try:
            hora_obj = datetime.strptime(hora, "%H:%M").time()
            almuerzo_inicio = datetime.strptime(settings.HORARIO_ALMUERZO_INICIO, "%H:%M").time()
            almuerzo_fin = datetime.strptime(settings.HORARIO_ALMUERZO_FIN, "%H:%M").time()
            
            return almuerzo_inicio <= hora_obj < almuerzo_fin
        except ValueError:
            return False
    
    @staticmethod
    def is_within_business_hours(fecha: str, hora: str) -> bool:
        """
        Verifica si una fecha y hora está dentro del horario de atención
        
        Args:
            fecha: Fecha en formato YYYY-MM-DD
            hora: Hora en formato HH:MM
            
        Returns:
            True si está en horario de atención
        """
        business_hours = TimeService.get_business_hours(fecha)
        if business_hours is None:
            return False
        
        hora_inicio, hora_fin = business_hours
        try:
            hora_obj = datetime.strptime(hora, "%H:%M").time()
            hora_inicio_obj = datetime.strptime(hora_inicio, "%H:%M").time()
            hora_fin_obj = datetime.strptime(hora_fin, "%H:%M").time()
            
            return hora_inicio_obj <= hora_obj <= hora_fin_obj
        except ValueError:
            return False
    
    @staticmethod
    def validate_appointment_datetime(fecha: str, hora: str) -> Tuple[bool, Optional[str]]:
        """
        Valida si una fecha y hora de cita es válida
        
        Args:
            fecha: Fecha en formato YYYY-MM-DD
            hora: Hora en formato HH:MM
            
        Returns:
            (es_valida, mensaje_error)
        """
        now = datetime.now()
        
        try:
            event_date = datetime.strptime(fecha, "%Y-%m-%d").date()
            event_time = datetime.strptime(hora, "%H:%M").time()
            event_datetime = datetime.combine(event_date, event_time)
        except ValueError:
            return False, "Formato de fecha u hora inválido. Use YYYY-MM-DD para fecha y HH:MM para hora."
        
        # Validar fecha pasada
        if event_date < now.date():
            return False, f"No se pueden agendar servicios en fechas pasadas. Fecha actual: {now.strftime('%Y-%m-%d')}"
        
        # Validar anticipación mínima
        if event_date == now.date():
            min_datetime = now + timedelta(hours=settings.ANTICIPACION_MINIMA_HORAS)
            if event_datetime < min_datetime:
                return False, f"Las citas deben agendarse con al menos {settings.ANTICIPACION_MINIMA_HORAS} horas de anticipación. Hora actual: {now.strftime('%H:%M')}"
        
        # Validar horario de atención
        business_hours = TimeService.get_business_hours(fecha)
        if business_hours is None:
            day_name = event_date.strftime("%A")
            return False, f"No se puede agendar en domingos. La farmacia está cerrada los domingos."
        
        # Validar si está en horario de almuerzo (solo lunes a viernes)
        if event_date.weekday() < 5:  # Lunes a Viernes
            if TimeService.is_lunch_time(hora):
                return False, f"El horario de {settings.HORARIO_ALMUERZO_INICIO} a {settings.HORARIO_ALMUERZO_FIN} está cerrado por almuerzo."
        
        # Validar si está dentro del horario de atención
        if not TimeService.is_within_business_hours(fecha, hora):
            hora_inicio, hora_fin = business_hours
            day_name = event_date.strftime("%A")
            return False, f"El horario de atención el {day_name} es de {hora_inicio} a {hora_fin}"
        
        return True, None
    
    @staticmethod
    def get_time_context() -> Dict[str, str]:
        """
        Obtiene contexto de tiempo para el agente
        
        Returns:
            Diccionario con información de tiempo actual
        """
        now = datetime.now()
        dias_semana_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        return {
            "fecha_actual": now.strftime("%Y-%m-%d"),
            "hora_actual": now.strftime("%H:%M"),
            "dia_semana": now.strftime("%A"),
            "dia_semana_es": dias_semana_es[now.weekday()],
            "timestamp": now.isoformat()
        }


# Instancia global del servicio
time_service = TimeService()


