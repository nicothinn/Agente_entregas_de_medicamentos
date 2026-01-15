"""
Servicio para manejo del flujo de cancelación/eliminación de servicios.

Este módulo contiene la lógica de negocio para detectar intenciones de cancelación
y procesar eliminaciones de servicios, separada de la lógica de UI.
"""
import re
from typing import Optional, List, Dict, Any
import pandas as pd

from src.services.excel_service import excel_service
from src.models.exceptions import ExcelLockedError
from src.utils.logger import logger


def is_cancel_intent(text: str) -> bool:
    """
    Detecta si el prompt es una intención de cancelar/eliminar.
    Acepta múltiples variaciones: eliminar, borrar, cancelar, quitar, anular, etc.
    
    Args:
        text: Texto del usuario
        
    Returns:
        True si detecta intención de cancelar/eliminar
    """
    if not text:
        return False
    
    t = (text or "").lower().strip()
    
    # Palabras clave de eliminación (más amplias)
    delete_keywords = [
        r"\b(elimina|eliminar|borra|borrar|cancela|cancelar|anula|anular|quita|quitar|suprime|suprimir|remueve|remover|borre|elimine)\b",
    ]
    
    # Buscar verbo de eliminación
    has_delete_verb = any(re.search(kw, t) for kw in delete_keywords)
    
    return has_delete_verb


def extract_name_for_cancel(text: str) -> Optional[str]:
    """
    Extrae el nombre del paciente de forma flexible desde cualquier prompt de eliminación.
    Ejemplos que debe entender:
    - "eliminar entregas de Jorge Ramírez"
    - "eliminar Jorge Ramírez"
    - "borrar las entregas de María"
    - "quitar registros de Juan Pérez"
    - "cancelar servicios de Ana"
    - "eliminar de Jorge"
    - "borrar Jorge"
    
    Args:
        text: Texto del usuario
        
    Returns:
        Nombre del paciente extraído o None si no se puede extraer
    """
    if not text:
        return None
    
    t = text.strip()
    
    # 1) Entre comillas: "Jorge Ramírez"
    m = re.search(r"[\"']([^\"']{3,})[\"']", t)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) >= 3:
            return candidate
    
    # 2) Después de "de/del/para" seguido de nombre (patrón más común)
    # Ej: "eliminar entregas de Jorge Ramírez"
    patterns = [
        r"\b(?:de|del|para)\s+([A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}){0,3})\b",
        r"\b(?:de|del|para)\s+([A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}){0,3})(?:\s+\b(?:por|para|hoy|mañana|pasado|a\s+las|a\s+la|en|con|del|de|completo|por completo)\b|$)",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, t, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Limpiar colas comunes
            candidate = re.sub(r"\s+\b(por completo|completo|por favor|hoy|mañana)\b.*$", "", candidate, flags=re.IGNORECASE).strip()
            if len(candidate) >= 2:
                return candidate
    
    # 3) Buscar nombre después de verbos de eliminación (sin "de")
    # Ej: "eliminar Jorge" o "borrar María López"
    m = re.search(
        r"\b(?:elimina|eliminar|borra|borrar|cancela|cancelar|quita|quitar|anula|anular)\s+(?:las?|los?|el|la|un|una)?\s*(?:entregas?|registros?|servicios?)?\s*([A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}){0,3})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        candidate = m.group(1).strip()
        # Evitar capturar palabras de acción
        if candidate.lower() not in ["eliminar", "borrar", "cancelar", "quitar", "anular", "entregas", "registros", "servicios"]:
            if len(candidate) >= 2:
                return candidate
    
    # 4) Si el texto termina con un nombre (últimas 1-4 palabras con letras)
    # Ej: "eliminar Jorge Ramírez" o "borrar María"
    m = re.search(r"([A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúüÜñ]{2,}){0,3})\s*$", t)
    if m:
        candidate = m.group(1).strip()
        # Evitar capturar palabras de acción si están al final
        if candidate.lower() not in ["eliminar", "borrar", "cancelar", "quitar", "anular", "entregas", "registros", "servicios", "de", "del"]:
            if len(candidate) >= 2:
                return candidate
    
    return None


def format_candidates(candidates: List[Dict[str, Any]], patient_name: str) -> str:
    """
    Formatea una lista de candidatos para mostrar al usuario.
    
    Args:
        candidates: Lista de servicios encontrados
        patient_name: Nombre del paciente
        
    Returns:
        String formateado con la lista de servicios
    """
    lines = [f"Encontré {len(candidates)} servicios activos para **{patient_name}**:", ""]
    for idx, ev in enumerate(candidates, 1):
        lines.append(
            f"{idx}. **{ev.get('Medicamento','N/A')}** — {ev.get('Fecha','N/A')} {ev.get('Hora','N/A')} — {ev.get('Sede','N/A')}  \n"
            f"   ID_Servicio: `{ev.get('ID_Servicio','')}`"
        )
    lines.append("")
    lines.append("Responde con el número a cancelar (ej: `1`) o varios (ej: `1,3`). También puedes escribir `todas`.")
    return "\n".join(lines)


def parse_selection(text: str, max_n: int) -> List[int]:
    """
    Parsea la selección del usuario (números o "todas").
    
    Args:
        text: Texto del usuario
        max_n: Número máximo de opciones
        
    Returns:
        Lista de índices seleccionados (1-indexed)
    """
    t = (text or "").strip().lower()
    if t in {"todas", "todos", "all"}:
        return list(range(1, max_n + 1))
    nums = [int(x) for x in re.findall(r"\d+", t)]
    out: List[int] = []
    seen: set[int] = set()
    for n in nums:
        if 1 <= n <= max_n and n not in seen:
            out.append(n)
            seen.add(n)
    return out


def find_services_by_name(name: str) -> List[Dict[str, Any]]:
    """
    Busca servicios por nombre del paciente (insensible a acentos).
    
    Args:
        name: Nombre del paciente
        
    Returns:
        Lista de servicios encontrados
    """
    logger.debug(f"Buscando servicios para: {name}")
    
    try:
        # Primero intentar búsqueda normal (excluye cancelados)
        cands = excel_service.find_events_by_criteria(nombre=name)
    except Exception as e:
        logger.exception(f"Error al buscar servicios: {str(e)}")
        return []
    
    # Para eliminar, incluimos también servicios cancelados y pasados si aparecen en el Excel.
    # find_events_by_criteria excluye cancelados por defecto, así que hacemos búsqueda ampliada desde el DF completo.
    # Usar búsqueda insensible a acentos
    try:
        df_all = excel_service.get_all_events()
        if df_all.empty:
            return cands
        
        # Normalizar nombres para búsqueda insensible a acentos
        normalized_search = excel_service.normalize_name(name)
        df_normalized = df_all["Nombre_Paciente"].apply(excel_service.normalize_name)
        mask = df_normalized.str.contains(normalized_search, case=False, na=False)
        cands_all = df_all[mask].to_dict("records")
        
        if cands_all:
            logger.info(f"Encontrados {len(cands_all)} servicios (incluyendo cancelados) para {name}")
            return cands_all
    except Exception as e:
        logger.warning(f"Error en búsqueda ampliada, usando resultados básicos: {str(e)}")
        pass
    
    return cands


def delete_services_by_ids(service_ids: List[str]) -> Dict[str, Any]:
    """
    Elimina servicios físicamente del Excel por sus IDs.
    
    Args:
        service_ids: Lista de ID_Servicio a eliminar
        
    Returns:
        Diccionario con resultado: {"deleted": int, "errors": List[str]}
    """
    deleted = 0
    errors: List[str] = []
    
    for sid in service_ids:
        try:
            sid_str = str(sid).strip()
            if not sid_str:
                errors.append(f"ID vacío")
                continue
                
            result = excel_service.hard_delete_service_by_id(sid_str)
            if result.get("success"):
                deleted += 1
                logger.info(f"Servicio eliminado: {sid_str}")
            else:
                errors.append(f"{sid_str}: {result.get('message', 'Error desconocido')}")
        except ExcelLockedError as e:
            logger.error(f"Excel bloqueado al eliminar {sid}: {str(e)}")
            errors.append(f"{sid}: Excel bloqueado - {str(e)}")
        except Exception as e:
            logger.exception(f"Error al eliminar servicio {sid}: {str(e)}")
            errors.append(f"{sid}: {str(e)}")
    
    return {
        "deleted": deleted,
        "errors": errors,
        "total_requested": len(service_ids)
    }

