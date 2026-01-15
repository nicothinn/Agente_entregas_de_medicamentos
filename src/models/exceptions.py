"""
Jerarquía de excepciones personalizadas para el dominio farmacéutico.

Todas las excepciones heredan de PharmaBaseError para permitir
captura genérica cuando sea necesario.
"""


class PharmaBaseError(Exception):
    """
    Excepción base para todas las excepciones del proyecto.
    
    Permite capturar cualquier error del dominio de forma genérica
    mientras mantiene información específica del tipo de error.
    """
    pass


class ExcelLockedError(PharmaBaseError):
    """
    Se lanza cuando el archivo Excel está abierto por otro proceso
    o no se puede acceder por problemas de permisos.
    
    Attributes:
        file_path: Ruta del archivo que está bloqueado
    """
    
    def __init__(self, message: str, file_path: str = "") -> None:
        super().__init__(message)
        self.file_path = file_path


class ExcelServiceError(PharmaBaseError):
    """
    Error general del servicio Excel.
    
    Se usa para errores que no son específicamente de bloqueo
    pero están relacionados con operaciones del ExcelService.
    """
    pass


class ValidationError(PharmaBaseError):
    """
    Error de validación de datos.
    
    Se lanza cuando los datos proporcionados no cumplen
    con las reglas de validación definidas en los modelos Pydantic.
    
    Attributes:
        field: Campo que falló la validación (opcional)
        value: Valor que causó el error (opcional)
    """
    
    def __init__(self, message: str, field: str = "", value: str = "") -> None:
        super().__init__(message)
        self.field = field
        self.value = value


class TimeServiceError(PharmaBaseError):
    """
    Error del servicio de tiempo.
    
    Se lanza cuando hay problemas con validaciones de horarios
    o cálculos de tiempo.
    """
    pass


class AgentError(PharmaBaseError):
    """
    Error relacionado con el agente LangChain.
    
    Se lanza cuando hay problemas en la ejecución del agente
    o en la invocación de herramientas.
    """
    pass

