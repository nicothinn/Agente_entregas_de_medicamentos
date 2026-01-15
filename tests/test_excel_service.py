"""
Tests para el servicio Excel (excel_service.py)
"""
import pytest
import tempfile
from pathlib import Path
import pandas as pd

from src.services.excel_service import ExcelService, ExcelLockedError, ExcelServiceError
from src.models.schemas import PharmaEvent
from src.models.exceptions import ExcelLockedError as NewExcelLockedError


class TestExcelService:
    """Tests para ExcelService"""
    
    @pytest.fixture
    def temp_excel_file(self):
        """Crea un archivo Excel temporal para testing"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        # Limpiar después del test
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    def excel_service(self, temp_excel_file):
        """Crea una instancia de ExcelService con archivo temporal"""
        return ExcelService(file_path=temp_excel_file)
    
    @pytest.fixture
    def sample_event(self):
        """Crea un evento de ejemplo"""
        return PharmaEvent(
            paciente_id="1234567890",
            nombre="Juan Pérez",
            medicamento="Insulina",
            tipo_servicio="Entrega Domicilio",
            sede="Sede Norte",
            fecha="2024-12-25",
            hora="14:30"
        )
    
    def test_create_service(self, excel_service):
        """Test que se puede crear una instancia del servicio"""
        assert excel_service is not None
        assert excel_service.file_path.exists()
    
    def test_add_event(self, excel_service, sample_event):
        """Test agregar un evento"""
        result = excel_service.add_pharma_event(sample_event)
        
        assert result["success"] is True
        assert "servicio_id" in result
        assert result["servicio_id"] is not None
    
    def test_get_all_events(self, excel_service, sample_event):
        """Test obtener todos los eventos"""
        # Agregar un evento primero
        excel_service.add_pharma_event(sample_event)
        
        # Obtener todos
        df = excel_service.get_all_events()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["Nombre_Paciente"] == "Juan Pérez"
    
    def test_find_events_by_criteria(self, excel_service, sample_event):
        """Test buscar eventos por criterios"""
        # Agregar un evento
        excel_service.add_pharma_event(sample_event)
        
        # Buscar por nombre
        events = excel_service.find_events_by_criteria(nombre="Juan Pérez")
        
        assert len(events) == 1
        assert events[0]["Nombre_Paciente"] == "Juan Pérez"
    
    def test_normalize_name(self):
        """Test normalización de nombres (insensible a acentos)"""
        normalized = ExcelService.normalize_name("Nicolás")
        assert normalized == "nicolas"
        
        normalized2 = ExcelService.normalize_name("José María")
        assert normalized2 == "jose maria"
        
        # Debe ser case-insensitive
        assert ExcelService.normalize_name("NICOLÁS") == "nicolas"
    
    def test_hard_delete_service_by_id(self, excel_service, sample_event):
        """Test eliminar servicio por ID"""
        # Agregar evento
        result = excel_service.add_pharma_event(sample_event)
        servicio_id = result["servicio_id"]
        
        # Verificar que existe
        df_before = excel_service.get_all_events()
        assert len(df_before) == 1
        
        # Eliminar
        delete_result = excel_service.hard_delete_service_by_id(servicio_id)
        assert delete_result["success"] is True
        
        # Verificar que se eliminó
        df_after = excel_service.get_all_events()
        assert len(df_after) == 0
    
    def test_hard_delete_nonexistent_id(self, excel_service):
        """Test que eliminar ID inexistente lanza excepción"""
        with pytest.raises(ExcelServiceError):
            excel_service.hard_delete_service_by_id("nonexistent-id")

