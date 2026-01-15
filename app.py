"""
Aplicación Streamlit para Audifarma - Asistente de Servicios Farmacéuticos
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path
import base64
import re

from src.agents.pharma_agent import get_agent
from src.services.excel_service import excel_service
from src.services.cancel_service import (
    is_cancel_intent,
    extract_name_for_cancel,
    format_candidates,
    parse_selection,
    find_services_by_name,
    delete_services_by_ids,
)
from src.models.exceptions import ExcelLockedError
from src.config import settings
from src.utils.logger import logger


# Configuración de la página
st.set_page_config(
    page_title="Audifarma",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado (enfocado en legibilidad, sin forzar fondos que vuelvan el texto invisible)
st.markdown("""
    <style>
    /* Logo */
    .logo-container {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.5rem 0;
    }

    .logo-img {
        max-height: 60px;
        max-width: 200px;
    }

    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.25rem;
    }

    .subtitle {
        color: #9aa0a6;
        margin-bottom: 1.25rem;
    }

    /* Legibilidad: no sobrescribir fondos de mensajes (evita texto blanco sobre fondo blanco) */
    [data-testid="stChatMessage"] {
        border-radius: 10px;
        padding: 0.25rem 0;
    }

    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        color: inherit;
    }

    /* Input: asegurar contraste */
    .stChatInput textarea {
        color: #111 !important;
        background: #fff !important;
        border-radius: 10px !important;
        border: 1px solid rgba(0,0,0,0.25) !important;
    }

    /* Espacio inferior para que el input no tape el contenido */
    .main .block-container {
        padding-bottom: 2rem !important;
    }
    </style>
""", unsafe_allow_html=True)


def load_logo():
    """Carga el logo si existe, sino retorna None"""
    logo_paths = [
        Path("assets/logo.png"),
        Path("assets/logo.jpg"),
        Path("data/logo.png"),
        Path("logo.png"),
        Path("logo.jpg"),
    ]
    
    for logo_path in logo_paths:
        if logo_path.exists():
            return logo_path
    return None


def display_logo():
    """Muestra el logo en la barra superior si existe"""
    logo_path = load_logo()
    if logo_path:
        try:
            with open(logo_path, "rb") as f:
                logo_data = f.read()
                logo_base64 = base64.b64encode(logo_data).decode()
                st.markdown(
                    f"""
                    <div class="logo-container">
                        <img src="data:image/png;base64,{logo_base64}" class="logo-img" alt="Audifarma Logo">
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        except Exception:
            pass  # Si no se puede cargar, simplemente no mostrar


def initialize_session_state():
    """Inicializa el estado de la sesión"""
    if "agent" not in st.session_state:
        try:
            st.session_state.agent = get_agent()
        except Exception as e:
            st.error(f"Error al inicializar el agente: {str(e)}")
            st.session_state.agent = None
    
    if "messages" not in st.session_state:
        # Agregar mensaje inicial por defecto
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hola soy un asistente de la farmacia Audifarma para programar, consultar y eliminar entregas de medicamentos."
            }
        ]
    
    if "last_update" not in st.session_state:
        st.session_state.last_update = datetime.now()

    # Estado para flujo de cancelación por chat (determinístico, sin loops del LLM)
    if "cancel_flow_active" not in st.session_state:
        st.session_state.cancel_flow_active = False
    if "cancel_candidates" not in st.session_state:
        st.session_state.cancel_candidates = []
    if "cancel_patient_name" not in st.session_state:
        st.session_state.cancel_patient_name = None
    
    # Poblar datos sintéticos si el Excel está vacío
    if "sample_data_populated" not in st.session_state:
        try:
            df = excel_service.get_all_events()
            if df.empty or len(df) == 0:
                excel_service.populate_sample_data()
            st.session_state.sample_data_populated = True
        except Exception as e:
            # Silenciar errores de población de datos (puede fallar si el Excel está abierto)
            st.session_state.sample_data_populated = True


def load_events_data() -> pd.DataFrame:
    """Carga los eventos desde Excel"""
    try:
        df = excel_service.get_all_events()
        return df
    except ExcelLockedError as e:
        st.error(f"⚠️ {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame()




def _handle_cancel_flow(prompt: str) -> str | None:
    """
    ELIMINACIÓN por nombre desde chat, sin LLM:
    1) Usuario pide cancelar/eliminar por nombre
    2) Se listan servicios activos
    3) Usuario elige número(s)
    4) Se elimina la fila del Excel (hard delete)
    """
    logger.debug(f"Procesando prompt para cancelación: {prompt[:50]}...")
    
    # Si ya estamos en selección
    if st.session_state.cancel_flow_active:
        cands = st.session_state.cancel_candidates or []
        if not cands:
            st.session_state.cancel_flow_active = False
            return "No hay una lista activa de servicios para cancelar. Escribe: `Cancelar servicios de <nombre>`."

        selected = parse_selection(prompt, len(cands))
        if not selected:
            return "No entendí qué servicio cancelar. Responde con un número (ej: `1`) o varios (ej: `1,3`)."

        # Extraer IDs de servicios seleccionados
        service_ids = []
        for n in selected:
            if n < 1 or n > len(cands):
                continue
            ev = cands[n - 1]
            sid = ev.get("ID_Servicio")
            if sid and not pd.isna(sid):
                service_ids.append(str(sid).strip())

        if not service_ids:
            return "No se pudieron extraer IDs válidos de los servicios seleccionados."

        # Eliminar servicios usando el servicio
        result = delete_services_by_ids(service_ids)

        # cerrar flujo
        st.session_state.cancel_flow_active = False
        st.session_state.cancel_candidates = []
        st.session_state.cancel_patient_name = None

        msg = f"✅ Eliminé **{result['deleted']}** servicio(s) del Excel."
        if result['errors']:
            msg += "\n\n⚠️ Algunos no se pudieron cancelar:\n- " + "\n- ".join(result['errors'])
        msg += "\n\nSi quieres eliminar más, escribe: `Eliminar servicios de <nombre>`."
        return msg

    # Si no estamos en flujo, detectar intención
    if not is_cancel_intent(prompt):
        return None

    name = extract_name_for_cancel(prompt)
    if not name:
        return (
            "No pude identificar el nombre del paciente. "
            "Por favor, menciona el nombre. Ejemplos:\n"
            "- `Eliminar entregas de Jorge Ramírez`\n"
            "- `Borrar registros de María`\n"
            "- `Cancelar servicios de Juan Pérez`"
        )

    # Buscar servicios usando el servicio
    cands = find_services_by_name(name)

    if not cands:
        return f"No encontré entregas/registros para **{name}**."

    st.session_state.cancel_flow_active = True
    st.session_state.cancel_candidates = cands
    st.session_state.cancel_patient_name = name
    return format_candidates(cands, name)


def render_sidebar_dashboard():
    """Renderiza el dashboard en la barra lateral"""
    st.sidebar.header("📊 Indicadores Operativos")
    
    # Cargar datos
    df = load_events_data()
    
    if df.empty:
        st.sidebar.info("No hay servicios registrados aún.")
        return
    
    # KPI 1: Entregas programadas hoy
    hoy = datetime.now().strftime("%Y-%m-%d")
    entregas_hoy = len(df[df['Fecha'] == hoy]) if 'Fecha' in df.columns else 0
    st.sidebar.metric("📅 Entregas Programadas Hoy", entregas_hoy)
    
    # KPI 2: Medicamento más solicitado
    if 'Medicamento' in df.columns and not df['Medicamento'].empty:
        top_med = df['Medicamento'].mode()
        if not top_med.empty:
            st.sidebar.write(f"💊 **Medicamento más solicitado:** {top_med.iloc[0]}")
    
    # KPI 3: Mapa de sedes (gráfico de barras)
    if 'Sede' in df.columns and not df['Sede'].empty:
        st.sidebar.subheader("📍 Distribución por Sede")
        sede_counts = df['Sede'].value_counts()
        st.sidebar.bar_chart(sede_counts)
    
    # Próximos 5 servicios
    st.sidebar.subheader("⏰ Próximos Servicios")
    if 'Fecha' in df.columns and 'Hora' in df.columns:
        # Filtrar solo pendientes
        df_pendientes = df[df.get('Estado', '') == 'Pendiente'].copy()
        if not df_pendientes.empty:
            # Crear columna combinada de fecha y hora para ordenar
            df_pendientes['Fecha_Hora'] = pd.to_datetime(
                df_pendientes['Fecha'] + ' ' + df_pendientes['Hora'],
                errors='coerce'
            )
            # Ordenar y tomar los próximos 5
            df_pendientes = df_pendientes.sort_values('Fecha_Hora').head(5)
            
            # Mostrar en formato amigable
            for idx, row in df_pendientes.iterrows():
                st.sidebar.write(f"**{row.get('Nombre_Paciente', 'N/A')}**")
                st.sidebar.write(f"📅 {row.get('Fecha', 'N/A')} 🕐 {row.get('Hora', 'N/A')}")
                st.sidebar.write(f"💊 {row.get('Medicamento', 'N/A')}")
                st.sidebar.write("---")
        else:
            st.sidebar.info("No hay servicios pendientes.")
    else:
        st.sidebar.info("Datos no disponibles.")


def render_main_chat():
    """Renderiza el chat principal con diseño mejorado"""
    # Header
    col1, col2 = st.columns([1, 5])
    with col1:
        st.markdown('<div style="font-size: 3rem; text-align: center;">💊</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="main-header">Audifarma</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Asistente de Servicios Farmacéuticos</div>', unsafe_allow_html=True)

    st.divider()

    # Renderizar historial (siempre arriba del input)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input (siempre al final). Si llega un prompt, procesamos y hacemos rerun
    prompt = st.chat_input("Escribe tu solicitud aquí...")
    if not prompt:
        return

    # Guardar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 1) Cancelación determinística por nombre + selección (sin LLM)
    response = _handle_cancel_flow(prompt)

    # 2) Si no aplica, usar el agente normal
    if response is None:
        try:
            if st.session_state.agent is None:
                response = "Error: No se pudo inicializar el agente."
            else:
                response = st.session_state.agent.invoke({"input": prompt})["output"]
        except ExcelLockedError as e:
            response = f"⚠️ Error: {str(e)}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_update = datetime.now()
    st.rerun()


def render_data_view():
    """Renderiza la vista de datos con tabla y descarga"""
    st.header("📋 Vista de Datos")
    
    df = load_events_data()
    
    if df.empty:
        st.info("No hay datos para mostrar.")
        return
    
    # Mostrar estadísticas rápidas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Servicios", len(df))
    with col2:
        pendientes = len(df[df.get('Estado', '') == 'Pendiente']) if 'Estado' in df.columns else 0
        st.metric("Pendientes", pendientes)
    with col3:
        entregados = len(df[df.get('Estado', '') == 'Entregado']) if 'Estado' in df.columns else 0
        st.metric("Entregados", entregados)
    with col4:
        cancelados = len(df[df.get('Estado', '') == 'Cancelado']) if 'Estado' in df.columns else 0
        st.metric("Cancelados", cancelados)
    
    st.divider()
    
    # Botón de descarga
    try:
        excel_file = excel_service.file_path
        if excel_file.exists():
            with open(excel_file, "rb") as f:
                excel_data = f.read()
                st.download_button(
                    label="📥 Descargar Excel",
                    data=excel_data,
                    file_name=f"agenda_audifarma_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    except Exception as e:
        st.warning(f"No se pudo preparar el archivo para descarga: {str(e)}")
    
    st.divider()
    
    # Mostrar tabla
    st.subheader("Tabla de Servicios")
    st.dataframe(df, use_container_width=True, height=600)


def render_visualizations():
    """Renderiza visualizaciones adicionales"""
    st.header("📈 Análisis de Servicios")
    
    df = load_events_data()
    
    if df.empty:
        st.info("No hay datos para visualizar.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Servicios por Día")
        if 'Fecha' in df.columns:
            servicios_por_dia = df['Fecha'].value_counts().sort_index()
            st.line_chart(servicios_por_dia)
    
    with col2:
        st.subheader("Distribución por Tipo de Servicio")
        if 'Tipo_Servicio' in df.columns:
            tipo_counts = df['Tipo_Servicio'].value_counts()
            st.bar_chart(tipo_counts)
    
    st.divider()
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Distribución por Estado")
        if 'Estado' in df.columns:
            estado_counts = df['Estado'].value_counts()
            st.bar_chart(estado_counts)
    
    with col4:
        st.subheader("Distribución por Sede")
        if 'Sede' in df.columns:
            sede_counts = df['Sede'].value_counts()
            st.bar_chart(sede_counts)


def main():
    """Función principal"""
    # Mostrar logo
    display_logo()
    
    # Inicializar estado
    initialize_session_state()
    
    # Renderizar sidebar
    render_sidebar_dashboard()
    
    # Crear pestañas
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📋 Vista de Datos", "📈 Gráficos"])
    
    with tab1:
        render_main_chat()
    
    with tab2:
        render_data_view()
    
    with tab3:
        render_visualizations()


if __name__ == "__main__":
    # Verificar configuración
    if not settings.openai_api_key:
        st.error("⚠️ OPENAI_API_KEY no está configurada. Por favor, configúrala en el archivo .env")
        st.stop()
    
    main()

