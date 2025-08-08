"""Agent SDK for ACP protocol integration."""

import logging
import os
import secrets
import threading
import time
from collections.abc import AsyncGenerator, Callable

import portpicker
import requests
from acp_sdk.models import Message, MessagePart
from acp_sdk.server import Server

from .exceptions import (
    AgentCapabilityError,
    AgentManifestError,
    AgentNameConflictError,
    MissingRequiredFieldsError,
    PlatformAuthenticationError,
    PlatformConnectionError,
    PlatformUnavailableError,
)

logger = logging.getLogger(__name__)

REQUIRED_REGISTRATION_FIELDS = {
    "agent_name": {
        "type": "string",
        "required": True,
        "description": "Unique identifier for the agent",
        "validation": "Must be alphanumeric with underscores, 3-50 characters",
        "example": "my_text_generation_agent",
    },
    "agent_type": {
        "type": "string",
        "required": True,
        "description": "Type/category of the agent",
        "validation": "Must be one of predefined agent types",
        "example": "dspy, crewai, google_adk, beeai, custom",
    },
    "capabilities": {
        "type": "array",
        "required": True,
        "description": "List of agent capabilities",
        "validation": "Must be non-empty array of strings",
        "example": ["text_generation", "reasoning", "data_processing"],
    },
    "process_function": {
        "type": "function",
        "required": True,
        "description": "Function to process incoming messages",
        "validation": "Must be callable function",
        "example": "self.process_message",
    },
}


class PingFilter(logging.Filter):
    """Filter to hide /ping requests from logs."""

    def filter(self, record):
        # Hide logs that contain "/ping" in the message
        message = record.getMessage() if hasattr(record, 'getMessage') else str(record.msg)
        return "/ping" not in message


class AgentSDK:
    """Agent SDK for seamless ACP protocol integration."""

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        capabilities: list[str],
        process_function: Callable,
        platform_url: str | None = None,
        callbacks: dict[str, Callable] | None = None,
        version: str = "1.0.0",
        description: str = "",
        tags: list[str] | None = None,
        contact: str = "",
        metadata: dict | None = None,
        input_content_types: list[str] | None = None,
        output_content_types: list[str] | None = None,
        url: str | None = None,
    ):
        """Initialize Agent SDK.

        Args:
            agent_name: Unique identifier for the agent (3-50 alphanumeric + underscores)
            agent_type: Type of agent (dspy, crewai, google_adk, beeai, custom)
            capabilities: List of agent capabilities (non-empty)
            process_function: Function to handle incoming messages
            platform_url: Platform URL (defaults to env var or localhost:8000)
            callbacks: Optional event callback functions
            version: Agent version (default: "1.0.0")
            description: Agent description
            tags: Optional categorization tags
            contact: Optional contact information
            metadata: Optional additional metadata dictionary
            input_content_types: List of supported input content types (default: ["*/*"])
            output_content_types: List of supported output content types (default: ["*/*"])
            url: Optional URL for the agent (defaults to auto-generated acp_base_url)
        """
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.process_function = process_function
        self.version = version
        self.description = description
        self.tags = tags or []
        self.contact = contact
        self.metadata = metadata or {
            "annotations": None,
            "documentation": None,
            "license": None,
            "programming_language": None,
            "natural_languages": None,
            "framework": None,
            "capabilities": None,
            "domains": None,
            "tags": None,
            "created_at": None,
            "updated_at": None,
            "author": None,
            "contributors": None,
            "links": None,
            "dependencies": None,
            "recommended_models": None
        }
        self.input_content_types = input_content_types or ["*/*"]
        self.output_content_types = output_content_types or ["*/*"]
        self.callbacks = callbacks or {}

        # Resolve platform URL with priority: env var -> parameter -> default
        self.platform_url = (
            os.getenv("PLATFORM_BASE_URL") or platform_url or "http://localhost:8000"
        )

        # Validate required fields
        self._validate_registration_fields()

        # Auto-allocate port for ACP server
        self.port = portpicker.pick_unused_port()
        self.acp_base_url = f"http://localhost:{self.port}"

        # Set URL with priority: parameter -> auto-generated acp_base_url
        self.url = url or self.acp_base_url

        # Generate auth token for platform communication
        self.auth_token = secrets.token_urlsafe(32)

        # Create ACP server
        self.server = Server()
        self._setup_acp_agent()

        # Server state
        self._server_ready = False
        self._registered = False

    def _validate_registration_fields(self) -> None:
        """Validate required registration fields."""
        registration_data = {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "process_function": self.process_function,
        }

        missing_fields = []
        invalid_fields = []

        # Check required fields
        for field_name, field_spec in REQUIRED_REGISTRATION_FIELDS.items():
            if (
                field_name not in registration_data
                or registration_data[field_name] is None
            ):
                missing_fields.append(field_name)
            # Validate field value
            elif not self._validate_field_value(
                registration_data[field_name], field_spec
            ):
                invalid_fields.append(field_name)

        if missing_fields:
            raise MissingRequiredFieldsError(
                missing_fields,
                list(REQUIRED_REGISTRATION_FIELDS.keys()),
                list(registration_data.keys()),
            )

        if invalid_fields:
            raise AgentManifestError(invalid_fields, registration_data)

    def _validate_field_value(self, value, field_spec: dict) -> bool:
        """Validate individual field value against specification."""
        if field_spec["type"] == "string":
            return isinstance(value, str) and len(value) > 0
        if field_spec["type"] == "array":
            return isinstance(value, list) and len(value) > 0
        if field_spec["type"] == "function":
            return callable(value)
        if field_spec["type"] == "dict":
            return isinstance(value, dict)
        return True

    def _setup_acp_agent(self) -> None:
        """Set up ACP agent handler."""

        @self.server.agent(name=self.agent_name)
        async def agent_handler(
            input: list[Message], context
        ) -> AsyncGenerator[Message, None]:
            """Handle ACP messages and call user's process function."""
            try:
                # Call on_message callback if provided
                if "on_message" in self.callbacks:
                    self.callbacks["on_message"](input)

                # Call user's process function
                result = self.process_function(input)

                # Convert result to ACP Message format
                if isinstance(result, dict) and "content" in result:
                    yield Message(parts=[MessagePart(content=result["content"])])
                elif isinstance(result, str):
                    yield Message(parts=[MessagePart(content=result)])
                else:
                    yield Message(parts=[MessagePart(content=str(result))])

            except Exception as e:
                # Call on_error callback if provided
                if "on_error" in self.callbacks:
                    self.callbacks["on_error"](e)
                # Re-raise the exception
                raise

    def _wait_for_server_ready(self, timeout: int = 30) -> None:
        """Wait for ACP server to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.acp_base_url}/agents", timeout=2)
                if response.status_code in [200, 404]:  # Server is responding
                    self._server_ready = True
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)

        raise PlatformConnectionError(
            self.acp_base_url, "ACP server failed to start within timeout"
        )

    def _register_with_platform(self) -> None:
        """Register agent with platform."""
        registration_data = {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "acp_base_url": self.acp_base_url,
            "auth_token": self.auth_token,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "contact": self.contact,
            "metadata": self.metadata,
            "input_content_types": self.input_content_types,
            "output_content_types": self.output_content_types,
            "url": self.url,
            "port": self.port,
        }

        try:
            response = requests.post(
                f"{self.platform_url}/platform/agents/register",
                json=registration_data,
                timeout=10,
            )

            if response.status_code == 200:
                self._registered = True
                # Call on_register callback if provided
                if "on_register" in self.callbacks:
                    self.callbacks["on_register"](response.json())
            elif response.status_code == 409:
                raise AgentNameConflictError(self.agent_name, response.json())
            elif response.status_code == 400:
                error_data = response.json()
                if "capabilities" in error_data.get("error", ""):
                    raise AgentCapabilityError(
                        self.capabilities, error_data.get("supported_capabilities")
                    )
                raise AgentManifestError(["invalid_data"], registration_data)
            elif response.status_code == 401:
                raise PlatformAuthenticationError("bearer_token", response.json())
            elif response.status_code == 503:
                raise PlatformUnavailableError(
                    self.platform_url, response.headers.get("Retry-After")
                )
            else:
                raise PlatformConnectionError(
                    self.platform_url, f"HTTP {response.status_code}: {response.text}"
                )

        except requests.exceptions.ConnectionError as e:
            raise PlatformConnectionError(self.platform_url, e)
        except requests.exceptions.Timeout as e:
            raise PlatformConnectionError(self.platform_url, e)
        except requests.exceptions.RequestException as e:
            raise PlatformConnectionError(self.platform_url, e)

    def start(self) -> None:
        """Start the agent and register with platform."""
        try:
            # Configure logging to hide /ping requests
            ping_filter = PingFilter()
            logging.getLogger("uvicorn.access").addFilter(ping_filter)

            # Start ACP server in background thread
            server_thread = threading.Thread(
                target=lambda: self.server.run(port=self.port), daemon=True
            )
            server_thread.start()

            # Wait for server to be ready
            self._wait_for_server_ready()

            # Auto-register with platform
            self._register_with_platform()

            # Keep main thread alive - ACP server runs in main thread
            print(f"Agent '{self.agent_name}' started on {self.acp_base_url}")
            print(f"Registered with platform at {self.platform_url}")

            # Call on_shutdown callback when exiting
            try:
                # Block main thread to keep agent running
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                if "on_shutdown" in self.callbacks:
                    self.callbacks["on_shutdown"]("user_request")
                print(f"\nAgent '{self.agent_name}' shutting down...")

        except Exception as e:
            if "on_error" in self.callbacks:
                self.callbacks["on_error"](e)
            raise

    def stop(self, deregister: bool = True) -> None:
        """Stop the agent gracefully.

        Args:
            deregister: If True, deregister from platform before stopping
        """
        try:
            # Call shutdown callback before deregistration
            if "on_shutdown" in self.callbacks:
                self.callbacks["on_shutdown"]("programmatic_request")

            # Deregister from platform if requested and we're registered
            if deregister and self._registered:
                self._deregister_from_platform()

        except Exception as e:
            logger.error(f"Error during agent shutdown: {e}")
            if "on_error" in self.callbacks:
                self.callbacks["on_error"](e)

    def deregister(self) -> bool:
        """Manually deregister agent from platform without stopping.

        Returns:
            bool: True if deregistration was successful, False otherwise
        """
        try:
            if not self._registered:
                logger.warning("Agent is not registered with platform")
                return False

            self._deregister_from_platform()
            return not self._registered  # Will be False if deregistration succeeded

        except Exception as e:
            logger.error(f"Error during manual deregistration: {e}")
            if "on_error" in self.callbacks:
                self.callbacks["on_error"](e)
            return False

    def _deregister_from_platform(self) -> None:
        """Deregister agent from platform."""
        try:
            response = requests.delete(
                f"{self.platform_url}/platform/agents/{self.agent_name}",
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Agent '{self.agent_name}' deregistered successfully")
                self._registered = False
            elif response.status_code == 404:
                logger.warning(f"Agent '{self.agent_name}' was not found on platform (already removed)")
                self._registered = False
            else:
                logger.error(f"Failed to deregister agent: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error deregistering from platform: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during deregistration: {e}")
        # Note: ACP server doesn't have a clean shutdown method
        # This would need to be implemented based on the actual server implementation