"""
Herramientas (tools) relacionadas con Excel para el agente LangChain.

Este módulo contiene todas las tools que permiten al agente interactuar
con el servicio Excel para realizar operaciones CRUD sobre servicios farmacéuticos.
"""
from typing import Optional
from pydantic import BaseModel, Field

from src.config import settings
from src.models.schemas import PharmaEvent, EventUpdate
from src.models.exceptions import ExcelServiceError, ExcelLockedError
from src.services.excel_service import excel_service
from src.services.time_service import time_service
from src.utils.date_parser import parse_relative_date
from src.utils.logger import logger


# Esquemas Pydantic para las tools
class DateQuerySchema(BaseModel):
    """Esquema para consultas por fecha"""
    fecha: str = Field(description="Fecha en formato YYYY-MM-DD")


class PatientQuerySchema(BaseModel):
    """Esquema para consultas por paciente"""
    paciente_id: Optional[str] = Field(
        default=None,
        description="Cédula del paciente (opcional si se proporciona nombre)"
    )
    nombre: Optional[str] = Field(
        default=None,
        description="Nombre del paciente (opcional si se proporciona paciente_id)"
    )


class StatusUpdateSchema(BaseModel):
    """Esquema para actualización de estado"""
    paciente_id: str = Field(description="Cédula del paciente")
    fecha: str = Field(description="Fecha en formato YYYY-MM-DD")
    hora: str = Field(description="Hora en formato HH:MM")
    nuevo_estado: str = Field(description="Nuevo estado: Pendiente, Entregado o Cancelado")


class CancelServiceSchema(BaseModel):
    """Esquema para cancelación de servicio"""
    servicio_id: str = Field(description="ID único del servicio (UUID) a cancelar")


class BuscarServiciosSchema(BaseModel):
    """Esquema para búsqueda flexible de servicios"""
    paciente_id: Optional[str] = Field(default=None, description="Cédula del paciente (opcional)")
    nombre: Optional[str] = Field(default=None, description="Nombre del paciente (opcional)")
    fecha: Optional[str] = Field(default=None, description="Fecha en formato YYYY-MM-DD (opcional)")
    hora: Optional[str] = Field(default=None, description="Hora en formato HH:MM (opcional)")
    medicamento: Optional[str] = Field(default=None, description="Nombre del medicamento (opcional)")


class DeleteEventSchema(BaseModel):
    """Esquema para eliminación de eventos (deprecated)"""
    servicio_id: Optional[str] = Field(
        default=None,
        description="ID único del servicio (UUID). Si se proporciona, se usa directamente."
    )
    paciente_id: Optional[str] = Field(
        default=None,
        description="Cédula del paciente (opcional si se tiene servicio_id)"
    )
    fecha: Optional[str] = Field(
        default=None,
        description="Fecha en formato YYYY-MM-DD (opcional si se tiene servicio_id)"
    )
    hora: Optional[str] = Field(
        default=None,
        description="Hora en formato HH:MM (opcional si se tiene servicio_id)"
    )


def add_pharma_event_tool(
    paciente_id: str,
    nombre: str,
    medicamento: str,
    tipo_servicio: str,
    sede: str,
    fecha: str,
    hora: str,
    estado: str = None
) -> str:
    """
    Agrega un nuevo servicio farmacéutico a la agenda.
    
    Args:
        paciente_id: Cédula del paciente
        nombre: Nombre completo del paciente
        medicamento: Nombre del medicamento
        tipo_servicio: "Entrega Domicilio" o "Cita Presencial"
        sede: Sede de Audifarma
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM (24 horas)
        estado: Estado del servicio (por defecto: "Pendiente")
    
    Returns:
        Mensaje de confirmación
    """
    try:
        logger.info(f"Agregando servicio: {nombre} ({paciente_id}) - {fecha} {hora}")
        
        # Validar que el nombre no esté vacío
        if not nombre or not nombre.strip():
            logger.warning("Intento de agregar servicio sin nombre")
            return "❌ Error: El nombre del paciente es obligatorio."
        
        # Usar estado por defecto si no se proporciona
        if estado is None:
            estado = settings.ESTADO_DEFAULT
        
        # Intentar parsear fecha relativa si es necesario
        relative_date = parse_relative_date(fecha)
        if relative_date:
            fecha = relative_date
            logger.debug(f"Fecha relativa convertida: {fecha}")
        
        # Validar fecha y hora con el servicio de tiempo
        es_valida, mensaje_error = time_service.validate_appointment_datetime(fecha, hora)
        if not es_valida:
            logger.warning(f"Validación de fecha/hora falló: {mensaje_error}")
            return f"❌ Error: {mensaje_error}"
        
        # Crear evento validado con Pydantic
        event = PharmaEvent(
            paciente_id=paciente_id,
            nombre=nombre.strip(),
            medicamento=medicamento,
            tipo_servicio=tipo_servicio,
            sede=sede,
            fecha=fecha,
            hora=hora,
            estado=estado
        )
        
        # Agregar al Excel
        result = excel_service.add_pharma_event(event)
        
        # Advertencia para medicamentos de alto costo
        medicamentos_alto_costo = ['insulina', 'adalimumab', 'infliximab', 'rituximab', 'trastuzumab']
        advertencia = ""
        if any(med.lower() in medicamento.lower() for med in medicamentos_alto_costo):
            advertencia = "\n⚠️ IMPORTANTE: Este es un medicamento de alto costo. Asegúrate de tener la fórmula médica original."
            logger.info(f"Medicamento de alto costo detectado: {medicamento}")
        
        logger.success(f"Servicio agregado exitosamente. ID: {result.get('servicio_id', 'N/A')}")
        return f"{result['message']}{advertencia}"
    
    except ExcelLockedError as e:
        logger.error(f"Excel bloqueado al agregar servicio: {str(e)}")
        return f"❌ Error: {str(e)}"
    except Exception as e:
        logger.exception(f"Error al agregar servicio: {str(e)}")
        return f"❌ Error al agregar el servicio: {str(e)}"


def get_events_by_date_tool(fecha: str) -> str:
    """
    Consulta los servicios programados para una fecha específica.
    
    Args:
        fecha: Fecha en formato YYYY-MM-DD
    
    Returns:
        Lista de servicios formateada
    """
    try:
        logger.debug(f"Consultando servicios para fecha: {fecha}")
        
        # Intentar parsear fecha relativa
        relative_date = parse_relative_date(fecha)
        if relative_date:
            fecha = relative_date
        
        events = excel_service.get_events_by_date(fecha)
        
        if not events:
            logger.info(f"No hay servicios para {fecha}")
            return f"No hay servicios programados para el {fecha}."
        
        logger.info(f"Encontrados {len(events)} servicios para {fecha}")
        result = f"Servicios programados para el {fecha}:\n\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. {event['Nombre_Paciente']} (ID: {event['Paciente_ID']})\n"
            result += f"   Medicamento: {event['Medicamento']}\n"
            result += f"   Tipo: {event['Tipo_Servicio']}\n"
            result += f"   Sede: {event['Sede']}\n"
            result += f"   Hora: {event['Hora']}\n"
            result += f"   Estado: {event['Estado']}\n\n"
        
        return result
    
    except Exception as e:
        logger.exception(f"Error al consultar servicios por fecha: {str(e)}")
        return f"❌ Error al consultar servicios: {str(e)}"


def consultar_servicios_tool(
    fecha: str = None,
    fecha_inicio: str = None,
    fecha_fin: str = None,
    hora: str = None
) -> str:
    """
    Consulta servicios de forma flexible. Detecta automáticamente el tipo de consulta:
    - Si se proporciona solo 'fecha': consulta por fecha específica
    - Si se proporciona 'fecha' y 'hora': consulta por fecha y hora específica
    - Si se proporciona 'fecha_inicio' y 'fecha_fin': consulta por rango de fechas
    
    Args:
        fecha: Fecha específica en formato YYYY-MM-DD (opcional)
        fecha_inicio: Fecha de inicio del rango en formato YYYY-MM-DD (opcional)
        fecha_fin: Fecha de fin del rango en formato YYYY-MM-DD (opcional)
        hora: Hora específica en formato HH:MM (opcional, requiere fecha)
    
    Returns:
        Lista de servicios formateada
    """
    try:
        logger.debug(f"Consultando servicios - fecha: {fecha}, rango: {fecha_inicio}-{fecha_fin}, hora: {hora}")
        events = []
        
        # Detectar tipo de consulta
        if fecha_inicio and fecha_fin:
            # Consulta por rango
            relative_start = parse_relative_date(fecha_inicio)
            if relative_start:
                fecha_inicio = relative_start
            
            relative_end = parse_relative_date(fecha_fin)
            if relative_end:
                fecha_fin = relative_end
            
            events = excel_service.get_events_by_date_range(fecha_inicio, fecha_fin)
            
            if not events:
                return f"No hay servicios programados entre el {fecha_inicio} y el {fecha_fin}."
            
            result = f"Servicios programados del {fecha_inicio} al {fecha_fin}:\n\n"
            
        elif fecha and hora:
            # Consulta por fecha y hora específica
            relative_date = parse_relative_date(fecha)
            if relative_date:
                fecha = relative_date
            
            events = excel_service.get_events_by_datetime(fecha, hora)
            
            if not events:
                return f"No hay servicios programados para el {fecha} a las {hora}."
            
            result = f"Servicios programados para el {fecha} a las {hora}:\n\n"
            
        elif fecha:
            # Consulta por fecha específica
            relative_date = parse_relative_date(fecha)
            if relative_date:
                fecha = relative_date
            
            events = excel_service.get_events_by_date(fecha)
            
            if not events:
                return f"No hay servicios programados para el {fecha}."
            
            result = f"Servicios programados para el {fecha}:\n\n"
        else:
            return "❌ Error: Debes proporcionar al menos una fecha, o un rango de fechas (fecha_inicio y fecha_fin)."
        
        logger.info(f"Encontrados {len(events)} servicios")
        # Formatear resultados
        for i, event in enumerate(events, 1):
            result += f"{i}. {event['Nombre_Paciente']} (ID: {event['Paciente_ID']})\n"
            result += f"   Medicamento: {event['Medicamento']}\n"
            result += f"   Tipo: {event['Tipo_Servicio']}\n"
            result += f"   Sede: {event['Sede']}\n"
            result += f"   Fecha: {event['Fecha']}\n"
            result += f"   Hora: {event['Hora']}\n"
            result += f"   Estado: {event['Estado']}\n\n"
        
        return result
    
    except Exception as e:
        logger.exception(f"Error al consultar servicios: {str(e)}")
        return f"❌ Error al consultar servicios: {str(e)}"


def get_events_by_patient_tool(paciente_id: Optional[str] = None, nombre: Optional[str] = None) -> str:
    """
    Consulta todos los servicios de un paciente específico.
    Puede buscar por ID (cédula) o por nombre. No requiere ambos.
    
    Args:
        paciente_id: Cédula del paciente (opcional si se proporciona nombre)
        nombre: Nombre del paciente (opcional si se proporciona paciente_id)
    
    Returns:
        Lista de servicios del paciente formateada
    """
    try:
        logger.debug(f"Consultando servicios por paciente - ID: {paciente_id}, Nombre: {nombre}")
        
        if not paciente_id and not nombre:
            return "❌ Error: Debes proporcionar al menos el ID del paciente (cédula) o el nombre del paciente."
        
        # Buscar por ID o nombre
        if paciente_id:
            events = excel_service.get_events_by_patient(paciente_id)
            identificador = f"ID {paciente_id}"
        else:
            # Buscar por nombre usando find_events_by_criteria
            events = excel_service.find_events_by_criteria(nombre=nombre)
            identificador = f"nombre '{nombre}'"
        
        if not events:
            logger.info(f"No se encontraron servicios para {identificador}")
            return f"No se encontraron servicios activos para el paciente con {identificador}."
        
        logger.info(f"Encontrados {len(events)} servicios para {identificador}")
        result = f"Servicios del paciente ({identificador}):\n\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. Fecha: {event['Fecha']} - Hora: {event['Hora']}\n"
            result += f"   Nombre: {event['Nombre_Paciente']}\n"
            result += f"   ID: {event['Paciente_ID']}\n"
            result += f"   Medicamento: {event['Medicamento']}\n"
            result += f"   Tipo: {event['Tipo_Servicio']}\n"
            result += f"   Sede: {event['Sede']}\n"
            result += f"   Estado: {event['Estado']}\n"
            if 'ID_Servicio' in event:
                result += f"   ID_Servicio: {event['ID_Servicio']}\n"
            result += "\n"
        
        return result
    
    except Exception as e:
        logger.exception(f"Error al consultar servicios por paciente: {str(e)}")
        return f"❌ Error al consultar servicios: {str(e)}"


def update_event_status_tool(
    paciente_id: str,
    fecha: str,
    hora: str,
    nuevo_estado: str
) -> str:
    """
    Actualiza el estado de un servicio específico.
    
    Args:
        paciente_id: Cédula del paciente
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM
        nuevo_estado: Nuevo estado ("Pendiente", "Entregado" o "Cancelado")
    
    Returns:
        Mensaje de confirmación
    """
    try:
        logger.info(f"Actualizando estado - Paciente: {paciente_id}, {fecha} {hora}, Estado: {nuevo_estado}")
        status_update = EventUpdate(estado=nuevo_estado)
        result = excel_service.update_event_status(
            paciente_id=paciente_id,
            fecha=fecha,
            hora=hora,
            new_status=status_update
        )
        logger.success(f"Estado actualizado exitosamente")
        return result['message']
    
    except ExcelServiceError as e:
        logger.error(f"Error del servicio Excel: {str(e)}")
        return f"❌ Error: {str(e)}"
    except Exception as e:
        logger.exception(f"Error al actualizar estado: {str(e)}")
        return f"❌ Error al actualizar el estado: {str(e)}"


def buscar_servicios_para_cancelar_tool(
    paciente_id: Optional[str] = None,
    nombre: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
    medicamento: Optional[str] = None
) -> str:
    """
    Busca servicios que coincidan con los criterios proporcionados.
    Útil para manejar ambigüedad antes de cancelar.
    
    Args:
        paciente_id: Cédula del paciente (opcional)
        nombre: Nombre del paciente (opcional)
        fecha: Fecha en formato YYYY-MM-DD (opcional)
        hora: Hora en formato HH:MM (opcional)
        medicamento: Nombre del medicamento (opcional)
    
    Returns:
        Lista formateada de servicios encontrados con sus ID_Servicio
    """
    try:
        logger.debug(f"Buscando servicios para cancelar - ID: {paciente_id}, Nombre: {nombre}, Fecha: {fecha}, Hora: {hora}")
        
        # Parsear fecha relativa si es necesario
        if fecha:
            relative_date = parse_relative_date(fecha)
            if relative_date:
                fecha = relative_date
        
        events = excel_service.find_events_by_criteria(
            paciente_id=paciente_id,
            nombre=nombre,
            fecha=fecha,
            hora=hora,
            medicamento=medicamento
        )
        
        if not events:
            criterios = []
            if paciente_id:
                criterios.append(f"ID: {paciente_id}")
            if nombre:
                criterios.append(f"Nombre: {nombre}")
            if fecha:
                criterios.append(f"Fecha: {fecha}")
            if hora:
                criterios.append(f"Hora: {hora}")
            if medicamento:
                criterios.append(f"Medicamento: {medicamento}")
            
            logger.info(f"No se encontraron servicios con criterios: {', '.join(criterios)}")
            return f"No se encontraron servicios activos con los criterios: {', '.join(criterios)}."
        
        if len(events) == 1:
            event = events[0]
            logger.info(f"Un servicio encontrado: {event.get('ID_Servicio', 'N/A')}")
            return f"Se encontró 1 servicio:\n\n" \
                   f"**ID_Servicio:** {event['ID_Servicio']}\n" \
                   f"**Paciente:** {event['Nombre_Paciente']} (ID: {event['Paciente_ID']})\n" \
                   f"**Medicamento:** {event['Medicamento']}\n" \
                   f"**Tipo:** {event['Tipo_Servicio']}\n" \
                   f"**Sede:** {event['Sede']}\n" \
                   f"**Fecha:** {event['Fecha']}\n" \
                   f"**Hora:** {event['Hora']}\n" \
                   f"**Estado:** {event['Estado']}\n\n" \
                   f"Usa el ID_Servicio {event['ID_Servicio']} para cancelar este servicio."
        
        # Múltiples servicios encontrados
        logger.info(f"Múltiples servicios encontrados: {len(events)}")
        result = f"⚠️ Se encontraron {len(events)} servicios que coinciden con los criterios:\n\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. **ID_Servicio:** {event['ID_Servicio']}\n"
            result += f"   **Paciente:** {event['Nombre_Paciente']} (ID: {event['Paciente_ID']})\n"
            result += f"   **Medicamento:** {event['Medicamento']}\n"
            result += f"   **Tipo:** {event['Tipo_Servicio']}\n"
            result += f"   **Sede:** {event['Sede']}\n"
            result += f"   **Fecha:** {event['Fecha']}\n"
            result += f"   **Hora:** {event['Hora']}\n"
            result += f"   **Estado:** {event['Estado']}\n\n"
        
        result += "Por favor, especifica el ID_Servicio del servicio que deseas cancelar, o proporciona más criterios (fecha, hora, medicamento) para reducir los resultados."
        
        return result
    
    except Exception as e:
        logger.exception(f"Error al buscar servicios: {str(e)}")
        return f"❌ Error al buscar servicios: {str(e)}"


def cancelar_servicio_tool(servicio_id: str) -> str:
    """
    Cancela un servicio específico por su ID_Servicio (Soft Delete).
    Cambia el estado a 'Cancelado' en lugar de eliminar la fila.
    Esto mantiene la trazabilidad para auditoría.
    
    Args:
        servicio_id: ID único del servicio (UUID)
    
    Returns:
        Mensaje de confirmación
    """
    try:
        logger.info(f"Cancelando servicio ID: {servicio_id}")
        result = excel_service.cancel_service_by_id(servicio_id)
        service_data = result.get('data', {})
        
        logger.success(f"Servicio cancelado exitosamente. ID: {servicio_id}")
        return f"✅ {result['message']}\n\n" \
               f"**Servicio cancelado:**\n" \
               f"- Paciente: {service_data.get('Nombre_Paciente', 'N/A')} (ID: {service_data.get('Paciente_ID', 'N/A')})\n" \
               f"- Medicamento: {service_data.get('Medicamento', 'N/A')}\n" \
               f"- Fecha: {service_data.get('Fecha', 'N/A')} a las {service_data.get('Hora', 'N/A')}\n" \
               f"- El registro se mantiene en el sistema con estado 'Cancelado' para auditoría."
    
    except ExcelServiceError as e:
        logger.error(f"Error al cancelar servicio: {str(e)}")
        return f"❌ Error: {str(e)}"
    except Exception as e:
        logger.exception(f"Error inesperado al cancelar servicio: {str(e)}")
        return f"❌ Error al cancelar el servicio: {str(e)}"


def delete_event_tool(
    servicio_id: Optional[str] = None,
    paciente_id: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None
) -> str:
    """
    DEPRECATED: Usar buscar_servicios_para_cancelar_tool y cancelar_servicio_tool en su lugar.
    Mantenido por compatibilidad.
    
    Elimina (cancela) un servicio específico de la agenda.
    Si se proporciona servicio_id, se usa directamente.
    Si no, busca por paciente_id, fecha y hora.
    
    Args:
        servicio_id: ID único del servicio (UUID) - preferido
        paciente_id: Cédula del paciente (opcional si se tiene servicio_id)
        fecha: Fecha en formato YYYY-MM-DD (opcional si se tiene servicio_id)
        hora: Hora en formato HH:MM (opcional si se tiene servicio_id)
    
    Returns:
        Mensaje de confirmación o lista de servicios si hay ambigüedad
    """
    try:
        logger.warning("delete_event_tool está deprecated. Usar buscar_servicios_para_cancelar_tool y cancelar_servicio_tool")
        
        # Si se proporciona servicio_id, cancelar directamente
        if servicio_id:
            return cancelar_servicio_tool(servicio_id)
        
        # Si no, buscar primero para manejar ambigüedad
        if not paciente_id or not fecha or not hora:
            return "❌ Error: Debes proporcionar servicio_id, o paciente_id, fecha y hora."
        
        # Buscar servicios
        events = excel_service.find_events_by_criteria(
            paciente_id=paciente_id,
            fecha=fecha,
            hora=hora
        )
        
        if not events:
            return f"❌ No se encontró el servicio para el paciente {paciente_id} el {fecha} a las {hora}."
        
        if len(events) > 1:
            # Hay ambigüedad, listar servicios
            result = f"⚠️ Se encontraron {len(events)} servicios para el paciente {paciente_id} el {fecha} a las {hora}:\n\n"
            for i, event in enumerate(events, 1):
                result += f"{i}. ID_Servicio: {event['ID_Servicio']}\n"
                result += f"   Medicamento: {event['Medicamento']}, Sede: {event['Sede']}\n\n"
            result += "Por favor, usa cancelar_servicio_tool con el ID_Servicio específico."
            return result
        
        # Un solo servicio encontrado, cancelar
        servicio_id = events[0]['ID_Servicio']
        return cancelar_servicio_tool(servicio_id)
    
    except ExcelServiceError as e:
        logger.error(f"Error del servicio Excel: {str(e)}")
        return f"❌ Error: {str(e)}"
    except Exception as e:
        logger.exception(f"Error inesperado al eliminar servicio: {str(e)}")
        return f"❌ Error al eliminar el servicio: {str(e)}"


# Alias para compatibilidad (deprecated)
BuscarServiciosParaCancelar = buscar_servicios_para_cancelar_tool

