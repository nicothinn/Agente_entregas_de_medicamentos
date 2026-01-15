"""
Configuración centralizada de la aplicación
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Settings(BaseSettings):
    """
    Configuración de la aplicación Audifarma.
    
    Centraliza todas las configuraciones del sistema incluyendo:
    - Credenciales de API (OpenAI)
    - Rutas de archivos
    - Reglas de negocio (horarios, estados)
    - Configuración del modelo LLM
    """
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    """Clave de API de OpenAI para el modelo GPT"""
    
    # LangSmith (opcional)
    langchain_api_key: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    """Clave de API de LangSmith para tracing (opcional)"""
    langchain_tracing_v2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    """Habilitar tracing de LangSmith (true/false)"""
    langchain_project: Optional[str] = os.getenv("LANGCHAIN_PROJECT", "pharma-schedule-ai")
    """Nombre del proyecto en LangSmith"""
    
    # File Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    """Directorio raíz del proyecto"""
    data_dir: Path = base_dir / "data"
    """Directorio donde se almacenan los archivos de datos"""
    excel_file: Path = data_dir / "agenda.xlsx"
    """Ruta completa al archivo Excel de agenda"""
    
    # Business Rules - Service Types
    TIPOS_SERVICIO: list[str] = ["Entrega Domicilio", "Cita Presencial"]
    """Tipos de servicio disponibles en Audifarma"""
    ESTADOS: list[str] = ["Pendiente", "Entregado", "Cancelado"]
    """Estados posibles de un servicio"""
    ESTADO_DEFAULT: str = "Pendiente"
    """Estado por defecto al crear un nuevo servicio"""
    
    # Business Rules - Business Hours
    HORARIO_INICIO_LUNES_VIERNES: str = "08:00"
    """Hora de apertura de lunes a viernes"""
    HORARIO_FIN_LUNES_VIERNES: str = "17:00"
    """Hora de cierre de lunes a viernes"""
    HORARIO_ALMUERZO_INICIO: str = "12:00"
    """Hora de inicio del almuerzo"""
    HORARIO_ALMUERZO_FIN: str = "13:00"
    """Hora de fin del almuerzo"""
    HORARIO_INICIO_SABADO: str = "08:00"
    """Hora de apertura los sábados"""
    HORARIO_FIN_SABADO: str = "12:00"
    """Hora de cierre los sábados"""
    ANTICIPACION_MINIMA_HORAS: int = 2
    """Anticipación mínima requerida para agendar una cita (en horas)"""
    
    # LLM Configuration
    model_name: str = "gpt-4o-mini"
    """Nombre del modelo de OpenAI a utilizar"""
    temperature: float = 0.0
    """Temperatura del modelo (0.0 = determinístico)"""
    
    class Config:
        """Configuración de Pydantic"""
        env_file = ".env"
        case_sensitive = False
        protected_namespaces = ('settings_',)


# Instancia global de configuración
settings = Settings()

# Asegurar que el directorio data existe
settings.data_dir.mkdir(exist_ok=True)

