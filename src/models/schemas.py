"""
Esquemas Pydantic para validación de datos de servicios farmacéuticos.

Este módulo define todos los modelos de datos utilizados en la aplicación,
garantizando validación de tipos y reglas de negocio mediante Pydantic.
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re

from src.config import settings
from src.models.exceptions import ValidationError


class PharmaEvent(BaseModel):
    """
    Modelo para eventos de servicios farmacéuticos de Audifarma.
    
    Representa un servicio completo con toda la información necesaria
    para agendar una entrega o cita presencial.
    
    Attributes:
        paciente_id: Documento de identidad del paciente (cédula, 5-20 caracteres)
        nombre: Nombre completo del paciente (obligatorio, 2-100 caracteres)
        medicamento: Nombre del medicamento o tratamiento
        tipo_servicio: Tipo de atención ("Entrega Domicilio" o "Cita Presencial")
        sede: Sede de Audifarma donde se realizará el servicio
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM (24 horas)
        estado: Estado del servicio (Pendiente, Entregado, Cancelado)
    """
    paciente_id: str = Field(
        ...,
        description="Documento de identidad del paciente (cédula)",
        min_length=5,
        max_length=20,
        examples=["1234567890", "987654321"]
    )
    nombre: str = Field(
        ...,
        description="Nombre completo del paciente (OBLIGATORIO)",
        min_length=2,
        max_length=100,
        examples=["Juan Pérez", "María González"]
    )
    medicamento: str = Field(
        description="Nombre del medicamento o tratamiento",
        min_length=2,
        max_length=200
    )
    tipo_servicio: Literal["Entrega Domicilio", "Cita Presencial"] = Field(
        description="Tipo de atención: 'Entrega Domicilio' o 'Cita Presencial'"
    )
    sede: str = Field(
        description="Sede de Audifarma donde se realizará el servicio",
        min_length=2,
        max_length=100
    )
    fecha: str = Field(
        description="Fecha en formato YYYY-MM-DD"
    )
    hora: str = Field(
        description="Hora en formato HH:MM (24 horas)"
    )
    estado: str = Field(
        default=settings.ESTADO_DEFAULT,
        description="Estado del servicio: Pendiente, Entregado o Cancelado"
    )
    
    @field_validator('fecha')
    @classmethod
    def validate_fecha(cls, v: str) -> str:
        """Valida que la fecha esté en formato YYYY-MM-DD"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('La fecha debe estar en formato YYYY-MM-DD')
    
    @field_validator('hora')
    @classmethod
    def validate_hora(cls, v: str) -> str:
        """Valida que la hora esté en formato HH:MM (24 horas)"""
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('La hora debe estar en formato HH:MM (24 horas, ej: 14:30)')
        return v
    
    @field_validator('estado')
    @classmethod
    def validate_estado(cls, v: str) -> str:
        """Valida que el estado sea uno de los permitidos"""
        if v not in settings.ESTADOS:
            raise ValueError(f'El estado debe ser uno de: {", ".join(settings.ESTADOS)}')
        return v
    
    @field_validator('tipo_servicio', mode='before')
    @classmethod
    def validate_tipo_servicio(cls, v: str) -> str:
        """Normaliza el tipo de servicio"""
        if isinstance(v, str):
            v = v.strip()
            # Permitir variaciones comunes
            if v.lower() in ['domicilio', 'entrega domicilio', 'entrega a domicilio']:
                return "Entrega Domicilio"
            elif v.lower() in ['presencial', 'cita presencial', 'cita']:
                return "Cita Presencial"
        return v
    
    class Config:
        """Configuración del modelo"""
        json_schema_extra = {
            "example": {
                "paciente_id": "1234567890",
                "nombre": "Juan Pérez",
                "medicamento": "Insulina",
                "tipo_servicio": "Entrega Domicilio",
                "sede": "Sede Norte",
                "fecha": "2024-12-25",
                "hora": "14:30",
                "estado": "Pendiente"
            }
        }


class EventUpdate(BaseModel):
    """Esquema para actualizar el estado de un evento"""
    estado: str = Field(
        description="Nuevo estado: Pendiente, Entregado o Cancelado"
    )
    
    @field_validator('estado')
    @classmethod
    def validate_estado(cls, v: str) -> str:
        """Valida que el estado sea uno de los permitidos"""
        if v not in settings.ESTADOS:
            raise ValueError(f'El estado debe ser uno de: {", ".join(settings.ESTADOS)}')
        return v


class DateRangeQuerySchema(BaseModel):
    """Esquema para consultas por rango de fechas"""
    fecha_inicio: str = Field(
        description="Fecha de inicio en formato YYYY-MM-DD"
    )
    fecha_fin: str = Field(
        description="Fecha de fin en formato YYYY-MM-DD"
    )
    
    @field_validator('fecha_inicio', 'fecha_fin')
    @classmethod
    def validate_fecha(cls, v: str) -> str:
        """Valida que la fecha esté en formato YYYY-MM-DD"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('La fecha debe estar en formato YYYY-MM-DD')


class DateTimeQuerySchema(BaseModel):
    """Esquema para consultas por fecha y hora específica"""
    fecha: str = Field(
        description="Fecha en formato YYYY-MM-DD"
    )
    hora: str = Field(
        description="Hora en formato HH:MM (24 horas)"
    )
    
    @field_validator('fecha')
    @classmethod
    def validate_fecha(cls, v: str) -> str:
        """Valida que la fecha esté en formato YYYY-MM-DD"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('La fecha debe estar en formato YYYY-MM-DD')
    
    @field_validator('hora')
    @classmethod
    def validate_hora(cls, v: str) -> str:
        """Valida que la hora esté en formato HH:MM (24 horas)"""
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('La hora debe estar en formato HH:MM (24 horas, ej: 14:30)')
        return v


class UnifiedQuerySchema(BaseModel):
    """Esquema unificado para consultas flexibles"""
    fecha: Optional[str] = Field(
        default=None,
        description="Fecha específica en formato YYYY-MM-DD (opcional)"
    )
    fecha_inicio: Optional[str] = Field(
        default=None,
        description="Fecha de inicio del rango en formato YYYY-MM-DD (opcional)"
    )
    fecha_fin: Optional[str] = Field(
        default=None,
        description="Fecha de fin del rango en formato YYYY-MM-DD (opcional)"
    )
    hora: Optional[str] = Field(
        default=None,
        description="Hora específica en formato HH:MM (opcional, requiere fecha)"
    )

