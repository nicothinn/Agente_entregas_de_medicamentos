"""
Agente LangChain para gestión de servicios farmacéuticos de Audifarma
"""
# Monkey patch para evitar el error de 'proxies' en versiones nuevas de openai
# Parchear httpx.Client que es usado por openai internamente
import httpx

_original_httpx_client_init = httpx.Client.__init__

def _patched_httpx_client_init(self, *args, **kwargs):
    # Remover 'proxies' si existe - openai 1.40+ no lo acepta
    if 'proxies' in kwargs:
        del kwargs['proxies']
    return _original_httpx_client_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_httpx_client_init

# También parchear AsyncClient
_original_httpx_async_client_init = httpx.AsyncClient.__init__

def _patched_httpx_async_client_init(self, *args, **kwargs):
    if 'proxies' in kwargs:
        del kwargs['proxies']
    return _original_httpx_async_client_init(self, *args, **kwargs)

httpx.AsyncClient.__init__ = _patched_httpx_async_client_init

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool

from src.config import settings
from src.models.schemas import UnifiedQuerySchema, PharmaEvent
from src.services.time_service import time_service
from src.tools.excel_tools import (
    add_pharma_event_tool,
    consultar_servicios_tool,
    get_events_by_date_tool,
    get_events_by_patient_tool,
    update_event_status_tool,
    buscar_servicios_para_cancelar_tool,
    cancelar_servicio_tool,
    delete_event_tool,
    DateQuerySchema,
    PatientQuerySchema,
    StatusUpdateSchema,
    CancelServiceSchema,
    BuscarServiciosSchema,
    DeleteEventSchema,
)
from src.tools.time_tools import get_current_datetime_tool
from src.utils.logger import logger


# System Prompt base (se actualizará dinámicamente con tiempo actual)
SYSTEM_PROMPT_BASE = """Eres el asistente de IA de Audifarma, especializado en la gestión de servicios farmacéuticos. 
Tu objetivo es agendar entregas de medicamentos y citas de pacientes con precisión quirúrgica.

INSTRUCCIONES IMPORTANTES:
1. Siempre debes validar que el paciente proporcione su ID (cédula), nombre completo y la sede antes de agendar.
2. El nombre del paciente es OBLIGATORIO - nunca agendes sin un nombre válido.
3. Si el medicamento es de "Alto Costo" (como Insulina, Adalimumab, Medicamentos biológicos), 
   recuerda al usuario que debe tener la fórmula médica original a mano.
4. Para fechas relativas como "mañana", "hoy", "pasado mañana", convierte automáticamente a la fecha real.
5. Valida que la hora esté en formato de 24 horas (ej: 14:30, no 2:30 PM).
6. Siempre confirma los detalles antes de guardar.
7. Usa la herramienta get_current_datetime si necesitas conocer la fecha/hora actual.

PARA CANCELAR/ELIMINAR SERVICIOS (IMPORTANTE - LÓGICA EMPRESARIAL):
1. NUNCA elimines datos permanentemente. Siempre usa "cancelar" (soft delete) que cambia el estado a "Cancelado".
2. Flujo recomendado:
   a) Si el usuario menciona nombre: Usa buscar_servicios_para_cancelar_tool con el nombre para encontrar servicios.
   b) Si hay MÚLTIPLES servicios encontrados: Lista todos y pide al usuario que especifique cuál cancelar usando el ID_Servicio.
   c) Si hay UN SOLO servicio: Muestra los detalles y PIDE CONFIRMACIÓN antes de cancelar.
   d) Una vez confirmado: Usa cancelar_servicio_tool con el ID_Servicio específico.
3. SIEMPRE pide confirmación explícita antes de cancelar: "¿Confirmas que deseas cancelar el servicio [detalles]?"
4. Si el usuario proporciona ID_Servicio directamente, puedes proceder más rápido pero aún pide confirmación.
5. Ejemplo de flujo:
   Usuario: "Cancela lo de Jorge Ramírez"
   → Tú: Usas buscar_servicios_para_cancelar_tool(nombre="Jorge Ramírez")
   → Si hay múltiples: "Encontré 2 servicios para Jorge Ramírez: [lista]. ¿Cuál deseas cancelar?"
   → Si hay uno: "Encontré 1 servicio: [detalles]. ¿Confirmas que deseas cancelarlo?"
   → Usuario confirma → Usas cancelar_servicio_tool(servicio_id)

FORMATOS REQUERIDOS:
- Fecha: YYYY-MM-DD (ej: 2024-12-25)
- Hora: HH:MM en formato 24 horas (ej: 14:30)
- Tipo de Servicio: "Entrega Domicilio" o "Cita Presencial"
- Estado: "Pendiente" (por defecto), "Entregado" o "Cancelado"

HORARIO DE ATENCIÓN:
- Lunes a Viernes: 08:00 - 17:00 (cierra a las 5 PM)
- Lunes a Viernes: 12:00 - 13:00 cerrado por almuerzo
- Sábados: 08:00 - 12:00 (mediodía)
- Domingos: Cerrado

RESTRICCIONES IMPORTANTES:
- No puedes agendar en fechas pasadas
- No puedes agendar fuera del horario de atención
- No puedes agendar en horario de almuerzo (12:00 - 13:00)
- Las citas deben ser con al menos 2 horas de anticipación
- Si el usuario intenta agendar en domingo, informa que está cerrado

EJEMPLOS DE INTERPRETACIÓN:

Usuario: "Agenda una entrega de Insulina para Juan Pérez, cédula 1234567890, mañana a las 3 de la tarde en Sede Norte"
Respuesta: Debo convertir "mañana" a la fecha real y "3 de la tarde" a 15:00.

Usuario: "Consulta las citas del paciente 1234567890"
Respuesta: Uso ConsultarPorPaciente con paciente_id="1234567890". No necesito el nombre.

Usuario: "Consulta los servicios de Jorge Ramírez"
Respuesta: Uso ConsultarPorPaciente con nombre="Jorge Ramírez". No necesito el ID del paciente.

Usuario: "Consulta servicios de María"
Respuesta: Uso ConsultarPorPaciente con nombre="María". Puedo buscar solo con el nombre, no necesito ID.

Usuario: "Consulta servicios del 2024-12-01 al 2024-12-10"
Respuesta: Debo usar la herramienta ConsultarServicios con fecha_inicio y fecha_fin.

Usuario: "Marca como entregado el servicio de Juan Pérez para el 2024-12-25 a las 14:30"
Respuesta: Debo actualizar el estado a "Entregado".

Usuario: "Cancela el servicio de Jorge Ramírez del 2026-01-21 a las 15:00"
Respuesta: Primero uso buscar_servicios_para_cancelar_tool con nombre="Jorge Ramírez", fecha="2026-01-21", hora="15:00". Si encuentro servicios, muestro los detalles y pido confirmación. Luego uso cancelar_servicio_tool con el ID_Servicio.

Usuario: "Cancela la entrega del paciente 741852963"
Respuesta: Uso buscar_servicios_para_cancelar_tool con paciente_id="741852963". Si hay múltiples servicios, los listo y pido que especifique cuál. Si hay uno, pido confirmación y luego cancelo.

Sé profesional, amable y siempre confirma los datos importantes antes de proceder."""


def create_pharma_agent() -> AgentExecutor:
    """
    Crea y configura el agente LangChain para servicios farmacéuticos
    """
    logger.info("Inicializando agente LangChain para servicios farmacéuticos")
    
    # Inicializar el modelo LLM
    # Usar variables de entorno en lugar de pasar api_key directamente para evitar conflictos
    import os
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    # Desactivar LangSmith / tracing (evita spam de 403 y cualquier intento de telemetría)
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    for k in [
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_TRACING",
    ]:
        os.environ.pop(k, None)
    
    logger.debug(f"Configurando LLM: modelo={settings.model_name}, temperature={settings.temperature}")
    llm = ChatOpenAI(
        model=settings.model_name,
        temperature=settings.temperature
    )
    
    # Obtener contexto de tiempo actual
    time_context = time_service.get_time_context()
    logger.debug(f"Contexto de tiempo: {time_context['fecha_actual']} {time_context['hora_actual']}")
    
    # Crear system prompt dinámico con tiempo actual
    SYSTEM_PROMPT = f"""{SYSTEM_PROMPT_BASE}

INFORMACIÓN DE TIEMPO ACTUAL:
- Fecha actual: {time_context['fecha_actual']}
- Hora actual: {time_context['hora_actual']}
- Día de la semana: {time_context['dia_semana_es']}
"""
    
    # Crear herramientas con Pydantic validation
    tools = [
        StructuredTool.from_function(
            func=get_current_datetime_tool,
            name="ObtenerFechaHoraActual",
            description="Útil para obtener la fecha y hora actual del sistema. Úsala cuando necesites validar fechas o conocer el tiempo actual."
        ),
        StructuredTool.from_function(
            func=add_pharma_event_tool,
            name="AgregarServicio",
            description="Útil para agendar nuevos servicios farmacéuticos (entregas o citas). Requiere: paciente_id, nombre (OBLIGATORIO), medicamento, tipo_servicio, sede, fecha (YYYY-MM-DD), hora (HH:MM).",
            args_schema=PharmaEvent
        ),
        StructuredTool.from_function(
            func=consultar_servicios_tool,
            name="ConsultarServicios",
            description="Útil para consultar servicios de forma flexible. Puede consultar por: fecha específica, fecha+hora específica, o rango de fechas. Parámetros opcionales: fecha, fecha_inicio, fecha_fin, hora.",
            args_schema=UnifiedQuerySchema
        ),
        StructuredTool.from_function(
            func=get_events_by_date_tool,
            name="ConsultarPorFecha",
            description="Útil para consultar todos los servicios programados para una fecha específica. Requiere fecha en formato YYYY-MM-DD.",
            args_schema=DateQuerySchema
        ),
        StructuredTool.from_function(
            func=get_events_by_patient_tool,
            name="ConsultarPorPaciente",
            description="Útil para consultar todos los servicios de un paciente. Puedes usar SOLO paciente_id (cédula) O SOLO nombre. No necesitas ambos. Ejemplo: 'Consulta servicios de Jorge Ramírez' o 'Consulta servicios del paciente 741852963'.",
            args_schema=PatientQuerySchema
        ),
        StructuredTool.from_function(
            func=update_event_status_tool,
            name="ActualizarEstado",
            description="Útil para actualizar el estado de un servicio (Pendiente, Entregado, Cancelado). Requiere: paciente_id, fecha, hora, nuevo_estado.",
            args_schema=StatusUpdateSchema
        ),
        StructuredTool.from_function(
            func=buscar_servicios_para_cancelar_tool,
            name="BuscarServiciosParaCancelar",
            description="Útil para buscar servicios antes de cancelar. Maneja ambigüedad cuando hay múltiples servicios. Parámetros opcionales: paciente_id, nombre, fecha, hora, medicamento. Retorna lista de servicios con sus ID_Servicio. ÚSALA PRIMERO cuando el usuario quiera cancelar un servicio.",
            args_schema=BuscarServiciosSchema
        ),
        StructuredTool.from_function(
            func=cancelar_servicio_tool,
            name="CancelarServicio",
            description="Cancela un servicio específico por su ID_Servicio (UUID). Hace 'soft delete' cambiando el estado a 'Cancelado' para mantener trazabilidad. SOLO úsala después de que el usuario haya confirmado y tengas el ID_Servicio específico. SIEMPRE pide confirmación antes de usar esta herramienta.",
            args_schema=CancelServiceSchema
        ),
        StructuredTool.from_function(
            func=delete_event_tool,
            name="EliminarServicio",
            description="DEPRECATED: Usar BuscarServiciosParaCancelar y CancelarServicio en su lugar. Útil para eliminar (cancelar) un servicio. Puede recibir servicio_id directamente, o paciente_id+fecha+hora. Si hay ambigüedad, lista los servicios encontrados.",
            args_schema=DeleteEventSchema
        ),
    ]
    
    # Crear prompt template con memoria
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Crear el agente
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # Crear memoria de conversación
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # Crear el ejecutor del agente
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=False
    )
    
    # Guardar memoria en el ejecutor para uso posterior
    agent_executor.memory = memory
    
    logger.success(f"Agente LangChain creado exitosamente con {len(tools)} herramientas")
    return agent_executor


# Instancia global del agente (se inicializa cuando se necesite)
_agent_instance: AgentExecutor = None


def get_agent() -> AgentExecutor:
    """Obtiene la instancia del agente (singleton)"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_pharma_agent()
    return _agent_instance
