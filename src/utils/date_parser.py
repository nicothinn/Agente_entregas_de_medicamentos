"""
Utilidades para parsing y manejo de fechas
"""
from datetime import datetime, timedelta
from typing import Optional


def parse_relative_date(date_str: str) -> Optional[str]:
    """
    Intenta parsear fechas relativas como 'mañana', 'hoy', etc.
    Retorna fecha en formato YYYY-MM-DD o None si no puede parsear
    """
    date_str = date_str.lower().strip()
    today = datetime.now().date()
    
    date_mappings = {
        'hoy': today,
        'today': today,
        'mañana': today + timedelta(days=1),
        'tomorrow': today + timedelta(days=1),
        'pasado mañana': today + timedelta(days=2),
        'day after tomorrow': today + timedelta(days=2),
    }
    
    if date_str in date_mappings:
        return date_mappings[date_str].strftime('%Y-%m-%d')
    
    return None


def format_date_for_display(date_str: str) -> str:
    """Formatea una fecha YYYY-MM-DD para mostrar al usuario"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        # Formato en español
        meses = [
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
        ]
        return f"{date_obj.day} de {meses[date_obj.month - 1]} de {date_obj.year}"
    except ValueError:
        return date_str


def is_valid_date(date_str: str) -> bool:
    """Valida si una cadena es una fecha válida en formato YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

