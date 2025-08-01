"""Redis client for platform data storage."""

import json
from datetime import UTC, datetime

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
        self.redis.hset(f"agent:{agent_name}", "last_verified", datetime.now(UTC).isoformat())

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

    def create_session(self, session_id: str, agent_name: str, context: dict = None) -> None:
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
            "last_activity": datetime.now(UTC).isoformat()
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

        self.redis.hset(f"session:{session_id}", "last_activity", datetime.now(UTC).isoformat())
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
