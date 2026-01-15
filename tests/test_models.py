"""
Tests para modelos Pydantic (schemas.py)
"""
import pytest
from pydantic import ValidationError

from src.models.schemas import PharmaEvent, EventUpdate, UnifiedQuerySchema
from src.config import settings


class TestPharmaEvent:
    """Tests para el modelo PharmaEvent"""
    
    def test_valid_event(self):
        """Test que un evento válido se crea correctamente"""
        event = PharmaEvent(
            paciente_id="1234567890",
            nombre="Juan Pérez",
            medicamento="Insulina",
            tipo_servicio="Entrega Domicilio",
            sede="Sede Norte",
            fecha="2024-12-25",
            hora="14:30"
        )
        
        assert event.paciente_id == "1234567890"
        assert event.nombre == "Juan Pérez"
        assert event.medicamento == "Insulina"
        assert event.estado == settings.ESTADO_DEFAULT
    
    def test_invalid_fecha_format(self):
        """Test que fecha inválida lanza ValidationError"""
        with pytest.raises(ValidationError):
            PharmaEvent(
                paciente_id="1234567890",
                nombre="Juan Pérez",
                medicamento="Insulina",
                tipo_servicio="Entrega Domicilio",
                sede="Sede Norte",
                fecha="25-12-2024",  # Formato incorrecto
                hora="14:30"
            )
    
    def test_invalid_hora_format(self):
        """Test que hora inválida lanza ValidationError"""
        with pytest.raises(ValidationError):
            PharmaEvent(
                paciente_id="1234567890",
                nombre="Juan Pérez",
                medicamento="Insulina",
                tipo_servicio="Entrega Domicilio",
                sede="Sede Norte",
                fecha="2024-12-25",
                hora="2:30 PM"  # Formato incorrecto
            )
    
    def test_empty_nombre(self):
        """Test que nombre vacío lanza ValidationError"""
        with pytest.raises(ValidationError):
            PharmaEvent(
                paciente_id="1234567890",
                nombre="",  # Nombre vacío
                medicamento="Insulina",
                tipo_servicio="Entrega Domicilio",
                sede="Sede Norte",
                fecha="2024-12-25",
                hora="14:30"
            )
    
    def test_invalid_estado(self):
        """Test que estado inválido lanza ValidationError"""
        with pytest.raises(ValidationError):
            PharmaEvent(
                paciente_id="1234567890",
                nombre="Juan Pérez",
                medicamento="Insulina",
                tipo_servicio="Entrega Domicilio",
                sede="Sede Norte",
                fecha="2024-12-25",
                hora="14:30",
                estado="Invalid"  # Estado inválido
            )


class TestEventUpdate:
    """Tests para el modelo EventUpdate"""
    
    def test_valid_update(self):
        """Test que actualización válida se crea correctamente"""
        update = EventUpdate(estado="Entregado")
        assert update.estado == "Entregado"
    
    def test_invalid_estado(self):
        """Test que estado inválido lanza ValidationError"""
        with pytest.raises(ValidationError):
            EventUpdate(estado="Invalid")


class TestUnifiedQuerySchema:
    """Tests para el modelo UnifiedQuerySchema"""
    
    def test_query_by_date(self):
        """Test consulta por fecha específica"""
        query = UnifiedQuerySchema(fecha="2024-12-25")
        assert query.fecha == "2024-12-25"
        assert query.fecha_inicio is None
        assert query.fecha_fin is None
    
    def test_query_by_range(self):
        """Test consulta por rango de fechas"""
        query = UnifiedQuerySchema(
            fecha_inicio="2024-12-01",
            fecha_fin="2024-12-31"
        )
        assert query.fecha_inicio == "2024-12-01"
        assert query.fecha_fin == "2024-12-31"
        assert query.fecha is None

