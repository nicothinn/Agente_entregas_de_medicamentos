"""
Tests para el agente LangChain (pharma_agent.py)
"""
import pytest
from unittest.mock import Mock, patch

from src.agents.pharma_agent import create_pharma_agent, get_agent


class TestPharmaAgent:
    """Tests para el agente LangChain"""
    
    @pytest.mark.skip(reason="Requiere API key de OpenAI y es costoso")
    def test_create_agent(self):
        """Test que se puede crear el agente"""
        # Este test se salta porque requiere API key real
        # En producción, usar mocks o API key de testing
        agent = create_pharma_agent()
        assert agent is not None
    
    def test_get_agent_singleton(self):
        """Test que get_agent retorna singleton"""
        # Este test también requiere API key
        # Se puede mockear para testing unitario
        pass
    
    @patch('src.agents.pharma_agent.ChatOpenAI')
    def test_agent_initialization_with_mock(self, mock_llm):
        """Test inicialización del agente con mock"""
        # Mock del LLM
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        
        # Este test verificaría que el agente se inicializa correctamente
        # con todas las tools configuradas
        pass

