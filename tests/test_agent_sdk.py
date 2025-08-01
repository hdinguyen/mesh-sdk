"""Tests for Agent SDK."""

from unittest.mock import patch

import pytest

from mesh_agent import AgentSDK
from mesh_agent.src.exceptions import (
    AgentManifestError,
    MissingRequiredFieldsError,
)


class TestAgentSDK:
    """Test cases for AgentSDK class."""

    def test_init_with_required_fields(self):
        """Test SDK initialization with required fields."""
        def dummy_process(messages):
            return {"content": "processed"}

        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )

        assert sdk.agent_name == "test_agent"
        assert sdk.agent_type == "custom"
        assert sdk.capabilities == ["text_processing"]
        assert sdk.process_function == dummy_process
        assert sdk.version == "1.0.0"
        assert sdk.platform_url == "http://localhost:8000"
        assert callable(sdk.process_function)

    def test_init_with_optional_fields(self):
        """Test SDK initialization with optional fields."""
        def dummy_process(messages):
            return {"content": "processed"}

        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="dspy",
            capabilities=["text_generation", "reasoning"],
            process_function=dummy_process,
            platform_url="http://custom-platform:9000",
            version="2.0.0",
            description="Test agent for development",
            tags=["test", "development"],
            contact="test@example.com"
        )

        assert sdk.agent_name == "test_agent"
        assert sdk.agent_type == "dspy"
        assert sdk.capabilities == ["text_generation", "reasoning"]
        assert sdk.version == "2.0.0"
        assert sdk.description == "Test agent for development"
        assert sdk.tags == ["test", "development"]
        assert sdk.contact == "test@example.com"
        assert sdk.platform_url == "http://custom-platform:9000"

    def test_init_missing_required_fields(self):
        """Test SDK initialization with missing required fields."""
        with pytest.raises(MissingRequiredFieldsError) as exc_info:
            AgentSDK(
                agent_name="test_agent",
                agent_type="custom",
                capabilities=[],  # Empty capabilities should fail
                process_function=None  # Missing process function
            )

        assert "Missing required fields" in str(exc_info.value)
        assert exc_info.value.error_code == "REG_004"

    def test_init_invalid_field_types(self):
        """Test SDK initialization with invalid field types."""
        with pytest.raises(AgentManifestError) as exc_info:
            AgentSDK(
                agent_name="",  # Empty string should fail
                agent_type="custom",
                capabilities=["text_processing"],
                process_function=lambda x: x
            )

        assert exc_info.value.error_code == "REG_003"

    def test_platform_url_priority(self):
        """Test platform URL resolution priority."""
        def dummy_process(messages):
            return {"content": "processed"}

        # Test environment variable takes priority
        with patch.dict("os.environ", {"PLATFORM_BASE_URL": "http://env-platform:8080"}):
            sdk = AgentSDK(
                agent_name="test_agent",
                agent_type="custom",
                capabilities=["text_processing"],
                process_function=dummy_process,
                platform_url="http://param-platform:9000"
            )
            assert sdk.platform_url == "http://env-platform:8080"

        # Test parameter takes priority over default
        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process,
            platform_url="http://param-platform:9000"
        )
        assert sdk.platform_url == "http://param-platform:9000"

        # Test default value
        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )
        assert sdk.platform_url == "http://localhost:8000"

    @patch("portpicker.pick_unused_port")
    def test_port_allocation(self, mock_portpicker):
        """Test automatic port allocation."""
        mock_portpicker.return_value = 8001

        def dummy_process(messages):
            return {"content": "processed"}

        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )

        assert sdk.port == 8001
        assert sdk.acp_base_url == "http://localhost:8001"
        mock_portpicker.assert_called_once()

    def test_auth_token_generation(self):
        """Test automatic auth token generation."""
        def dummy_process(messages):
            return {"content": "processed"}

        sdk1 = AgentSDK(
            agent_name="test_agent1",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )

        sdk2 = AgentSDK(
            agent_name="test_agent2",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )

        # Tokens should be unique and non-empty
        assert sdk1.auth_token != sdk2.auth_token
        assert len(sdk1.auth_token) > 0
        assert len(sdk2.auth_token) > 0

    def test_field_validation(self):
        """Test field validation logic."""
        def dummy_process(messages):
            return {"content": "processed"}

        sdk = AgentSDK(
            agent_name="test_agent",
            agent_type="custom",
            capabilities=["text_processing"],
            process_function=dummy_process
        )

        # Test string validation
        assert sdk._validate_field_value("test", {"type": "string"}) == True
        assert sdk._validate_field_value("", {"type": "string"}) == False

        # Test array validation
        assert sdk._validate_field_value(["item"], {"type": "array"}) == True
        assert sdk._validate_field_value([], {"type": "array"}) == False

        # Test function validation
        assert sdk._validate_field_value(lambda x: x, {"type": "function"}) == True
        assert sdk._validate_field_value("not_a_function", {"type": "function"}) == False
