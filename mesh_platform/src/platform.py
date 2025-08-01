"""Platform core implementation for Agent Mesh SDK."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .redis_client import RedisClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlatformCore:
    """Platform core for managing agents and routing ACP requests."""

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        """Initialize platform core.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
        """
        self.redis_client = RedisClient(host=redis_host, port=redis_port)
        self.app = FastAPI(title="Agent Mesh Platform", version="0.1.0")
        self.ping_tasks: dict[str, asyncio.Task] = {}  # Track ping tasks per agent
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        # Custom registration endpoint
        @self.app.post("/platform/agents/register")
        async def register_agent(request: Request):
            """Register a new agent with the platform."""
            try:
                agent_data = await request.json()

                # Validate required fields
                required_fields = [
                    "agent_name",
                    "agent_type",
                    "capabilities",
                    "acp_base_url",
                    "auth_token",
                ]
                missing_fields = [
                    field for field in required_fields if field not in agent_data
                ]

                if missing_fields:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing required fields: {missing_fields}",
                    )

                # Validate capabilities
                if (
                    not isinstance(agent_data["capabilities"], list)
                    or not agent_data["capabilities"]
                ):
                    raise HTTPException(
                        status_code=400, detail="Capabilities must be a non-empty list"
                    )

                # Store capabilities as JSON string for Redis
                agent_data["capabilities"] = json.dumps(agent_data["capabilities"])
                if "tags" in agent_data:
                    agent_data["tags"] = json.dumps(agent_data.get("tags", []))

                # Try to register agent
                if not self.redis_client.register_agent(agent_data):
                    raise HTTPException(
                        status_code=409,
                        detail=f"Agent '{agent_data['agent_name']}' already exists",
                    )

                # Verify agent connection
                try:
                    await self._verify_agent_connection(agent_data)
                    logger.info(
                        f"Agent '{agent_data['agent_name']}' registered and verified successfully"
                    )

                    # Start ping loop for this agent
                    await self._start_agent_ping_loop(agent_data)
                except Exception as e:
                    # Remove agent from registry if verification fails
                    self.redis_client.delete_agent(agent_data["agent_name"])
                    logger.error(f"Agent verification failed: {e}")
                    raise HTTPException(
                        status_code=400, detail=f"Agent verification failed: {e!s}"
                    )

                return JSONResponse(
                    status_code=200,
                    content={
                        "message": "Agent registered successfully",
                        "agent_name": agent_data["agent_name"],
                        "status": "active",
                    },
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Agent registration error: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        # Standard ACP endpoints
        @self.app.get("/agents")
        async def list_agents():
            """List all registered agents (ACP standard)."""
            try:
                agents = self.redis_client.list_agents()
                # Convert to ACP format
                acp_agents = []
                for agent in agents:
                    # capabilities and tags are already parsed by redis_client.get_agent()
                    capabilities = agent.get("capabilities", [])
                    if isinstance(capabilities, str):
                        capabilities = json.loads(capabilities)

                    tags = agent.get("tags", [])
                    if isinstance(tags, str):
                        tags = json.loads(tags)

                    acp_agent = {
                        "name": agent["agent_name"],
                        "version": agent.get("version", "1.0.0"),
                        "description": agent.get("description", ""),
                        "capabilities": capabilities,
                        "tags": tags,
                        "contact": agent.get("contact", ""),
                    }
                    acp_agents.append(acp_agent)

                return JSONResponse(content={"agents": acp_agents})

            except Exception as e:
                logger.error(f"Error listing agents: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.get("/agents/{agent_name}")
        async def get_agent_manifest(agent_name: str):
            """Get specific agent manifest (ACP standard)."""
            try:
                agent = self.redis_client.get_agent(agent_name)
                if not agent:
                    raise HTTPException(status_code=404, detail="Agent not found")

                # Convert to ACP manifest format
                manifest = {
                    "name": agent["agent_name"],
                    "version": agent.get("version", "1.0.0"),
                    "description": agent.get("description", ""),
                    "capabilities": agent.get("capabilities", []),
                    "tags": agent.get("tags", []),
                    "contact": agent.get("contact", ""),
                    "status": agent.get("status", "unknown"),
                }

                return JSONResponse(content=manifest)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting agent manifest: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.post("/runs")
        async def create_run(request: Request):
            """Create and start agent run (ACP standard)."""
            try:
                run_data = await request.json()

                # Validate required fields
                if "agent" not in run_data or "input" not in run_data:
                    raise HTTPException(
                        status_code=400, detail="Missing required fields: agent, input"
                    )

                agent_name = run_data["agent"]
                input_messages = run_data["input"]

                # Get agent data
                agent = self.redis_client.get_agent(agent_name)
                if not agent:
                    raise HTTPException(status_code=404, detail="Agent not found")

                # Create run ID
                run_id = str(uuid.uuid4())

                # Execute agent run
                try:
                    result = await self._execute_agent_run(
                        agent, input_messages, run_id
                    )

                    return JSONResponse(
                        content={
                            "run_id": run_id,
                            "status": "completed",
                            "output": result,
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    )

                except Exception as e:
                    logger.error(f"Agent execution error: {e}")
                    return JSONResponse(
                        status_code=500,
                        content={
                            "run_id": run_id,
                            "status": "failed",
                            "error": str(e),
                            "created_at": datetime.now(UTC).isoformat(),
                        },
                    )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error creating run: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.get("/runs/{run_id}")
        async def get_run_status(run_id: str):
            """Get run status (ACP standard)."""
            # For MVP, we'll just return a simple response
            # In a full implementation, you'd track run status in Redis
            return JSONResponse(
                content={
                    "run_id": run_id,
                    "status": "completed",
                    "message": "Run status tracking not implemented in MVP",
                }
            )

        @self.app.post("/runs/{run_id}/cancel")
        async def cancel_run(run_id: str):
            """Cancel agent run (ACP standard)."""
            # For MVP, we'll just return a simple response
            return JSONResponse(
                content={
                    "run_id": run_id,
                    "status": "cancelled",
                    "message": "Run cancellation not implemented in MVP",
                }
            )

        @self.app.delete("/platform/agents/cleanup")
        async def cleanup_all_agents():
            """Clean up all agents from the platform."""
            try:
                # Cancel all ping tasks first
                for agent_name, task in self.ping_tasks.items():
                    logger.info(f"Cancelling ping task for agent '{agent_name}'")
                    task.cancel()
                self.ping_tasks.clear()
                
                # Delete all agents from Redis
                deleted_count = self.redis_client.cleanup_all_agents()
                
                logger.info(f"Cleaned up {deleted_count} agents from platform")
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "message": f"Successfully cleaned up {deleted_count} agents",
                        "deleted_count": deleted_count,
                    },
                )
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

    async def _verify_agent_connection(self, agent_data: dict) -> None:
        """Verify agent connection after registration."""
        try:
            async with Client(
                base_url=agent_data["acp_base_url"],
                headers={"Authorization": f"Bearer {agent_data['auth_token']}"},
            ) as client:
                # Try to get agents list from the agent
                response = await client._client.get("/agents")
                if response.status_code not in [200, 404]:
                    raise Exception(
                        f"Agent verification failed with status {response.status_code}"
                    )

        except Exception as e:
            raise Exception(f"Failed to verify agent connection: {e!s}")

    async def _execute_agent_run(
        self, agent: dict, input_messages: list[dict], run_id: str
    ) -> list[dict]:
        """Execute agent run via ACP client."""
        try:
            # Convert input to ACP Message format
            messages = []
            for msg in input_messages:
                if isinstance(msg, dict) and "content" in msg:
                    messages.append(
                        Message(parts=[MessagePart(content=msg["content"])])
                    )
                elif isinstance(msg, str):
                    messages.append(Message(parts=[MessagePart(content=msg)]))
                else:
                    messages.append(Message(parts=[MessagePart(content=str(msg))]))

            # Execute via ACP client
            async with Client(
                base_url=agent["acp_base_url"],
                headers={"Authorization": f"Bearer {agent['auth_token']}"},
            ) as client:
                run = await client.run_sync(agent=agent["agent_name"], input=messages)

                # Extract output
                output = []
                if hasattr(run, "output") and run.output:
                    for message in run.output:
                        if hasattr(message, "parts"):
                            for part in message.parts:
                                output.append({"content": part.content})
                        else:
                            output.append({"content": str(message)})

                return output or [{"content": "No output from agent"}]

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise Exception(f"Agent execution failed: {e!s}")

    async def _start_agent_ping_loop(self, agent_data: dict) -> None:
        """Start background ping loop for an agent."""
        agent_name = agent_data["agent_name"]

        # Cancel existing ping task if any
        if agent_name in self.ping_tasks:
            self.ping_tasks[agent_name].cancel()

        # Start new ping task
        task = asyncio.create_task(self._ping_agent_loop(agent_data))
        self.ping_tasks[agent_name] = task
        logger.info(f"Started ping loop for agent '{agent_name}'")

    async def _ping_agent_loop(self, agent_data: dict) -> None:
        """Background loop to ping agent periodically."""
        agent_name = agent_data["agent_name"]
        ping_interval = 3  # Ping every 3 seconds
        max_failures = 3
        consecutive_failures = 0

        while True:
            try:
                await asyncio.sleep(ping_interval)

                # Ping the agent
                success = await self._ping_agent(agent_data)

                if success:
                    # Reset failure counter on success
                    consecutive_failures = 0
                    # Update last verified timestamp in Redis
                    self.redis_client.update_agent_status(agent_name, "active")
                    logger.debug(f"Ping successful for agent '{agent_name}'")
                else:
                    consecutive_failures += 1
                    logger.warning(
                        f"Ping failed for agent '{agent_name}' (attempt {consecutive_failures}/{max_failures})"
                    )

                    if consecutive_failures >= max_failures:
                        logger.error(
                            f"Agent '{agent_name}' failed {max_failures} consecutive pings, removing from registry"
                        )
                        # Remove agent from Redis
                        self.redis_client.delete_agent(agent_name)
                        # Clean up ping task
                        if agent_name in self.ping_tasks:
                            del self.ping_tasks[agent_name]
                        break

            except asyncio.CancelledError:
                logger.info(f"Ping loop cancelled for agent '{agent_name}'")
                break
            except Exception as e:
                logger.error(f"Error in ping loop for agent '{agent_name}': {e}")
                consecutive_failures += 1

                if consecutive_failures >= max_failures:
                    logger.error(
                        f"Agent '{agent_name}' failed {max_failures} consecutive times due to errors, removing from registry"
                    )
                    self.redis_client.delete_agent(agent_name)
                    if agent_name in self.ping_tasks:
                        del self.ping_tasks[agent_name]
                    break

    async def _ping_agent(self, agent_data: dict) -> bool:
        """Ping an agent using the ACP /ping endpoint."""
        try:
            async with Client(
                base_url=agent_data["acp_base_url"],
                headers={"Authorization": f"Bearer {agent_data['auth_token']}"},
            ) as client:
                # Ping the agent
                response = await client._client.get("/ping")
                return response.status_code == 200

        except Exception as e:
            logger.debug(f"Ping failed for agent '{agent_data['agent_name']}': {e}")
            return False

    async def shutdown(self) -> None:
        """Cleanup method to cancel all ping tasks on shutdown."""
        logger.info("Shutting down platform, cancelling all ping tasks")
        for agent_name, task in self.ping_tasks.items():
            logger.info(f"Cancelling ping task for agent '{agent_name}'")
            task.cancel()
        self.ping_tasks.clear()

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run the platform server."""
        import uvicorn

        logger.info(f"Starting Agent Mesh Platform on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port)
