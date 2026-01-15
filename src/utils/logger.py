"""
Configuración centralizada de logging con Loguru.

Proporciona un logger configurado con:
- Salida a consola con formato colorizado
- Rotación diaria de archivos de log
- Retención de 30 días
"""
from loguru import logger
import sys
from pathlib import Path


def setup_logger(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """
    Configura el logger de Loguru con handlers para consola y archivo.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio donde guardar los logs. Si es None, usa 'logs/' en el proyecto.
    """
    # Remover handler por defecto
    logger.remove()
    
    # Handler para consola (stderr)
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=log_level,
        colorize=True,
    )
    
    # Handler para archivo
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "pharma_ai_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",  # En archivo guardamos todo
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        compression="zip",  # Comprimir logs antiguos
        enqueue=True,  # Thread-safe logging
    )
    
    logger.info(f"Logger configurado. Nivel: {log_level}, Directorio: {log_dir}")


# Configurar logger al importar el módulo
setup_logger()

# Exportar logger para uso directo
__all__ = ["logger", "setup_logger"]

