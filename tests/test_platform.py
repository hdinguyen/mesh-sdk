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
