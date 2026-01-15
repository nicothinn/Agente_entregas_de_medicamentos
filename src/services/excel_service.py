"""
Servicio para gestión de servicios farmacéuticos en Excel
Incluye manejo de concurrencia y escritura atómica
"""
import pandas as pd
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import tempfile
import shutil
import uuid
import unicodedata

from src.config import settings
from src.models.schemas import PharmaEvent, EventUpdate
from src.models.exceptions import ExcelServiceError, ExcelLockedError
from src.utils.logger import logger


class ExcelService:
    """Servicio para operaciones CRUD en Excel"""
    
    COLUMNS = [
        "ID_Servicio",
        "Paciente_ID",
        "Nombre_Paciente",
        "Medicamento",
        "Tipo_Servicio",
        "Sede",
        "Fecha",
        "Hora",
        "Estado"
    ]
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normaliza un nombre removiendo acentos y convirtiendo a minúsculas.
        Permite búsquedas insensibles a acentos: 'Nicolás' == 'Nicolas' == 'nicolas'
        """
        if not name or pd.isna(name):
            return ""
        # Normalizar unicode (NFKD separa letra + acento)
        name_norm = unicodedata.normalize('NFKD', str(name))
        # Filtrar signos diacríticos (acentos)
        name_no_accents = ''.join(c for c in name_norm if not unicodedata.combining(c))
        return name_no_accents.lower().strip()
    
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or settings.excel_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Asegura que el archivo Excel existe con las columnas correctas"""
        if not self.file_path.exists():
            # Crear DataFrame vacío con las columnas
            df = pd.DataFrame(columns=self.COLUMNS)
            try:
                df.to_excel(self.file_path, index=False, engine='openpyxl')
            except PermissionError:
                raise ExcelLockedError(
                    f"El archivo {self.file_path} está bloqueado o no se puede crear. "
                    "Asegúrate de que el archivo no esté abierto en otro programa."
                )
        else:
            # Verificar que el archivo tiene las columnas correctas
            try:
                df = pd.read_excel(self.file_path, engine='openpyxl')
                # Si faltan columnas, agregarlas
                missing_cols = set(self.COLUMNS) - set(df.columns)
                if missing_cols:
                    for col in missing_cols:
                        if col == "ID_Servicio":
                            # Para ID_Servicio, generar UUIDs para filas existentes
                            df[col] = [str(uuid.uuid4()) for _ in range(len(df))]
                        else:
                            df[col] = ""
                    df.to_excel(self.file_path, index=False, engine='openpyxl')
                # Si hay filas sin ID_Servicio, generarlos
                if 'ID_Servicio' in df.columns:
                    mask = df['ID_Servicio'].isna() | (df['ID_Servicio'] == '')
                    if mask.any():
                        df.loc[mask, 'ID_Servicio'] = [str(uuid.uuid4()) for _ in range(mask.sum())]
                        df.to_excel(self.file_path, index=False, engine='openpyxl')
            except PermissionError:
                raise ExcelLockedError(
                    f"El archivo {self.file_path} está bloqueado. "
                    "Cierra el archivo en otros programas y vuelve a intentar."
                )
            except Exception as e:
                raise ExcelServiceError(f"Error al verificar el archivo Excel: {str(e)}")
    
    def _read_dataframe(self) -> pd.DataFrame:
        """Lee el DataFrame del Excel con manejo de errores"""
        logger.debug(f"Leyendo DataFrame desde {self.file_path}")
        try:
            if not self.file_path.exists():
                logger.warning(f"Archivo Excel no existe: {self.file_path}, retornando DataFrame vacío")
                return pd.DataFrame(columns=self.COLUMNS)
            df = pd.read_excel(self.file_path, engine='openpyxl')
            logger.debug(f"Excel leído exitosamente. Filas: {len(df)}")
            # Asegurar que todas las columnas existen
            for col in self.COLUMNS:
                if col not in df.columns:
                    logger.warning(f"Columna faltante en Excel: {col}, agregándola")
                    df[col] = ""
            return df
        except PermissionError as e:
            logger.error(f"Error de permisos al leer Excel: {self.file_path}")
            raise ExcelLockedError(
                f"El archivo {self.file_path} está bloqueado. "
                "Cierra el archivo en otros programas y vuelve a intentar."
            )
        except Exception as e:
            logger.exception(f"Error inesperado al leer Excel: {str(e)}")
            raise ExcelServiceError(f"Error al leer el archivo Excel: {str(e)}")
    
    def _write_dataframe(self, df: pd.DataFrame) -> None:
        """
        Escribe el DataFrame al Excel de forma atómica
        Usa un archivo temporal para evitar corrupción
        """
        logger.debug(f"Escribiendo DataFrame a {self.file_path} ({len(df)} filas)")
        try:
            # Escribir a un archivo temporal primero
            temp_file = self.file_path.with_suffix('.tmp.xlsx')
            df.to_excel(temp_file, index=False, engine='openpyxl')
            logger.debug(f"Archivo temporal creado: {temp_file}")
            
            # Reemplazar el archivo original atómicamente
            if self.file_path.exists():
                os.replace(temp_file, self.file_path)
            else:
                temp_file.rename(self.file_path)
            logger.info(f"Excel actualizado exitosamente: {self.file_path}")
        except PermissionError as e:
            logger.error(f"Error de permisos al escribir Excel: {self.file_path}")
            if temp_file.exists():
                temp_file.unlink()
            raise ExcelLockedError(
                f"El archivo {self.file_path} está bloqueado. "
                "Cierra el archivo en otros programas y vuelve a intentar."
            )
        except Exception as e:
            logger.exception(f"Error inesperado al escribir Excel: {str(e)}")
            if temp_file.exists():
                temp_file.unlink()
            raise ExcelServiceError(f"Error al escribir el archivo Excel: {str(e)}")
    
    def add_pharma_event(self, event: PharmaEvent) -> Dict[str, Any]:
        """
        Agrega un nuevo servicio farmacéutico (escritura atómica)
        Genera un ID_Servicio único (UUID) para cada evento
        """
        logger.info(f"Agregando nuevo servicio para {event.nombre} ({event.paciente_id}) - {event.fecha} {event.hora}")
        df = self._read_dataframe()
        
        # Generar ID único para el servicio
        servicio_id = str(uuid.uuid4())
        logger.debug(f"ID_Servicio generado: {servicio_id}")
        
        # Crear nueva fila
        new_row = {
            "ID_Servicio": servicio_id,
            "Paciente_ID": event.paciente_id,
            "Nombre_Paciente": event.nombre,
            "Medicamento": event.medicamento,
            "Tipo_Servicio": event.tipo_servicio,
            "Sede": event.sede,
            "Fecha": event.fecha,
            "Hora": event.hora,
            "Estado": event.estado
        }
        
        # Agregar la nueva fila
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Escribir de forma atómica
        self._write_dataframe(df)
        
        logger.success(f"Servicio agregado exitosamente. ID: {servicio_id}")
        return {
            "success": True,
            "message": f"Servicio agendado exitosamente para {event.nombre} el {event.fecha} a las {event.hora}",
            "data": new_row,
            "servicio_id": servicio_id
        }
    
    def get_events_by_date(self, date: str, incluir_cancelados: bool = False) -> List[Dict[str, Any]]:
        """
        Consulta servicios por fecha (formato YYYY-MM-DD)
        Por defecto excluye servicios cancelados
        """
        df = self._read_dataframe()
        
        if df.empty:
            return []
        
        # Filtrar por fecha
        filtered_df = df[df['Fecha'] == date]
        
        # Excluir cancelados por defecto
        if not incluir_cancelados:
            filtered_df = filtered_df[filtered_df['Estado'] != 'Cancelado']
        
        # Convertir a lista de diccionarios
        return filtered_df.to_dict('records')
    
    def get_events_by_patient(self, paciente_id: str, incluir_cancelados: bool = False) -> List[Dict[str, Any]]:
        """
        Consulta servicios por paciente (ID)
        Por defecto excluye servicios cancelados
        """
        df = self._read_dataframe()
        
        if df.empty:
            return []
        
        # Filtrar por paciente_id
        filtered_df = df[df['Paciente_ID'] == paciente_id]
        
        # Excluir cancelados por defecto
        if not incluir_cancelados:
            filtered_df = filtered_df[filtered_df['Estado'] != 'Cancelado']
        
        # Convertir a lista de diccionarios
        return filtered_df.to_dict('records')
    
    def get_all_events(self) -> pd.DataFrame:
        """
        Obtiene todos los eventos
        """
        return self._read_dataframe()
    
    def get_events_by_datetime(self, fecha: str, hora: str) -> List[Dict[str, Any]]:
        """
        Consulta servicios por fecha y hora específica
        
        Args:
            fecha: Fecha en formato YYYY-MM-DD
            hora: Hora en formato HH:MM
            
        Returns:
            Lista de diccionarios con los eventos encontrados
        """
        df = self._read_dataframe()
        
        if df.empty:
            return []
        
        # Filtrar por fecha y hora
        filtered_df = df[(df['Fecha'] == fecha) & (df['Hora'] == hora)]
        
        # Convertir a lista de diccionarios
        return filtered_df.to_dict('records')
    
    def get_events_by_date_range(self, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
        """
        Consulta servicios por rango de fechas
        
        Args:
            fecha_inicio: Fecha de inicio en formato YYYY-MM-DD
            fecha_fin: Fecha de fin en formato YYYY-MM-DD
            
        Returns:
            Lista de diccionarios con los eventos encontrados
        """
        df = self._read_dataframe()
        
        if df.empty:
            return []
        
        # Convertir fechas a datetime para comparación
        df['Fecha_dt'] = pd.to_datetime(df['Fecha'], errors='coerce')
        fecha_inicio_dt = pd.to_datetime(fecha_inicio, errors='coerce')
        fecha_fin_dt = pd.to_datetime(fecha_fin, errors='coerce')
        
        # Filtrar por rango de fechas
        mask = (df['Fecha_dt'] >= fecha_inicio_dt) & (df['Fecha_dt'] <= fecha_fin_dt)
        filtered_df = df[mask].copy()
        
        # Eliminar columna temporal
        filtered_df = filtered_df.drop(columns=['Fecha_dt'])
        
        # Convertir a lista de diccionarios
        return filtered_df.to_dict('records')
    
    def populate_sample_data(self) -> None:
        """
        Pobla el Excel con datos sintéticos de ejemplo para pruebas
        Solo se ejecuta si el Excel está vacío o tiene solo encabezados
        """
        df = self._read_dataframe()
        
        # Verificar si ya hay datos (más de solo encabezados)
        if not df.empty and len(df) > 0:
            return  # Ya hay datos, no poblar
        
        # Datos sintéticos de ejemplo
        from datetime import datetime, timedelta
        
        now = datetime.now()
        sample_data = []
        
        # Lista de datos base
        base_data = [
            ("101202564", "Reinaldo González", "Losartan", "Entrega Domicilio", "Sur", 2, "14:00", "Pendiente"),
            ("523456789", "María Rodríguez", "Insulina", "Entrega Domicilio", "Norte", 1, "10:00", "Pendiente"),
            ("789123456", "Carlos Méndez", "Metformina", "Cita Presencial", "Centro", 3, "15:30", "Pendiente"),
            ("456789123", "Ana López", "Atorvastatina", "Entrega Domicilio", "Sur", -2, "11:00", "Entregado"),
            ("321654987", "Pedro Sánchez", "Omeprazol", "Entrega Domicilio", "Norte", -5, "09:00", "Entregado"),
            ("654321987", "Laura Torres", "Adalimumab", "Cita Presencial", "Centro", 4, "16:00", "Pendiente"),
            ("987654321", "Roberto Jiménez", "Amlodipino", "Entrega Domicilio", "Sur", 5, "13:00", "Pendiente"),
            ("147258369", "Carmen Vásquez", "Levotiroxina", "Entrega Domicilio", "Norte", -1, "14:30", "Cancelado"),
            ("258369147", "Fernando Castro", "Enalapril", "Cita Presencial", "Centro", 6, "10:30", "Pendiente"),
            ("369147258", "Patricia Morales", "Losartan", "Entrega Domicilio", "Sur", 7, "11:30", "Pendiente"),
            ("741852963", "Jorge Ramírez", "Metformina", "Entrega Domicilio", "Norte", 8, "15:00", "Pendiente"),
            ("852963741", "Sofía Herrera", "Insulina", "Cita Presencial", "Centro", -3, "08:30", "Entregado"),
        ]
        
        # Generar datos con ID_Servicio único
        for paciente_id, nombre, medicamento, tipo, sede, dias, hora, estado in base_data:
            sample_data.append({
                "ID_Servicio": str(uuid.uuid4()),
                "Paciente_ID": paciente_id,
                "Nombre_Paciente": nombre,
                "Medicamento": medicamento,
                "Tipo_Servicio": tipo,
                "Sede": sede,
                "Fecha": (now + timedelta(days=dias)).strftime("%Y-%m-%d"),
                "Hora": hora,
                "Estado": estado
            })
        
        # Crear DataFrame con los datos sintéticos
        sample_df = pd.DataFrame(sample_data)
        
        # Escribir al Excel
        self._write_dataframe(sample_df)
    
    def update_event_status(
        self,
        paciente_id: str,
        fecha: str,
        hora: str,
        new_status: EventUpdate
    ) -> Dict[str, Any]:
        """
        Actualiza el estado de un evento específico
        """
        df = self._read_dataframe()
        
        if df.empty:
            raise ExcelServiceError("No hay eventos en el archivo")
        
        # Encontrar la fila
        mask = (
            (df['Paciente_ID'] == paciente_id) &
            (df['Fecha'] == fecha) &
            (df['Hora'] == hora)
        )
        
        if not mask.any():
            raise ExcelServiceError(
                f"No se encontró el servicio para el paciente {paciente_id} "
                f"el {fecha} a las {hora}"
            )
        
        # Actualizar el estado
        df.loc[mask, 'Estado'] = new_status.estado
        
        # Escribir de forma atómica
        self._write_dataframe(df)
        
        return {
            "success": True,
            "message": f"Estado actualizado a '{new_status.estado}'",
            "data": df[mask].to_dict('records')[0]
        }
    
    def find_events_by_criteria(
        self,
        paciente_id: Optional[str] = None,
        nombre: Optional[str] = None,
        fecha: Optional[str] = None,
        hora: Optional[str] = None,
        medicamento: Optional[str] = None,
        estado: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca eventos por criterios flexibles (para manejo de ambigüedad)
        Retorna lista de eventos que coinciden con los criterios
        """
        df = self._read_dataframe()
        
        if df.empty:
            return []
        
        # Construir máscara de filtrado
        mask = pd.Series([True] * len(df))
        
        if paciente_id:
            mask = mask & (df['Paciente_ID'] == paciente_id)
        
        if nombre:
            # Búsqueda insensible a acentos: normalizar tanto el nombre buscado como los nombres en el DF
            normalized_search = self.normalize_name(nombre)
            # Aplicar normalización a cada nombre en el DataFrame y comparar
            df_normalized = df['Nombre_Paciente'].apply(self.normalize_name)
            mask = mask & (df_normalized.str.contains(normalized_search, case=False, na=False))
        
        if fecha:
            mask = mask & (df['Fecha'] == fecha)
        
        if hora:
            mask = mask & (df['Hora'] == hora)
        
        if medicamento:
            mask = mask & (df['Medicamento'].str.contains(medicamento, case=False, na=False))
        
        # Filtrar solo servicios activos (no cancelados) por defecto
        if estado:
            mask = mask & (df['Estado'] == estado)
        else:
            # Por defecto, excluir cancelados para búsquedas
            mask = mask & (df['Estado'] != 'Cancelado')
        
        filtered_df = df[mask]
        
        return filtered_df.to_dict('records')
    
    def cancel_service_by_id(self, servicio_id: str) -> Dict[str, Any]:
        """
        Cancela un servicio específico por ID_Servicio (Soft Delete)
        Cambia el estado a 'Cancelado' en lugar de eliminar la fila
        """
        df = self._read_dataframe()
        
        if df.empty:
            raise ExcelServiceError("No hay eventos en el archivo")
        
        # Normalizar ID_Servicio a string para comparación robusta
        servicio_id_str = str(servicio_id).strip()
        # Convertir columna ID_Servicio a string para comparación
        df['ID_Servicio'] = df['ID_Servicio'].astype(str).str.strip()
        
        # Buscar por ID_Servicio
        mask = df['ID_Servicio'] == servicio_id_str
        
        if not mask.any():
            raise ExcelServiceError(
                f"No se encontró el servicio con ID {servicio_id_str}"
            )
        
        # Verificar que no esté ya cancelado
        if df.loc[mask, 'Estado'].iloc[0] == 'Cancelado':
            raise ExcelServiceError(
                f"El servicio con ID {servicio_id} ya está cancelado"
            )
        
        # Guardar los datos antes de cancelar
        service_data = df[mask].to_dict('records')[0]
        
        # Cambiar estado a Cancelado (Soft Delete)
        df.loc[mask, 'Estado'] = 'Cancelado'
        
        # Escribir de forma atómica
        self._write_dataframe(df)
        
        return {
            "success": True,
            "message": f"Servicio cancelado exitosamente",
            "data": service_data
        }

    def hard_delete_service_by_id(self, servicio_id: str) -> Dict[str, Any]:
        """
        Elimina físicamente una fila del Excel por ID_Servicio (HARD DELETE).
        Útil cuando se requiere borrar el registro completamente del archivo.
        """
        logger.info(f"Iniciando eliminación física de servicio ID: {servicio_id}")
        df = self._read_dataframe()

        if df.empty:
            logger.warning("Intento de eliminar servicio en archivo vacío")
            raise ExcelServiceError("No hay eventos en el archivo")

        # Normalizar ID_Servicio a string para comparación robusta
        servicio_id_str = str(servicio_id).strip()
        # Convertir columna ID_Servicio a string para comparación
        df["ID_Servicio"] = df["ID_Servicio"].astype(str).str.strip()
        
        mask = df["ID_Servicio"] == servicio_id_str
        if not mask.any():
            # Intentar buscar sin espacios y con diferentes formatos
            logger.debug(f"Búsqueda exacta falló, intentando búsqueda normalizada")
            df_ids_normalized = df["ID_Servicio"].str.replace(" ", "").str.lower()
            servicio_id_normalized = servicio_id_str.replace(" ", "").lower()
            mask = df_ids_normalized == servicio_id_normalized
            
            if not mask.any():
                logger.error(f"Servicio no encontrado. ID buscado: {servicio_id_str}")
                raise ExcelServiceError(f"No se encontró el servicio con ID '{servicio_id_str}'. IDs disponibles: {df['ID_Servicio'].head(3).tolist()}")

        deleted_data = df[mask].to_dict("records")[0]
        logger.debug(f"Servicio encontrado: {deleted_data.get('Nombre_Paciente', 'N/A')} - {deleted_data.get('Fecha', 'N/A')}")
        df = df[~mask]
        self._write_dataframe(df)
        
        logger.success(f"Servicio eliminado físicamente del Excel. ID: {servicio_id_str}")
        return {
            "success": True,
            "message": "Servicio eliminado definitivamente del Excel",
            "data": deleted_data,
        }
    
    def delete_event(
        self,
        paciente_id: str,
        fecha: str,
        hora: str
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Usar cancel_service_by_id en su lugar
        Mantenido por compatibilidad, pero ahora hace soft delete
        """
        # Buscar el servicio
        events = self.find_events_by_criteria(
            paciente_id=paciente_id,
            fecha=fecha,
            hora=hora
        )
        
        if not events:
            raise ExcelServiceError(
                f"No se encontró el servicio para el paciente {paciente_id} "
                f"el {fecha} a las {hora}"
            )
        
        if len(events) > 1:
            raise ExcelServiceError(
                f"Se encontraron múltiples servicios. Use cancel_service_by_id con el ID_Servicio específico."
            )
        
        # Cancelar el servicio encontrado
        servicio_id = events[0]['ID_Servicio']
        return self.cancel_service_by_id(servicio_id)


# Instancia global del servicio
excel_service = ExcelService()


