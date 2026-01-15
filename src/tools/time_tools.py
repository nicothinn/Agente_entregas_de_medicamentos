"""
Herramientas (tools) relacionadas con tiempo y fechas para el agente LangChain.
"""
from src.services.time_service import time_service
from src.utils.logger import logger


def get_current_datetime_tool() -> str:
    """
    Obtiene la fecha y hora actual del sistema.
    Útil para validar fechas de agendamiento y horarios de atención.
    
    Returns:
        String con información de fecha y hora actual
    """
    try:
        logger.debug("Obteniendo fecha y hora actual")
        context = time_service.get_time_context()
        result = f"Fecha actual: {context['fecha_actual']}, Hora actual: {context['hora_actual']}, Día: {context['dia_semana_es']}"
        logger.debug(f"Fecha/hora obtenida: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error al obtener fecha/hora actual: {str(e)}")
        return f"❌ Error al obtener fecha/hora actual: {str(e)}"

