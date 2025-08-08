"""Flow execution engine for orchestrating agent workflows."""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Dict, List, Optional, Set

from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

from .redis_client import RedisClient

logger = logging.getLogger(__name__)


class FlowExecutionEngine:
    """Engine for executing agent flows with dependency management and health checks."""

    def __init__(self, redis_client: RedisClient):
        """Initialize flow execution engine.

        Args:
            redis_client: Redis client for data storage
        """
        self.redis_client = redis_client
        self.retry_count = 3
        self.retry_delay = 1.0  # seconds

    async def execute_flow(self, flow_id: str, input_data: dict) -> dict:
        """Execute a flow with health checks and dependency management.

        Args:
            flow_id: Flow identifier
            input_data: Input data for the flow

        Returns:
            Execution result dictionary

        Raises:
            ValueError: If flow not found or invalid
            RuntimeError: If flow execution fails
        """
        # Get flow definition
        flow_data = self.redis_client.get_flow(flow_id)
        if not flow_data:
            raise ValueError(f"Flow '{flow_id}' not found")

        agents = flow_data.get("agents", [])
        if not agents:
            raise ValueError(f"Flow '{flow_id}' has no agents")

        # Create execution record
        execution_id = self.redis_client.create_flow_execution(flow_id, input_data)

        try:
            # Update status to running
            self.redis_client.update_flow_execution(
                flow_id,
                execution_id,
                status="running",
                started_at=datetime.now(UTC).isoformat(),
            )

            logger.info(f"Starting flow execution: {flow_id}/{execution_id}")

            # Step 1: Health check
            health_result = await self._check_flow_health(agents)
            if not health_result["healthy"]:
                error_msg = f"Flow not ready: {health_result['error']}"
                self.redis_client.update_flow_execution(
                    flow_id,
                    execution_id,
                    status="failed",
                    error=error_msg,
                    completed_at=datetime.now(UTC).isoformat(),
                )
                raise RuntimeError(error_msg)

            # Step 2: Execute flow
            result = await self._execute_flow_with_dependencies(
                flow_id, execution_id, agents, input_data
            )

            # Step 3: Update final status
            self.redis_client.update_flow_execution(
                flow_id,
                execution_id,
                status="completed",
                output_data=result,
                completed_at=datetime.now(UTC).isoformat(),
            )

            logger.info(f"Flow execution completed: {flow_id}/{execution_id}")
            return result

        except Exception as e:
            # Update execution with error
            self.redis_client.update_flow_execution(
                flow_id,
                execution_id,
                status="failed",
                error=str(e),
                completed_at=datetime.now(UTC).isoformat(),
            )
            logger.error(f"Flow execution failed: {flow_id}/{execution_id}: {e}")
            raise

    async def _check_flow_health(self, agents: List[dict]) -> dict:
        """Check if all required agents are healthy.

        Args:
            agents: List of agent configurations

        Returns:
            Dictionary with health status and any error message
        """
        required_agents = [agent for agent in agents if agent.get("required", True)]

        logger.info(f"Checking health of {len(required_agents)} required agents")

        for agent_config in required_agents:
            agent_name = agent_config["agent_name"]

            # Get agent data from registry
            agent_data = self.redis_client.get_agent(agent_name)
            if not agent_data:
                return {
                    "healthy": False,
                    "error": f"Required agent '{agent_name}' not found in registry",
                }

            # Check if agent is available via ping
            if not await self._ping_agent(agent_data):
                return {
                    "healthy": False,
                    "error": f"Required agent '{agent_name}' is not responding",
                }

        logger.info("All required agents are healthy")
        return {"healthy": True, "error": None}

    async def _ping_agent(self, agent_data: dict) -> bool:
        """Ping an agent to check availability.

        Args:
            agent_data: Agent registration data

        Returns:
            True if agent is responding, False otherwise
        """
        try:
            acp_base_url = agent_data.get("acp_base_url")
            auth_token = agent_data.get("auth_token")

            if not acp_base_url:
                return False

            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            async with Client(base_url=acp_base_url, headers=headers) as client:
                # Try to get agent info (simple health check)
                response = await client._client.get("/")
                return response.status_code == 200

        except Exception as e:
            logger.warning(f"Agent ping failed for {agent_data.get('agent_name')}: {e}")
            return False

    async def _execute_flow_with_dependencies(
        self, flow_id: str, execution_id: str, agents: List[dict], input_data: dict
    ) -> dict:
        """Execute flow with dependency resolution.

        Args:
            flow_id: Flow identifier
            execution_id: Execution identifier
            agents: List of agent configurations
            input_data: Input data for the flow

        Returns:
            Final flow output
        """
        # Build dependency graph
        agent_map = {agent["agent_name"]: agent for agent in agents}
        completed_agents = set()
        agent_results = {}

        # Find start agents (no upstream dependencies)
        start_agents = [
            agent for agent in agents if not agent.get("upstream_agents", [])
        ]

        if not start_agents:
            raise RuntimeError("No start agents found in flow")

        logger.info(f"Found {len(start_agents)} start agents")

        # Execute start agents in parallel
        start_tasks = []
        for agent_config in start_agents:
            task = self._execute_agent_with_retry(
                flow_id, execution_id, agent_config, input_data
            )
            start_tasks.append(task)

        # Wait for start agents to complete
        start_results = await asyncio.gather(*start_tasks, return_exceptions=True)

        # Process start agent results
        for i, result in enumerate(start_results):
            agent_config = start_agents[i]
            agent_name = agent_config["agent_name"]

            if isinstance(result, Exception):
                if agent_config.get("required", True):
                    raise RuntimeError(
                        f"Required start agent '{agent_name}' failed: {result}"
                    )
                else:
                    # Optional agent failed - use empty result
                    agent_results[agent_name] = {}
                    logger.warning(
                        f"Optional start agent '{agent_name}' failed: {result}"
                    )
            else:
                agent_results[agent_name] = result

            completed_agents.add(agent_name)

        # Continue with downstream agents
        while len(completed_agents) < len(agents):
            # Find agents ready to execute
            ready_agents = []
            for agent_config in agents:
                agent_name = agent_config["agent_name"]
                if agent_name in completed_agents:
                    continue

                if self._is_agent_ready(agent_config, completed_agents, agent_map):
                    ready_agents.append(agent_config)

            if not ready_agents:
                # Check if we have any agents left that could potentially run
                remaining_agents = [
                    agent["agent_name"]
                    for agent in agents
                    if agent["agent_name"] not in completed_agents
                ]
                if remaining_agents:
                    raise RuntimeError(
                        f"Circular dependency or missing upstream agents: {remaining_agents}"
                    )
                break

            logger.info(f"Executing {len(ready_agents)} ready agents")

            # Execute ready agents in parallel
            ready_tasks = []
            for agent_config in ready_agents:
                # Build input from upstream agents
                agent_input = self._build_agent_input(
                    agent_config, agent_results, input_data
                )

                task = self._execute_agent_with_retry(
                    flow_id, execution_id, agent_config, agent_input
                )
                ready_tasks.append(task)

            # Wait for ready agents to complete
            ready_results = await asyncio.gather(*ready_tasks, return_exceptions=True)

            # Process ready agent results
            for i, result in enumerate(ready_results):
                agent_config = ready_agents[i]
                agent_name = agent_config["agent_name"]

                if isinstance(result, Exception):
                    if agent_config.get("required", True):
                        raise RuntimeError(
                            f"Required agent '{agent_name}' failed: {result}"
                        )
                    else:
                        # Optional agent failed - use empty result
                        agent_results[agent_name] = {}
                        logger.warning(
                            f"Optional agent '{agent_name}' failed: {result}"
                        )
                else:
                    agent_results[agent_name] = result

                completed_agents.add(agent_name)

        # Find final agents (agents with no downstream dependencies)
        final_agents = []
        for agent_config in agents:
            agent_name = agent_config["agent_name"]
            is_final = True

            # Check if any other agent depends on this one
            for other_agent in agents:
                if agent_name in other_agent.get("upstream_agents", []):
                    is_final = False
                    break

            if is_final:
                final_agents.append(agent_name)

        # Build final output from final agents
        if len(final_agents) == 1:
            # Single final agent - return its output directly
            return agent_results.get(final_agents[0], {})
        else:
            # Multiple final agents - return namespaced results
            final_output = {}
            for agent_name in final_agents:
                final_output[agent_name] = agent_results.get(agent_name, {})
            return final_output

    def _is_agent_ready(
        self, agent_config: dict, completed_agents: Set[str], agent_map: Dict[str, dict]
    ) -> bool:
        """Check if agent is ready to execute based on dependencies.

        Args:
            agent_config: Agent configuration
            completed_agents: Set of completed agent names
            agent_map: Map of agent name to configuration

        Returns:
            True if agent is ready to execute
        """
        upstream_agents = agent_config.get("upstream_agents", [])
        if not upstream_agents:
            return True  # No dependencies

        # Check if all required upstream agents are complete
        for upstream_name in upstream_agents:
            upstream_config = agent_map.get(upstream_name)
            if not upstream_config:
                continue  # Skip unknown agents

            if upstream_config.get("required", True):
                # Required upstream must be complete
                if upstream_name not in completed_agents:
                    return False

        return True

    def _build_agent_input(
        self, agent_config: dict, agent_results: Dict[str, dict], initial_input: dict
    ) -> dict:
        """Build input data for an agent based on upstream results.

        Args:
            agent_config: Agent configuration
            agent_results: Results from completed agents
            initial_input: Initial flow input data

        Returns:
            Input data for the agent
        """
        upstream_agents = agent_config.get("upstream_agents", [])

        if not upstream_agents:
            # Start agent - gets initial input
            return initial_input

        if len(upstream_agents) == 1:
            # Single upstream - direct pass-through
            upstream_name = upstream_agents[0]
            return agent_results.get(upstream_name, {})
        else:
            # Multiple upstreams - namespaced aggregation
            aggregated_input = {}
            for upstream_name in upstream_agents:
                upstream_result = agent_results.get(upstream_name, {})
                aggregated_input[upstream_name] = upstream_result
            return aggregated_input

    async def _execute_agent_with_retry(
        self, flow_id: str, execution_id: str, agent_config: dict, input_data: dict
    ) -> dict:
        """Execute an agent with retry logic.

        Args:
            flow_id: Flow identifier
            execution_id: Execution identifier
            agent_config: Agent configuration
            input_data: Input data for the agent

        Returns:
            Agent execution result

        Raises:
            RuntimeError: If agent execution fails after all retries
        """
        agent_name = agent_config["agent_name"]
        last_error = None

        for attempt in range(self.retry_count):
            try:
                logger.info(
                    f"Executing agent '{agent_name}' (attempt {attempt + 1}/{self.retry_count})"
                )

                result = await self._execute_single_agent(agent_name, input_data)

                # Store successful result
                agent_result = {
                    "status": "completed",
                    "output": result,
                    "error": None,
                    "execution_time": 0,  # TODO: Add timing
                    "attempts": attempt + 1,
                }

                self.redis_client.update_agent_result(
                    flow_id, execution_id, agent_name, agent_result
                )

                logger.info(f"Agent '{agent_name}' completed successfully")
                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Agent '{agent_name}' failed (attempt {attempt + 1}): {e}"
                )

                if attempt < self.retry_count - 1:
                    # Wait before retry
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final attempt failed - store error result
                    agent_result = {
                        "status": "failed",
                        "output": {},
                        "error": str(e),
                        "execution_time": 0,
                        "attempts": self.retry_count,
                    }

                    self.redis_client.update_agent_result(
                        flow_id, execution_id, agent_name, agent_result
                    )

        raise RuntimeError(
            f"Agent '{agent_name}' failed after {self.retry_count} attempts: {last_error}"
        )

    async def _execute_single_agent(self, agent_name: str, input_data: dict) -> dict:
        """Execute a single agent.

        Args:
            agent_name: Agent name
            input_data: Input data for the agent

        Returns:
            Agent execution result

        Raises:
            RuntimeError: If agent execution fails
        """
        # Get agent data
        agent_data = self.redis_client.get_agent(agent_name)
        if not agent_data:
            raise RuntimeError(f"Agent '{agent_name}' not found in registry")

        acp_base_url = agent_data.get("acp_base_url")
        auth_token = agent_data.get("auth_token")

        if not acp_base_url:
            raise RuntimeError(f"Agent '{agent_name}' has no ACP base URL")

        # Prepare ACP message
        message_content = (
            json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)
        )
        messages = [Message(parts=[MessagePart(content=message_content)])]

        # Execute via ACP
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            async with Client(base_url=acp_base_url, headers=headers) as client:
                run = await client.run_sync(agent=agent_name, input=messages)

                if not run.output:
                    return {}

                # Extract result from ACP response
                if run.output and len(run.output) > 0:
                    output_content = run.output[0].parts[0].content
                    try:
                        # Try to parse as JSON
                        return json.loads(output_content)
                    except json.JSONDecodeError:
                        # Return as string content
                        return {"content": output_content}

                return {}

        except Exception as e:
            raise RuntimeError(f"ACP execution failed for agent '{agent_name}': {e}")
