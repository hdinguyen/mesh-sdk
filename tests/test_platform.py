"""Tests for Platform Core."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from mesh_platform import PlatformCore, RedisClient


class TestPlatformCore:
    """Test cases for PlatformCore class."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing."""
        mock_client = Mock(spec=RedisClient)
        return mock_client

    @pytest.fixture
    def platform(self, mock_redis_client):
        """Create platform instance with mocked Redis."""
        with patch(
            "mesh_platform.src.platform.RedisClient", return_value=mock_redis_client
        ):
            platform = PlatformCore()
            return platform

    @pytest.fixture
    def client(self, platform):
        """Create test client."""
        return TestClient(platform.app)

    def test_register_agent_success(self, client, platform):
        """Test successful agent registration."""
        platform.redis_client.register_agent.return_value = True

        agent_data = {
            "agent_name": "test_agent",
            "agent_type": "custom",
            "capabilities": ["text_processing"],
            "acp_base_url": "http://localhost:8001",
            "auth_token": "test_token_123",
            "version": "1.0.0",
        }

        with patch.object(platform, "_verify_agent_connection") as mock_verify:
            mock_verify.return_value = None  # Successful verification

            response = client.post("/platform/agents/register", json=agent_data)

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Agent registered successfully"
            assert data["agent_name"] == "test_agent"
            assert data["status"] == "active"

            platform.redis_client.register_agent.assert_called_once()
            mock_verify.assert_called_once()

    def test_register_agent_missing_fields(self, client, platform):
        """Test agent registration with missing required fields."""
        agent_data = {
            "agent_name": "test_agent",
            # Missing required fields
        }

        response = client.post("/platform/agents/register", json=agent_data)

        assert response.status_code == 400
        assert "Missing required fields" in response.json()["detail"]

    def test_register_agent_duplicate_name(self, client, platform):
        """Test agent registration with duplicate name."""
        platform.redis_client.register_agent.return_value = False  # Already exists

        agent_data = {
            "agent_name": "existing_agent",
            "agent_type": "custom",
            "capabilities": ["text_processing"],
            "acp_base_url": "http://localhost:8001",
            "auth_token": "test_token_123",
        }

        response = client.post("/platform/agents/register", json=agent_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_register_agent_verification_failure(self, client, platform):
        """Test agent registration with verification failure."""
        platform.redis_client.register_agent.return_value = True
        platform.redis_client.delete_agent.return_value = True

        agent_data = {
            "agent_name": "test_agent",
            "agent_type": "custom",
            "capabilities": ["text_processing"],
            "acp_base_url": "http://localhost:8001",
            "auth_token": "test_token_123",
        }

        with patch.object(platform, "_verify_agent_connection") as mock_verify:
            mock_verify.side_effect = Exception("Connection failed")

            response = client.post("/platform/agents/register", json=agent_data)

            assert response.status_code == 400
            assert "Agent verification failed" in response.json()["detail"]

            # Should cleanup failed registration
            platform.redis_client.delete_agent.assert_called_once_with("test_agent")

    def test_list_agents(self, client, platform):
        """Test listing all agents."""
        mock_agents = [
            {
                "agent_name": "agent1",
                "agent_type": "custom",
                "capabilities": ["text_processing"],
                "version": "1.0.0",
                "description": "Test agent 1",
                "tags": ["test"],
                "contact": "test@example.com",
            },
            {
                "agent_name": "agent2",
                "agent_type": "dspy",
                "capabilities": ["reasoning"],
                "version": "2.0.0",
                "description": "Test agent 2",
                "tags": ["production"],
                "contact": "prod@example.com",
            },
        ]

        platform.redis_client.list_agents.return_value = mock_agents

        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 2

        # Check ACP format conversion
        agent1 = data["agents"][0]
        assert agent1["name"] == "agent1"
        assert agent1["capabilities"] == ["text_processing"]
        assert agent1["version"] == "1.0.0"

    def test_get_agent_manifest(self, client, platform):
        """Test getting specific agent manifest."""
        mock_agent = {
            "agent_name": "test_agent",
            "agent_type": "custom",
            "capabilities": ["text_processing"],
            "version": "1.0.0",
            "description": "Test agent",
            "tags": ["test"],
            "contact": "test@example.com",
            "status": "active",
        }

        platform.redis_client.get_agent.return_value = mock_agent

        response = client.get("/agents/test_agent")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_agent"
        assert data["capabilities"] == ["text_processing"]
        assert data["status"] == "active"

    def test_get_agent_manifest_not_found(self, client, platform):
        """Test getting manifest for non-existent agent."""
        platform.redis_client.get_agent.return_value = None

        response = client.get("/agents/nonexistent_agent")

        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]

    def test_create_run(self, client, platform):
        """Test creating an agent run."""
        mock_agent = {
            "agent_name": "test_agent",
            "acp_base_url": "http://localhost:8001",
            "auth_token": "test_token",
        }

        platform.redis_client.get_agent.return_value = mock_agent

        run_data = {"agent": "test_agent", "input": [{"content": "Hello, agent!"}]}

        mock_output = [{"content": "Hello, human!"}]

        with patch.object(platform, "_execute_agent_run") as mock_execute:
            mock_execute.return_value = mock_output

            response = client.post("/runs", json=run_data)

            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
            assert data["status"] == "completed"
            assert data["output"] == mock_output

            mock_execute.assert_called_once()

    def test_create_run_agent_not_found(self, client, platform):
        """Test creating run for non-existent agent."""
        platform.redis_client.get_agent.return_value = None

        run_data = {
            "agent": "nonexistent_agent",
            "input": [{"content": "Hello, agent!"}],
        }

        response = client.post("/runs", json=run_data)

        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]

    def test_create_run_missing_fields(self, client, platform):
        """Test creating run with missing required fields."""
        run_data = {
            "agent": "test_agent"
            # Missing input field
        }

        response = client.post("/runs", json=run_data)

        assert response.status_code == 400
        assert "Missing required fields" in response.json()["detail"]


class TestRedisClient:
    """Test cases for RedisClient class."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        return mock_redis

    @pytest.fixture
    def redis_client(self, mock_redis):
        """Create RedisClient with mocked Redis."""
        with patch("redis.Redis", return_value=mock_redis):
            client = RedisClient()
            client.redis = mock_redis
            return client

    def test_register_agent_success(self, redis_client):
        """Test successful agent registration."""
        redis_client.redis.exists.return_value = False  # Agent doesn't exist
        redis_client.redis.hset.return_value = True
        redis_client.redis.sadd.return_value = True

        agent_data = {
            "agent_name": "test_agent",
            "agent_type": "custom",
            "capabilities": '["text_processing"]',
        }

        result = redis_client.register_agent(agent_data)

        assert result == True
        redis_client.redis.exists.assert_called_with("agent:test_agent")
        redis_client.redis.hset.assert_called_once()
        redis_client.redis.sadd.assert_called_with("agents", "test_agent")

    def test_register_agent_already_exists(self, redis_client):
        """Test registering agent that already exists."""
        redis_client.redis.exists.return_value = True  # Agent exists

        agent_data = {
            "agent_name": "existing_agent",
            "agent_type": "custom",
            "capabilities": '["text_processing"]',
        }

        result = redis_client.register_agent(agent_data)

        assert result == False
        redis_client.redis.hset.assert_not_called()

    def test_get_agent_success(self, redis_client):
        """Test getting agent data."""
        redis_client.redis.exists.return_value = True
        redis_client.redis.hgetall.return_value = {
            "agent_name": "test_agent",
            "agent_type": "custom",
            "capabilities": '["text_processing"]',
            "status": "active",
        }

        result = redis_client.get_agent("test_agent")

        assert result is not None
        assert result["agent_name"] == "test_agent"
        assert result["capabilities"] == ["text_processing"]  # JSON parsed

    def test_get_agent_not_found(self, redis_client):
        """Test getting non-existent agent."""
        redis_client.redis.exists.return_value = False

        result = redis_client.get_agent("nonexistent_agent")

        assert result is None

    def test_list_agents(self, redis_client):
        """Test listing all agents."""
        redis_client.redis.smembers.return_value = {"agent1", "agent2"}

        # Mock get_agent calls
        def mock_get_agent(name):
            if name == "agent1":
                return {"agent_name": "agent1", "status": "active"}
            if name == "agent2":
                return {"agent_name": "agent2", "status": "inactive"}
            return None

        redis_client.get_agent = Mock(side_effect=mock_get_agent)

        result = redis_client.list_agents()

        assert len(result) == 2
        agent_names = [agent["agent_name"] for agent in result]
        assert "agent1" in agent_names
        assert "agent2" in agent_names

    def test_delete_agent(self, redis_client):
        """Test deleting an agent."""
        redis_client.redis.exists.return_value = True
        redis_client.redis.delete.return_value = 1
        redis_client.redis.srem.return_value = 1

        result = redis_client.delete_agent("test_agent")

        assert result == True
        redis_client.redis.delete.assert_any_call("agent:test_agent")
        redis_client.redis.delete.assert_any_call("queue:test_agent")
        redis_client.redis.srem.assert_called_with("agents", "test_agent")


class TestFlowImportExport:
    """Test cases for Flow Import/Export functionality."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing."""
        mock_client = Mock(spec=RedisClient)
        return mock_client

    @pytest.fixture
    def platform(self, mock_redis_client):
        """Create platform instance with mocked Redis."""
        with patch(
            "mesh_platform.src.platform.RedisClient", return_value=mock_redis_client
        ):
            platform = PlatformCore()
            return platform

    @pytest.fixture
    def client(self, platform):
        """Create test client."""
        return TestClient(platform.app)

    @pytest.fixture
    def sample_flow_data(self):
        """Sample flow data for testing."""
        return {
            "name": "Test Workflow",
            "description": "A test workflow for import/export",
            "agents": [
                {
                    "agent_name": "text_extractor",
                    "upstream_agents": [],
                    "required": True,
                    "description": "Extracts text from documents"
                },
                {
                    "agent_name": "sentiment_analyzer",
                    "upstream_agents": ["text_extractor"],
                    "required": True,
                    "description": "Analyzes sentiment of text"
                }
            ]
        }

    def test_export_flow_success(self, client, platform, sample_flow_data):
        """Test successful flow export."""
        flow_id = "test-flow-123"
        
        # Mock export data
        export_data = {
            **sample_flow_data,
            "metadata": {
                "exported_at": "2025-01-15T10:30:00Z",
                "platform_version": "1.0.0",
                "agent_count": 2,
                "original_flow_id": flow_id
            }
        }
        
        platform.redis_client.export_flow_data.return_value = export_data

        response = client.get(f"/flows/{flow_id}/export")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert data["description"] == "A test workflow for import/export"
        assert len(data["agents"]) == 2
        assert "metadata" in data
        assert data["metadata"]["agent_count"] == 2
        
        platform.redis_client.export_flow_data.assert_called_once_with(flow_id, platform_version="1.0.0")

    def test_export_flow_not_found(self, client, platform):
        """Test exporting non-existent flow."""
        flow_id = "nonexistent-flow"
        
        platform.redis_client.export_flow_data.return_value = None

        response = client.get(f"/flows/{flow_id}/export")

        assert response.status_code == 404
        assert "Flow not found" in response.json()["detail"]

    def test_import_flow_success(self, client, platform, sample_flow_data):
        """Test successful flow import."""
        flow_id = "imported-flow-123"
        warnings = ["Agent 'sentiment_analyzer' not currently registered"]
        
        platform.redis_client.import_flow_data.return_value = (flow_id, warnings)

        import_request = {
            "flow_data": sample_flow_data,
            "validate_agents": True,
            "overwrite_existing": False
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 201
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["name"] == "Test Workflow"
        assert data["status"] == "imported"
        assert data["agents_added"] == 2
        assert data["warnings"] == warnings
        assert "message" in data
        
        platform.redis_client.import_flow_data.assert_called_once_with(
            sample_flow_data, True, False
        )

    def test_import_flow_missing_flow_data(self, client, platform):
        """Test importing flow with missing flow_data field."""
        import_request = {
            "validate_agents": True,
            "overwrite_existing": False
            # Missing flow_data
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 400
        assert "Missing required field: flow_data" in response.json()["detail"]

    def test_import_flow_invalid_flow_data(self, client, platform):
        """Test importing flow with invalid flow_data structure."""
        import_request = {
            "flow_data": {
                # Missing name field
                "description": "Invalid flow data"
            },
            "validate_agents": True,
            "overwrite_existing": False
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 400
        assert "Invalid flow_data" in response.json()["detail"]

    def test_import_flow_name_conflict(self, client, platform, sample_flow_data):
        """Test importing flow with name conflict."""
        platform.redis_client.import_flow_data.side_effect = ValueError("Flow 'Test Workflow' already exists")

        import_request = {
            "flow_data": sample_flow_data,
            "validate_agents": True,
            "overwrite_existing": False
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_import_flow_validation_error(self, client, platform, sample_flow_data):
        """Test importing flow with validation error."""
        platform.redis_client.import_flow_data.side_effect = ValueError("Invalid agent configuration")

        import_request = {
            "flow_data": sample_flow_data,
            "validate_agents": True,
            "overwrite_existing": False
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 400
        assert "Invalid agent configuration" in response.json()["detail"]

    def test_import_flow_with_overwrite(self, client, platform, sample_flow_data):
        """Test importing flow with overwrite enabled."""
        flow_id = "overwritten-flow-123"
        warnings = []
        
        platform.redis_client.import_flow_data.return_value = (flow_id, warnings)

        import_request = {
            "flow_data": sample_flow_data,
            "validate_agents": False,
            "overwrite_existing": True
        }

        response = client.post("/flows/import", json=import_request)

        assert response.status_code == 201
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["warnings"] == []
        
        platform.redis_client.import_flow_data.assert_called_once_with(
            sample_flow_data, False, True
        )


class TestRedisClientFlowImportExport:
    """Test cases for RedisClient flow import/export methods."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        return mock_redis

    @pytest.fixture
    def redis_client(self, mock_redis):
        """Create RedisClient with mocked Redis."""
        with patch("redis.Redis", return_value=mock_redis):
            client = RedisClient()
            client.redis = mock_redis
            return client

    @pytest.fixture
    def sample_flow_data(self):
        """Sample flow data for testing."""
        return {
            "flow_id": "test-flow-123",
            "name": "Test Workflow",
            "description": "A test workflow",
            "agents": [
                {
                    "agent_name": "text_extractor",
                    "upstream_agents": [],
                    "required": True,
                    "description": "Extracts text"
                }
            ]
        }

    def test_export_flow_data_success(self, redis_client, sample_flow_data):
        """Test successful flow data export."""
        flow_id = "test-flow-123"
        
        redis_client.get_flow = Mock(return_value=sample_flow_data)

        result = redis_client.export_flow_data(flow_id, "1.0.0")

        assert result is not None
        assert result["name"] == "Test Workflow"
        assert result["description"] == "A test workflow"
        assert len(result["agents"]) == 1
        assert "metadata" in result
        assert result["metadata"]["platform_version"] == "1.0.0"
        assert result["metadata"]["original_flow_id"] == flow_id

    def test_export_flow_data_not_found(self, redis_client):
        """Test exporting non-existent flow data."""
        flow_id = "nonexistent-flow"
        
        redis_client.get_flow = Mock(return_value=None)

        result = redis_client.export_flow_data(flow_id)

        assert result is None

    def test_flow_name_exists_true(self, redis_client):
        """Test flow name exists check returns True."""
        redis_client.redis.smembers.return_value = {"flow1", "flow2"}
        redis_client.redis.hgetall.side_effect = [
            {"name": "Existing Flow"},
            {"name": "Another Flow"}
        ]

        result = redis_client.flow_name_exists("Existing Flow")

        assert result == True

    def test_flow_name_exists_false(self, redis_client):
        """Test flow name exists check returns False."""
        redis_client.redis.smembers.return_value = {"flow1", "flow2"}
        redis_client.redis.hgetall.side_effect = [
            {"name": "Existing Flow"},
            {"name": "Another Flow"}
        ]

        result = redis_client.flow_name_exists("Non-existent Flow")

        assert result == False

    def test_import_flow_data_success(self, redis_client):
        """Test successful flow data import."""
        flow_data = {
            "name": "Imported Flow",
            "description": "An imported workflow",
            "agents": [
                {
                    "agent_name": "test_agent",
                    "upstream_agents": [],
                    "required": True,
                    "description": "Test agent"
                }
            ]
        }
        
        redis_client.flow_name_exists = Mock(return_value=False)
        redis_client.create_flow = Mock(return_value="new-flow-id")
        redis_client.add_agent_to_flow = Mock(return_value=True)
        redis_client.get_agent = Mock(return_value={"agent_name": "test_agent"})

        flow_id, warnings = redis_client.import_flow_data(flow_data, True, False)

        assert flow_id == "new-flow-id"
        assert warnings == []
        redis_client.create_flow.assert_called_once_with(
            name="Imported Flow",
            description="An imported workflow",
            imported_from="json_import"
        )

    def test_import_flow_data_with_warnings(self, redis_client):
        """Test flow data import with agent validation warnings."""
        flow_data = {
            "name": "Imported Flow",
            "agents": [
                {
                    "agent_name": "missing_agent",
                    "upstream_agents": [],
                    "required": True
                }
            ]
        }
        
        redis_client.flow_name_exists = Mock(return_value=False)
        redis_client.create_flow = Mock(return_value="new-flow-id")
        redis_client.add_agent_to_flow = Mock(return_value=True)
        redis_client.get_agent = Mock(return_value=None)  # Agent not found

        flow_id, warnings = redis_client.import_flow_data(flow_data, True, False)

        assert flow_id == "new-flow-id"
        assert len(warnings) == 1
        assert "missing_agent" in warnings[0]
        assert "not currently registered" in warnings[0]

    def test_import_flow_data_name_conflict(self, redis_client):
        """Test flow data import with name conflict."""
        flow_data = {
            "name": "Existing Flow"
        }
        
        redis_client.flow_name_exists = Mock(return_value=True)

        with pytest.raises(ValueError, match="already exists"):
            redis_client.import_flow_data(flow_data, True, False)

    def test_import_flow_data_overwrite(self, redis_client):
        """Test flow data import with overwrite enabled."""
        flow_data = {
            "name": "Existing Flow",
            "agents": []
        }
        
        redis_client.flow_name_exists = Mock(return_value=True)
        redis_client.redis.smembers.return_value = {"existing-flow-id"}
        redis_client.redis.hgetall.return_value = {"name": "Existing Flow"}
        redis_client.delete_flow = Mock(return_value=True)
        redis_client.create_flow = Mock(return_value="new-flow-id")

        flow_id, warnings = redis_client.import_flow_data(flow_data, False, True)

        assert flow_id == "new-flow-id"
        redis_client.delete_flow.assert_called_once_with("existing-flow-id")
