"""Redis client for platform data storage."""

import json
import uuid
from datetime import UTC, datetime
from typing import Optional

import redis


class RedisClient:
    """Redis client for managing agent data, queues, and sessions."""

    def __init__(self, host: str = "localhost", port: int = 6380, db: int = 0):
        """Initialize Redis client.

        Args:
            host: Redis host (default: localhost)
            port: Redis port (default: 6380 for Docker)
            db: Redis database number (default: 0)
        """
        self.host = host
        self.port = port
        self.db = db
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)

        # Test connection
        try:
            self.redis.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis at {host}:{port}") from e

    def register_agent(self, agent_data: dict) -> bool:
        """Register an agent in Redis.

        Args:
            agent_data: Agent registration data

        Returns:
            True if registration successful, False if agent already exists
        """
        agent_name = agent_data["agent_name"]

        # Check if agent already exists
        if self.redis.exists(f"agent:{agent_name}"):
            return False

        # Add timestamps
        agent_data["status"] = "active"
        agent_data["registered_at"] = datetime.now(UTC).isoformat()
        agent_data["last_verified"] = datetime.now(UTC).isoformat()

        # Store agent data
        self.redis.hset(f"agent:{agent_name}", mapping=agent_data)

        # Add to agent list
        self.redis.sadd("agents", agent_name)

        return True

    def get_agent(self, agent_name: str) -> dict | None:
        """Get agent data by name.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent data dictionary or None if not found
        """
        if not self.redis.exists(f"agent:{agent_name}"):
            return None

        agent_data = self.redis.hgetall(f"agent:{agent_name}")

        # Parse JSON fields
        if "capabilities" in agent_data:
            try:
                agent_data["capabilities"] = json.loads(agent_data["capabilities"])
            except json.JSONDecodeError:
                pass

        if "tags" in agent_data:
            try:
                agent_data["tags"] = json.loads(agent_data["tags"])
            except json.JSONDecodeError:
                pass

        return agent_data

    def list_agents(self) -> list[dict]:
        """List all registered agents.

        Returns:
            List of agent data dictionaries
        """
        agent_names = self.redis.smembers("agents")
        agents = []

        for agent_name in agent_names:
            agent_data = self.get_agent(agent_name)
            if agent_data:
                agents.append(agent_data)

        return agents

    def update_agent_status(self, agent_name: str, status: str) -> bool:
        """Update agent status.

        Args:
            agent_name: Name of the agent
            status: New status (active, inactive, error)

        Returns:
            True if updated successfully, False if agent not found
        """
        if not self.redis.exists(f"agent:{agent_name}"):
            return False

        self.redis.hset(f"agent:{agent_name}", "status", status)
        self.redis.hset(
            f"agent:{agent_name}", "last_verified", datetime.now(UTC).isoformat()
        )

        return True

    def delete_agent(self, agent_name: str) -> bool:
        """Delete an agent from Redis.

        Args:
            agent_name: Name of the agent to delete

        Returns:
            True if deleted successfully, False if agent not found
        """
        if not self.redis.exists(f"agent:{agent_name}"):
            return False

        # Delete agent data
        self.redis.delete(f"agent:{agent_name}")

        # Remove from agent list
        self.redis.srem("agents", agent_name)

        # Clean up related data
        self.redis.delete(f"queue:{agent_name}")

        return True

    def cleanup_all_agents(self) -> int:
        """Delete all agents from Redis.

        Returns:
            Number of agents deleted
        """
        agent_names = self.redis.smembers("agents")
        count = 0

        for agent_name in agent_names:
            if self.delete_agent(agent_name):
                count += 1

        return count

    def add_to_queue(self, agent_name: str, message: dict) -> None:
        """Add message to agent queue.

        Args:
            agent_name: Name of the agent
            message: Message to queue
        """
        message_json = json.dumps(message)
        self.redis.lpush(f"queue:{agent_name}", message_json)

    def get_from_queue(self, agent_name: str) -> dict | None:
        """Get message from agent queue.

        Args:
            agent_name: Name of the agent

        Returns:
            Message dictionary or None if queue is empty
        """
        message_json = self.redis.rpop(f"queue:{agent_name}")
        if message_json:
            try:
                return json.loads(message_json)
            except json.JSONDecodeError:
                return None
        return None

    def create_session(
        self, session_id: str, agent_name: str, context: dict = None
    ) -> None:
        """Create a new session.

        Args:
            session_id: Unique session identifier
            agent_name: Name of the agent for this session
            context: Optional session context
        """
        session_data = {
            "agent_name": agent_name,
            "context": json.dumps(context or {}),
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
        }

        self.redis.hset(f"session:{session_id}", mapping=session_data)
        # Set session expiration (24 hours)
        self.redis.expire(f"session:{session_id}", 86400)

    def get_session(self, session_id: str) -> dict | None:
        """Get session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data dictionary or None if not found
        """
        if not self.redis.exists(f"session:{session_id}"):
            return None

        session_data = self.redis.hgetall(f"session:{session_id}")

        # Parse context JSON
        if "context" in session_data:
            try:
                session_data["context"] = json.loads(session_data["context"])
            except json.JSONDecodeError:
                session_data["context"] = {}

        return session_data

    def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp.

        Args:
            session_id: Session identifier

        Returns:
            True if updated successfully, False if session not found
        """
        if not self.redis.exists(f"session:{session_id}"):
            return False

        self.redis.hset(
            f"session:{session_id}", "last_activity", datetime.now(UTC).isoformat()
        )
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully, False if session not found
        """
        if not self.redis.exists(f"session:{session_id}"):
            return False

        self.redis.delete(f"session:{session_id}")
        return True

    # Flow Management Methods

    def create_flow(self, name: str, description: str = "", imported_from: str = None) -> str:
        """Create a new flow.

        Args:
            name: Flow name
            description: Optional flow description
            imported_from: Optional source indication for imported flows

        Returns:
            Flow ID
        """
        flow_id = str(uuid.uuid4())
        flow_data = {
            "flow_id": flow_id,
            "name": name,
            "description": description,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        
        if imported_from:
            flow_data["imported_from"] = imported_from

        # Store flow definition
        self.redis.hset(f"flow:{flow_id}", mapping=flow_data)

        # Add to flow list
        self.redis.sadd("flows", flow_id)

        # Initialize empty agents list
        self.redis.delete(f"flow:{flow_id}:agents")

        return flow_id

    def flow_name_exists(self, name: str) -> bool:
        """Check if a flow name already exists.

        Args:
            name: Flow name to check

        Returns:
            True if flow name exists, False otherwise
        """
        flow_ids = self.redis.smembers("flows")
        for flow_id in flow_ids:
            flow_data = self.redis.hgetall(f"flow:{flow_id}")
            if flow_data.get("name") == name:
                return True
        return False

    def get_flow(self, flow_id: str) -> Optional[dict]:
        """Get flow by ID.

        Args:
            flow_id: Flow identifier

        Returns:
            Flow data dictionary or None if not found
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return None

        flow_data = self.redis.hgetall(f"flow:{flow_id}")

        # Get agents list
        agents_data = self.redis.lrange(f"flow:{flow_id}:agents", 0, -1)
        agents = []
        for agent_json in agents_data:
            try:
                agents.append(json.loads(agent_json))
            except json.JSONDecodeError:
                continue

        flow_data["agents"] = agents
        return flow_data

    def list_flows(self) -> list[dict]:
        """List all flows.

        Returns:
            List of flow data dictionaries
        """
        flow_ids = self.redis.smembers("flows")
        flows = []

        for flow_id in flow_ids:
            flow_data = self.get_flow(flow_id)
            if flow_data:
                flows.append(flow_data)

        return flows

    def update_flow(self, flow_id: str, **updates) -> bool:
        """Update flow data.

        Args:
            flow_id: Flow identifier
            **updates: Fields to update

        Returns:
            True if updated successfully, False if flow not found
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return False

        updates["updated_at"] = datetime.now(UTC).isoformat()
        self.redis.hset(f"flow:{flow_id}", mapping=updates)
        return True

    def delete_flow(self, flow_id: str) -> bool:
        """Delete a flow.

        Args:
            flow_id: Flow identifier

        Returns:
            True if deleted successfully, False if flow not found
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return False

        # Delete flow data
        self.redis.delete(f"flow:{flow_id}")
        self.redis.delete(f"flow:{flow_id}:agents")

        # Remove from flow list
        self.redis.srem("flows", flow_id)

        # Clean up executions (keep recent ones for debugging)
        execution_keys = self.redis.keys(f"flow:{flow_id}:execution:*")
        if execution_keys:
            self.redis.delete(*execution_keys)

        return True

    def add_agent_to_flow(
        self,
        flow_id: str,
        agent_name: str,
        upstream_agents: list[str] = None,
        required: bool = True,
        description: str = "",
    ) -> bool:
        """Add agent to flow.

        Args:
            flow_id: Flow identifier
            agent_name: Agent name
            upstream_agents: List of upstream agent names
            required: Whether agent is required
            description: Optional agent description

        Returns:
            True if added successfully, False if flow not found or agent already exists
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return False

        # Check if agent already exists in flow
        agents_data = self.redis.lrange(f"flow:{flow_id}:agents", 0, -1)
        for agent_json in agents_data:
            try:
                agent_data = json.loads(agent_json)
                if agent_data.get("agent_name") == agent_name:
                    return False  # Agent already exists
            except json.JSONDecodeError:
                continue

        agent_data = {
            "agent_name": agent_name,
            "upstream_agents": upstream_agents or [],
            "required": required,
            "description": description,
            "added_at": datetime.now(UTC).isoformat(),
        }

        # Add agent to flow
        self.redis.lpush(f"flow:{flow_id}:agents", json.dumps(agent_data))

        # Update flow timestamp
        self.update_flow(flow_id)

        return True

    def remove_agent_from_flow(self, flow_id: str, agent_name: str) -> bool:
        """Remove agent from flow.

        Args:
            flow_id: Flow identifier
            agent_name: Agent name

        Returns:
            True if removed successfully, False if flow or agent not found
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return False

        # Get all agents
        agents_data = self.redis.lrange(f"flow:{flow_id}:agents", 0, -1)
        updated_agents = []
        found = False

        for agent_json in agents_data:
            try:
                agent_data = json.loads(agent_json)
                if agent_data.get("agent_name") != agent_name:
                    updated_agents.append(agent_json)
                else:
                    found = True
            except json.JSONDecodeError:
                continue

        if not found:
            return False

        # Replace agents list
        self.redis.delete(f"flow:{flow_id}:agents")
        if updated_agents:
            self.redis.rpush(f"flow:{flow_id}:agents", *updated_agents)

        # Update flow timestamp
        self.update_flow(flow_id)

        return True

    def get_flow_agents(self, flow_id: str) -> list[dict]:
        """Get agents in flow.

        Args:
            flow_id: Flow identifier

        Returns:
            List of agent configurations
        """
        if not self.redis.exists(f"flow:{flow_id}"):
            return []

        agents_data = self.redis.lrange(f"flow:{flow_id}:agents", 0, -1)
        agents = []

        for agent_json in agents_data:
            try:
                agents.append(json.loads(agent_json))
            except json.JSONDecodeError:
                continue

        return agents

    def create_flow_execution(self, flow_id: str, input_data: dict) -> str:
        """Create a new flow execution.

        Args:
            flow_id: Flow identifier
            input_data: Input data for execution

        Returns:
            Execution ID
        """
        execution_id = str(uuid.uuid4())
        execution_data = {
            "execution_id": execution_id,
            "flow_id": flow_id,
            "status": "pending",
            "input_data": json.dumps(input_data),
            "output_data": json.dumps({}),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": "",
            "error": "",
            "agent_results": json.dumps({}),
        }

        # Store execution data
        self.redis.hset(
            f"flow:{flow_id}:execution:{execution_id}", mapping=execution_data
        )

        # Add to executions list (maintain recent 100)
        self.redis.lpush(f"flow:{flow_id}:executions", execution_id)
        self.redis.ltrim(
            f"flow:{flow_id}:executions", 0, 99
        )  # Keep only 100 recent executions

        return execution_id

    def get_flow_execution(self, flow_id: str, execution_id: str) -> Optional[dict]:
        """Get flow execution by ID.

        Args:
            flow_id: Flow identifier
            execution_id: Execution identifier

        Returns:
            Execution data dictionary or None if not found
        """
        if not self.redis.exists(f"flow:{flow_id}:execution:{execution_id}"):
            return None

        execution_data = self.redis.hgetall(f"flow:{flow_id}:execution:{execution_id}")

        # Parse JSON fields
        for field in ["input_data", "output_data", "agent_results"]:
            if field in execution_data and execution_data[field]:
                try:
                    execution_data[field] = json.loads(execution_data[field])
                except json.JSONDecodeError:
                    execution_data[field] = {}

        return execution_data

    def update_flow_execution(self, flow_id: str, execution_id: str, **updates) -> bool:
        """Update flow execution.

        Args:
            flow_id: Flow identifier
            execution_id: Execution identifier
            **updates: Fields to update

        Returns:
            True if updated successfully, False if execution not found
        """
        if not self.redis.exists(f"flow:{flow_id}:execution:{execution_id}"):
            return False

        # Convert dict fields to JSON
        for field in ["output_data", "agent_results"]:
            if field in updates and isinstance(updates[field], dict):
                updates[field] = json.dumps(updates[field])

        self.redis.hset(f"flow:{flow_id}:execution:{execution_id}", mapping=updates)
        return True

    def list_flow_executions(self, flow_id: str, limit: int = 10) -> list[dict]:
        """List recent flow executions.

        Args:
            flow_id: Flow identifier
            limit: Maximum number of executions to return

        Returns:
            List of execution data dictionaries
        """
        if not self.redis.exists(f"flow:{flow_id}:executions"):
            return []

        execution_ids = self.redis.lrange(f"flow:{flow_id}:executions", 0, limit - 1)
        executions = []

        for execution_id in execution_ids:
            execution_data = self.get_flow_execution(flow_id, execution_id)
            if execution_data:
                executions.append(execution_data)

        return executions

    def update_agent_result(
        self, flow_id: str, execution_id: str, agent_name: str, result: dict
    ) -> bool:
        """Update agent result in flow execution.

        Args:
            flow_id: Flow identifier
            execution_id: Execution identifier
            agent_name: Agent name
            result: Agent execution result

        Returns:
            True if updated successfully, False if execution not found
        """
        execution_data = self.get_flow_execution(flow_id, execution_id)
        if not execution_data:
            return False

        agent_results = execution_data.get("agent_results", {})
        agent_results[agent_name] = result

        return self.update_flow_execution(
            flow_id, execution_id, agent_results=agent_results
        )

    # Flow Import/Export Methods

    def export_flow_data(self, flow_id: str, platform_version: str = "1.0.0") -> dict | None:
        """Export flow definition as portable JSON.

        Args:
            flow_id: Flow identifier
            platform_version: Platform version for metadata

        Returns:
            Flow export data dictionary or None if not found
        """
        flow_data = self.get_flow(flow_id)
        if not flow_data:
            return None

        return {
            "name": flow_data.get("name", ""),
            "description": flow_data.get("description", ""),
            "agents": [
                {
                    "agent_name": agent.get("agent_name", ""),
                    "upstream_agents": agent.get("upstream_agents", []),
                    "required": agent.get("required", True),
                    "description": agent.get("description", "")
                }
                for agent in flow_data.get("agents", [])
            ],
            "metadata": {
                "exported_at": datetime.now(UTC).isoformat(),
                "platform_version": platform_version,
                "agent_count": len(flow_data.get("agents", [])),
                "original_flow_id": flow_id
            }
        }

    def import_flow_data(self, flow_data: dict, validate_agents: bool = True,
                        overwrite_existing: bool = False) -> tuple[str, list[str]]:
        """Import flow from JSON definition.

        Args:
            flow_data: Flow definition data
            validate_agents: Whether to validate agent existence
            overwrite_existing: Whether to overwrite if flow name exists

        Returns:
            Tuple of (flow_id, warnings_list)

        Raises:
            ValueError: If flow data is invalid or name conflicts exist
        """
        # Validate required fields
        if "name" not in flow_data:
            error_msg = "Missing required field: name"
            raise ValueError(error_msg)

        flow_name = flow_data["name"]

        # Check for name conflicts
        if not overwrite_existing and self.flow_name_exists(flow_name):
            error_msg = f"Flow '{flow_name}' already exists"
            raise ValueError(error_msg)

        # If overwriting, delete existing flow
        if overwrite_existing and self.flow_name_exists(flow_name):
            # Find existing flow ID and delete it
            flow_ids = self.redis.smembers("flows")
            for existing_flow_id in flow_ids:
                existing_flow_data = self.redis.hgetall(f"flow:{existing_flow_id}")
                if existing_flow_data.get("name") == flow_name:
                    self.delete_flow(existing_flow_id)
                    break

        # Validate agents if requested
        warnings = []
        agents_data = flow_data.get("agents", [])
        if validate_agents:
            for agent in agents_data:
                agent_name = agent.get("agent_name")
                if agent_name and not self.get_agent(agent_name):
                    warnings.append(
                        f"Agent '{agent_name}' not currently registered "
                        "but will be validated at execution time"
                    )

        # Create new flow
        flow_id = self.create_flow(
            name=flow_name,
            description=flow_data.get("description", ""),
            imported_from="json_import"
        )

        # Add agents to flow
        for agent in agents_data:
            agent_name = agent.get("agent_name", "")
            if agent_name:
                self.add_agent_to_flow(
                    flow_id=flow_id,
                    agent_name=agent_name,
                    upstream_agents=agent.get("upstream_agents", []),
                    required=agent.get("required", True),
                    description=agent.get("description", "")
                )

        return flow_id, warnings
