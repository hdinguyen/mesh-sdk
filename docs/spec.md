# Project Specification

## Project Overview
**Project Name:** Agent mesh SDK

## Executive Summary
**One-line description:** SDK enabling seamless integration between agents and platforms using the Agent Communication Protocol (ACP). The platform manages agent orchestration, registration, and workflow control, while agents connect to receive and process messages from the platform.

**Key Objectives:**
- **Framework Agnostic:** Supports DSPy, CrewAI, Google ADK, BeeAI, and custom frameworks
- **ACP Protocol Abstraction:** SDK handles all ACP communication details
- **Callback-Driven:** Event-driven architecture with configurable callbacks
- **Multi-modal Support:** Handles text, images, audio, video via MimeTypes
- **Stateful/Stateless:** Supports both session-based and request-response patterns

**Success Criteria:**
- Agents can register themselves with platform via SDK automatically
- Agents receive and process messages through ACP protocol seamlessly
- Platform acts as ACP gateway routing messages to appropriate agents
- Multi-agent deployment on same machine with automatic port allocation

## Technical Requirements

### System Architecture
**Technology Stack:**
- **Backend:** Python 3.12+
- **Package Management:** uv (https://docs.astral.sh/uv/)
- **Database:** Redis
- **Protocol:** ACP (Agent Communication Protocol) - REST-based HTTP API
- **Linting:** Ruff (https://docs.astral.sh/ruff/)

**Key Components:**
1. **Platform Core** (`platform/src/`) - Acts as ACP gateway, implements standard ACP endpoints, manages agent registration, message routing, and workflow orchestration
2. **Agent SDK** (`agent/src/`) - Provides interface for agents to connect and communicate with platform via ACP protocol
3. **ACP Protocol Integration** - Standard communication protocol handling authentication, message routing, and error handling

**Architecture Pattern:**
- **Agents = ACP Servers:** Each agent runs `acp_sdk.server.Server` 
- **Platform = ACP Client:** Platform uses `acp_sdk.client.Client` to communicate with agents
- **Registration Flow:** Agents register with platform, providing their ACP server URL and auth credentials
- **Message Routing:** Platform receives external ACP requests and routes to appropriate registered agents
- **Auto-Discovery:** Platform immediately verifies agent connections after registration

### Data Models

#### Agent Registration Schema
```python
{
    "agent_name": "string",           # Required: Unique identifier (3-50 alphanumeric + underscores)
    "agent_type": "string",           # Required: dspy, crewai, google_adk, beeai, custom
    "capabilities": ["array"],        # Required: List of agent capabilities (non-empty)
    "acp_base_url": "string",         # Required: Agent's ACP server URL (http://localhost:PORT)
    "auth_token": "string",           # Required: Bearer token for platform to authenticate with agent
    "version": "string",              # Optional: Agent version (default: "1.0.0")
    "description": "string",          # Optional: Agent description
    "tags": ["array"],                # Optional: Categorization tags
    "contact": "string"               # Optional: Maintainer contact
}
```

#### ACP Message Structure
```python
{
    "content": "message_content",
    "metadata": {
        "Content-Type": "mimetype",
        "X-ACP-Version": "protocol_version", 
        "X-ACP-Session-ID": "session_id",
        "X-ACP-Request-ID": "request_id"
    }
}
```

#### Redis Storage Schema
```python
# Agent registration data
"agent:{agent_name}": {
    "agent_name": "string",
    "agent_type": "string", 
    "capabilities": ["array"],
    "acp_base_url": "string",
    "auth_token": "string",
    "status": "active|inactive|error",
    "registered_at": "timestamp",
    "last_verified": "timestamp"
}

# Message queues
"queue:{agent_name}": ["list", "of", "pending", "messages"]

# Session state  
"session:{session_id}": {
    "agent_name": "string",
    "context": "object",
    "created_at": "timestamp",
    "last_activity": "timestamp"
}
```

### API Specifications

#### Platform Architecture
**Platform Role:** Acts as ACP gateway to multiple agents
- **Implements Standard ACP Endpoints:** `/agents`, `/runs`, `/runs/{run_id}`, etc.
- **Agent Registration:** Agents register with platform via custom endpoint
- **Message Routing:** Platform receives ACP requests and routes to registered agents
- **Redis Storage:** Stores agent registration metadata, message queues, session state

#### Platform Registration Endpoint
**Base URL:** `http://localhost:8000` (configurable)
**Authentication:** Bearer token (persistent for MVP)

**Agent Registration:**
```
POST /platform/agents/register
Content-Type: application/json
Authorization: Bearer <optional-token>

{
    "agent_name": "my_agent",
    "agent_type": "custom",
    "capabilities": ["text_generation"],
    "acp_base_url": "http://localhost:8001",
    "auth_token": "xyz123...",
    "version": "1.0.0",
    "description": "My custom agent"
}
```

#### Standard ACP Endpoints (Implemented by Platform)
- `GET /agents` - List all registered agents (ACP standard)
- `GET /agents/{name}` - Get specific agent manifest (ACP standard)
- `POST /runs` - Create and start agent run (ACP standard)
- `GET /runs/{run_id}` - Get run status (ACP standard)
- `POST /runs/{run_id}/cancel` - Cancel agent run (ACP standard)

## Communication Protocol Details

### Agent Communication Protocol (ACP)
**Protocol Reference:** [Agent Communication Protocol](https://agentcommunicationprotocol.dev/)
**Protocol Type:** Open standard under Linux Foundation
**Communication Method:** REST-based HTTP API

### Core Protocol Features
- **REST-based Communication:** Uses standard HTTP patterns and conventions
- **Multi-modal Support:** Handles all message types via MimeTypes
- **Async-first Design:** Built for long-running agent tasks with sync support
- **Offline Discovery:** Agents discoverable even when inactive
- **No SDK Required:** Can be used with standard HTTP tools (curl, Postman, etc.)

### Message Structure
**Content Identification:** Uses MimeTypes for all data formats
**Supported Formats:**
- Text (text/plain, text/markdown, application/json)
- Images (image/*)
- Audio (audio/*)
- Video (video/*)
- Custom binary formats (application/*)

### Agent Architecture
**Agent Implementation Pattern:**
- Agents are **ACP Servers** running `acp_sdk.server.Server`
- Platform is **ACP Client** using `acp_sdk.client.Client`
- Agents register with platform by providing their ACP server URL and auth token
- Platform routes messages to agents using `client.run_sync()` or `client.run_async()`

### Agent Startup Flow
1. **Port Allocation** - SDK finds free port using `portpicker` package
2. **ACP Server Start** - Agent starts ACP server in background thread
3. **Auto-Registration** - SDK automatically registers with platform
4. **Platform Verification** - Platform immediately verifies agent connection
5. **Ready State** - Agent ready to receive messages via ACP protocol

### Message Flow
1. **External Request** - Client sends ACP request to platform
2. **Agent Selection** - Platform selects appropriate registered agent
3. **Message Construction** - Platform builds ACP Message object
4. **Agent Execution** - Platform calls `client.run_sync(agent, messages)`
5. **Response Processing** - Platform receives and returns agent response

### Agent Manifest
**Required Metadata:**
```json
{
  "agent_name": "string",
  "version": "string",
  "description": "string",
  "capabilities": ["array of supported operations"],
  "input_schema": "JSON schema for input validation",
  "output_schema": "JSON schema for output validation",
  "tags": ["array of categories"],
  "contact": "agent maintainer contact info"
}
```

### Message Metadata
**Standard Headers:**
- `Content-Type`: MimeType of the message content
- `X-ACP-Version`: Protocol version being used
- `X-ACP-Session-ID`: Session identifier for stateful operations
- `X-ACP-Request-ID`: Unique request identifier for tracking

### Error Handling
**Standard Error Response Format:**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error description",
    "details": "Additional error context",
    "timestamp": "ISO 8601 timestamp"
  }
}
```

**Common Error Codes:**
- `ACP_001`: Agent not found
- `ACP_002`: Invalid message format
- `ACP_003`: Agent busy/unavailable
- `ACP_004`: Authentication failed
- `ACP_005`: Rate limit exceeded

### Stateful vs Stateless Operations
**Stateful Agents:**
- Maintain session state across requests
- Use `X-ACP-Session-ID` header
- Support long-running operations
- Can store context between messages

**Stateless Agents:**
- Process each request independently
- No session persistence required
- Faster response times
- Easier to scale horizontally

### Distributed Sessions
**Session Management:**
- Sessions can span multiple agent instances
- Session state shared via platform storage
- Automatic session cleanup on timeout
- Session recovery mechanisms

## SDK Implementation Details

### Core SDK Architecture
**AgentSDK Class Responsibilities:**
- **ACP Server Management:** Wraps `acp_sdk.server.Server` with automatic setup
- **Port Allocation:** Uses `portpicker` to find available ports (starting from 8000)
- **Authentication:** Generates bearer tokens using `secrets.token_urlsafe(32)`
- **Platform Registration:** Automatically registers with platform on startup
- **Threading Model:** ACP server runs in main thread, registration in background
- **Error Handling:** Fail-fast approach with clear exception messages
- **Callback System:** Event-driven callbacks for registration, errors, etc.

### Required Dependencies
**Auto-installed packages:**
```python
required_packages = [
    "acp-sdk",      # ACP protocol implementation
    "portpicker",   # Automatic port allocation
    "requests",     # HTTP client for platform registration
]
```

### Configuration Priority
**Platform URL Resolution:**
1. **Environment Variable:** `PLATFORM_BASE_URL` (highest priority)
2. **Constructor Parameter:** `platform_url` parameter
3. **Default Value:** `http://localhost:8000` (fallback)

```python
import os
platform_url = os.getenv("PLATFORM_BASE_URL") or platform_url or "http://localhost:8000"
```

### Required Registration Fields
**Mandatory fields for agent registration:**
- `agent_name`: Unique identifier (3-50 alphanumeric chars + underscores)
- `agent_type`: Framework type (dspy, crewai, google_adk, beeai, custom)  
- `capabilities`: Non-empty array of capability strings
- `process_function`: Callable function to handle messages

**Auto-generated fields:**
- `acp_base_url`: Generated from allocated port
- `auth_token`: Generated using `secrets.token_urlsafe(32)`
- `version`: Defaults to "1.0.0"

### Agent Startup Sequence
**Detailed startup flow:**
1. **SDK Initialization:** Validate required fields, allocate port, generate auth token
2. **ACP Server Setup:** Create server instance and register agent handler function
3. **Background Thread Start:** Launch ACP server in daemon thread
4. **Server Ready Check:** Poll localhost:port until server responds
5. **Platform Registration:** POST to `/platform/agents/register` with agent data
6. **Platform Verification:** Platform immediately calls agent to verify connection
7. **Callback Execution:** Call `on_register` callback if successful
8. **Main Thread Block:** `server.run()` keeps main thread alive

### Integration Patterns
**SDK Architecture:** The Agent mesh SDK wraps the ACP server, handles platform registration, and provides a simple interface for agent developers.

**Technical Implementation:**
```python
# SDK wraps ACP server and handles platform integration
from acp_sdk.server import Server
from acp_sdk.models import Message, MessagePart
import portpicker
import threading
import requests

class AgentSDK:
    def __init__(self, agent_name, agent_type, capabilities, process_function, 
                 platform_url="http://localhost:8000", callbacks=None):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.process_function = process_function
        self.platform_url = platform_url
        self.callbacks = callbacks or {}
        
        # Auto-allocate port for ACP server
        self.port = portpicker.pick_unused_port()
        self.acp_base_url = f"http://localhost:{self.port}"
        
        # Generate auth token for platform communication
        import secrets
        self.auth_token = secrets.token_urlsafe(32)
        
        # Create ACP server
        self.server = Server()
        self._setup_acp_agent()
    
    def _setup_acp_agent(self):
        @self.server.agent()
        async def agent_handler(input: list[Message], context) -> AsyncGenerator:
            # Call user's process function
            result = self.process_function(input)
            # Convert result to ACP Message format
            yield Message(parts=[MessagePart(content=result['content'])])
    
    def start(self):
        # Start ACP server in background thread
        server_thread = threading.Thread(
            target=lambda: self.server.run(port=self.port), 
            daemon=True
        )
        server_thread.start()
        
        # Wait for server to be ready
        self._wait_for_server_ready()
        
        # Auto-register with platform
        self._register_with_platform()
        
        # Keep main thread alive
        self.server.run(port=self.port)  # This blocks
    
    def _register_with_platform(self):
        registration_data = {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "acp_base_url": self.acp_base_url,
            "auth_token": self.auth_token,
            "version": "1.0.0"
        }
        
        response = requests.post(
            f"{self.platform_url}/platform/agents/register",
            json=registration_data
        )
        
        if response.status_code == 200:
            self.callbacks.get('on_register', lambda x: None)(response.json())
        else:
            self.callbacks.get('on_error', lambda x: None)(response.json())
```

**Framework Integration Examples:**

**DSPy Integration:**
```python
from mesh_sdk import AgentSDK

class MyDSPyAgent:
    def __init__(self):
        self.dspy_agent = YourDSPyImplementation()
        
        self.sdk = AgentSDK(
            agent_name="my_dspy_agent",
            agent_type="dspy",
            capabilities=["text_generation", "reasoning"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_error": self.on_error
            }
        )
    
    def process_message(self, messages):
        # messages is list[Message] from ACP
        content = messages[0].parts[0].content
        result = self.dspy_agent(content)
        return {"content": result, "metadata": {"confidence": 0.95}}
    
    def start(self):
        self.sdk.start()  # Starts ACP server and auto-registers
    
    def on_register(self, registration_data):
        print(f"Agent registered: {registration_data}")
    
    def on_error(self, error):
        print(f"Error: {error}")

agent = MyDSPyAgent()
agent.start()
```

**CrewAI Integration:**
```python
# CrewAI agent with SDK handling ACP communication
from mesh_sdk import AgentSDK

class MyCrewAIAgent:
    def __init__(self):
        # Initialize CrewAI agent
        self.crew_agent = YourCrewAIImplementation()
        
        # SDK manages ACP protocol
        self.sdk = AgentSDK(
            agent_name="my_crewai_agent",
            agent_type="crewai",
            capabilities=["task_execution", "team_coordination"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown
            }
        )
    
    def process_message(self, message):
        # Your CrewAI logic - SDK handles ACP details
        task = message.content
        result = self.crew_agent.execute(task)
        return {"content": result, "metadata": {"status": "completed"}}
    
    def start(self):
        # SDK handles all ACP communication
        self.sdk.start()
```

**Google ADK Integration:**
```python
# Google ADK agent with SDK ACP handling
from mesh_sdk import AgentSDK

class MyGoogleADKAgent:
    def __init__(self):
        # Initialize Google ADK agent
        self.adk_agent = YourGoogleADKImplementation()
        
        # SDK manages ACP protocol
        self.sdk = AgentSDK(
            agent_name="my_google_adk_agent",
            agent_type="google_adk",
            capabilities=["assistant_actions", "tool_calling"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown
            }
        )
    
    def process_message(self, message):
        # Your Google ADK logic
        adk_request = message.content
        result = self.adk_agent.process(adk_request)
        return {"content": result, "metadata": {"tools_used": result.tools}}
    
    def start(self):
        # SDK handles ACP registration and communication
        self.sdk.start()
```

**BeeAI Integration:**
```python
# BeeAI agent with SDK ACP handling
from mesh_sdk import AgentSDK

class MyBeeAIAgent:
    def __init__(self):
        # Initialize BeeAI agent
        self.beeai_agent = YourBeeAIImplementation()
        
        # SDK manages ACP protocol
        self.sdk = AgentSDK(
            agent_name="my_beeai_agent",
            agent_type="beeai",
            capabilities=["workflow_execution", "data_processing"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown
            }
        )
    
    def process_message(self, message):
        # Your BeeAI logic
        workflow_input = message.content
        result = self.beeai_agent.run_workflow(workflow_input)
        return {"content": result, "metadata": {"workflow_id": result.id}}
    
    def start(self):
        # SDK handles all ACP communication
        self.sdk.start()
```

**Custom Agent Integration:**
```python
# Any custom agent framework
from mesh_sdk import AgentSDK

class MyCustomAgent:
    def __init__(self):
        # Your custom agent implementation
        self.custom_agent = YourCustomImplementation()
        
        # SDK handles ACP protocol regardless of framework
        self.sdk = AgentSDK(
            agent_name="my_custom_agent",
            agent_type="custom",
            capabilities=["custom_capability"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown
            }
        )
    
    def process_message(self, message):
        # Your custom logic here
        custom_input = message.content
        result = self.custom_agent.process(custom_input)
        return {"content": result, "metadata": {"custom_field": "value"}}
    
    def start(self):
        # SDK handles ACP communication
        self.sdk.start()
```

### Error Handling Strategy
**Fail-Fast Philosophy:**
- **Registration Failures:** Raise exception immediately, no retries
- **Platform Connection Errors:** Raise exception immediately, no retries  
- **Verification Failures:** Raise exception immediately, no retries
- **Clear Error Messages:** Provide detailed error information for debugging
- **No Automatic Recovery:** Users must handle errors explicitly

**Exception Types:**
```python
class AgentRegistrationError(Exception):
    """Base exception for agent registration failures"""
    pass

class AgentNameConflictError(AgentRegistrationError):
    """Agent name already exists in platform"""
    pass

class PlatformConnectionError(AgentRegistrationError):
    """Unable to connect to platform"""
    pass

class PlatformVerificationError(AgentRegistrationError):
    """Platform failed to verify agent connection"""
    pass
```

### Callback System
**Available Callbacks:**
```python
callbacks = {
    "on_register": callback_function,      # Called after successful registration
    "on_message": callback_function,       # Called when message received (before processing)
    "on_error": callback_function,         # Called when error occurs during processing
    "on_shutdown": callback_function,      # Called during shutdown
    "on_health_check": callback_function,  # Called during health checks
}
```

**Callback Function Signatures:**
```python
def on_register(registration_data: dict) -> None:
    """Called when agent successfully registers with platform"""
    # registration_data contains platform response
    pass

def on_message(messages: list[Message]) -> None:
    """Called when message received (before processing)"""
    # messages is ACP Message list from platform
    pass

def on_error(error: Exception) -> None:
    """Called when error occurs during processing"""
    # error is the exception that occurred
    pass

def on_shutdown(reason: str) -> None:
    """Called during agent shutdown"""
    # reason: "user_request", "platform_request", "error"
    pass

def on_health_check() -> dict:
    """Called during platform health checks"""
    return {"status": "healthy", "details": "Agent running normally"}
```

## Platform Implementation Details

### Platform Core Responsibilities
**ACP Gateway Functions:**
- **Implement Standard ACP Endpoints:** `/agents`, `/runs`, `/runs/{run_id}`, etc.
- **Agent Registry Management:** Store agent metadata in Redis
- **Message Routing:** Route incoming ACP requests to appropriate agents
- **Agent Verification:** Verify agent connections after registration
- **Session Management:** Handle stateful operations via Redis
- **Health Monitoring:** Monitor agent status and availability

### Platform-to-Agent Communication
**Message Flow:**
1. **External ACP Request:** Client sends `POST /runs` to platform
2. **Agent Selection:** Platform selects agent based on capabilities/name
3. **ACP Client Call:** Platform uses `client.run_sync(agent="name", input=messages)`
4. **Agent Processing:** Agent receives messages via ACP server handler
5. **Response Return:** Platform returns agent response to original client

**Platform ACP Client Usage:**
```python
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

async def execute_agent(agent_name: str, content: str):
    agent_data = redis.get(f"agent:{agent_name}")
    
    async with Client(
        base_url=agent_data["acp_base_url"],
        headers={"Authorization": f"Bearer {agent_data['auth_token']}"}
    ) as client:
        run = await client.run_sync(
            agent=agent_name,
            input=[Message(parts=[MessagePart(content=content)])]
        )
        return run.output
```

### Agent Verification Process
**Platform verifies agents immediately after registration:**
1. **Registration Received:** Platform receives agent registration
2. **Store in Redis:** Save agent data to Redis
3. **Immediate Verification:** Platform calls agent's ACP endpoint to verify
4. **Health Check:** Send test message to ensure agent is responsive
5. **Mark Active:** Update agent status to "active" if verification succeeds
6. **Registration Response:** Return success/error to agent

### Development Commands
**Standard uv commands for development:**
```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check .

# Format code  
uv run ruff format .

# Run platform
uv run python -m platform

# Run agent examples
uv run python -m agent
```

**Callback Usage Examples:**
```python
# Minimal callback usage
callbacks = {
    "on_register": lambda data: print(f"Registered: {data}"),
    "on_error": lambda error: print(f"Error: {error}")
}

# Advanced callback usage with custom logic
class AdvancedAgent:
    def __init__(self):
        self.sdk = AgentSDK(
            agent_name="advanced_agent",
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown,
                "on_health_check": self.on_health_check
            }
        )
    
    def on_register(self, registration_data):
        # Initialize resources after registration
        self.agent_id = registration_data["agent_id"]
        self.session_token = registration_data["session_token"]
        self.initialize_resources()
    
    def on_message_received(self, message):
        # Log and validate incoming messages
        self.log_message(message)
        if not self.validate_message(message):
            raise ValueError("Invalid message format")
    
    def on_error(self, error):
        # Implement retry logic or fallback behavior
        if error.code == "ACP_003":  # Agent busy
            self.retry_later()
        elif error.code == "ACP_004":  # Authentication failed
            self.reauthenticate()
    
    def on_shutdown(self, reason):
        # Cleanup resources and save state
        self.save_current_state()
        self.cleanup_resources()
        self.notify_dependencies()
    
    def on_health_check(self, health_data):
        # Return detailed health status
        return {
            "status": "healthy",
            "memory_usage": self.get_memory_usage(),
            "processing_queue": len(self.queue),
            "last_activity": self.last_activity_time
        }
```

### SDK Responsibilities
**The Agent mesh SDK handles:**
- **ACP Registration**: Automatic agent registration with platform
- **Message Routing**: Receiving and parsing ACP messages
- **Protocol Translation**: Converting ACP format to agent-friendly format
- **Response Formatting**: Converting agent responses to ACP format
- **Error Handling**: ACP-compliant error responses
- **Session Management**: ACP session handling for stateful agents
- **Health Checks**: Platform health monitoring
- **Deregistration**: Clean agent shutdown
- **Callback Management**: Invoking registered callbacks at appropriate events

### Agent Developer Responsibilities
**Agent developers only need to:**
- Implement their core agent logic
- Define agent capabilities and metadata
- Handle their framework-specific processing
- Return results in a simple format

### Integration Benefits
- **Framework Agnostic**: Works with any agent framework
- **Protocol Abstraction**: Developers don't need to learn ACP
- **Rapid Integration**: Minimal code changes required
- **Consistent Interface**: Standardized integration pattern
- **Automatic Updates**: SDK handles protocol version updates

## Error Handling & Recovery

### Registration Exceptions
**Custom Exceptions for Registration Failures:**

```python
class AgentRegistrationError(Exception):
    """Base exception for agent registration failures"""
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details

class AgentNameConflictError(AgentRegistrationError):
    """Raised when agent name already exists in platform"""
    def __init__(self, agent_name, existing_agent_info=None):
        message = f"Agent name '{agent_name}' is already registered"
        super().__init__(message, "REG_001", {"existing_agent": existing_agent_info})

class AgentCapabilityError(AgentRegistrationError):
    """Raised when agent capabilities are invalid or unsupported"""
    def __init__(self, invalid_capabilities, supported_capabilities=None):
        message = f"Invalid capabilities: {invalid_capabilities}"
        super().__init__(message, "REG_002", {"supported": supported_capabilities})

class AgentManifestError(AgentRegistrationError):
    """Raised when agent manifest is malformed or incomplete"""
    def __init__(self, missing_fields, manifest_data=None):
        message = f"Invalid manifest - missing fields: {missing_fields}"
        super().__init__(message, "REG_003", {"manifest": manifest_data})

class MissingRequiredFieldsError(AgentRegistrationError):
    """Raised when required fields are missing from agent registration"""
    def __init__(self, missing_fields, required_fields=None, provided_fields=None):
        message = f"Missing required fields: {missing_fields}"
        super().__init__(message, "REG_004", {
            "missing_fields": missing_fields,
            "required_fields": required_fields,
            "provided_fields": provided_fields
        })

class PlatformConnectionError(AgentRegistrationError):
    """Raised when unable to connect to platform"""
    def __init__(self, platform_url, connection_error=None):
        message = f"Unable to connect to platform at {platform_url}"
        super().__init__(message, "REG_005", {"connection_error": str(connection_error)})

class PlatformAuthenticationError(AgentRegistrationError):
    """Raised when platform authentication fails"""
    def __init__(self, auth_method, auth_error=None):
        message = f"Platform authentication failed using {auth_method}"
        super().__init__(message, "REG_006", {"auth_error": auth_error})

class PlatformUnavailableError(AgentRegistrationError):
    """Raised when platform is temporarily unavailable"""
    def __init__(self, platform_url, retry_after=None):
        message = f"Platform at {platform_url} is temporarily unavailable"
        super().__init__(message, "REG_007", {"retry_after": retry_after})
```

### Registration Error Handling
**SDK Registration Error Handling:**

```python
class AgentSDK:
    def register_with_platform(self):
        """Register agent with platform with comprehensive error handling"""
        try:
            # Validate agent manifest before registration
            self._validate_manifest()
            
            # Attempt platform connection
            self._connect_to_platform()
            
            # Send registration request
            response = self._send_registration_request()
            
            # Handle successful registration
            self._handle_successful_registration(response)
            
        except AgentNameConflictError as e:
            # Handle name conflict - suggest alternative name
            self._handle_name_conflict(e)
            
        except AgentCapabilityError as e:
            # Handle capability mismatch - filter or update capabilities
            self._handle_capability_error(e)
            
        except AgentManifestError as e:
            # Handle manifest issues - provide guidance on fixing
            self._handle_manifest_error(e)
            
        except MissingRequiredFieldsError as e:
            # Handle missing required fields - provide field requirements
            self._handle_missing_fields_error(e)
            
        except PlatformConnectionError as e:
            # Handle connection issues - implement retry logic
            self._handle_connection_error(e)
            
        except PlatformAuthenticationError as e:
            # Handle authentication issues - prompt for credentials
            self._handle_authentication_error(e)
            
        except PlatformUnavailableError as e:
            # Handle platform unavailability - implement backoff strategy
            self._handle_platform_unavailable(e)
            
        except Exception as e:
            # Handle unexpected errors
            self._handle_unexpected_error(e)
    
    def _handle_name_conflict(self, error):
        """Handle agent name conflict"""
        suggested_name = self._generate_unique_name()
        raise AgentNameConflictError(
            self.agent_name,
            f"Suggested alternative name: {suggested_name}"
        )
    
    def _handle_capability_error(self, error):
        """Handle capability validation error"""
        # Filter out unsupported capabilities
        supported_caps = self._filter_supported_capabilities()
        if not supported_caps:
            raise AgentCapabilityError(
                self.capabilities,
                "No supported capabilities found"
            )
        # Retry registration with filtered capabilities
        self.capabilities = supported_caps
        self.register_with_platform()
    
    def _handle_manifest_error(self, error):
        """Handle manifest validation error"""
        # Provide detailed guidance on fixing manifest
        guidance = self._generate_manifest_guidance(error.details)
        raise AgentManifestError(
            error.details.get("missing_fields", []),
            {"guidance": guidance, "example_manifest": self._get_example_manifest()}
        )
    
    def _handle_missing_fields_error(self, error):
        """Handle missing required fields error"""
        # Provide detailed guidance on required fields
        missing_fields = error.details.get("missing_fields", [])
        required_fields = error.details.get("required_fields", [])
        provided_fields = error.details.get("provided_fields", [])
        
        guidance = self._generate_required_fields_guidance(missing_fields, required_fields)
        example_data = self._get_example_registration_data()
        
        raise MissingRequiredFieldsError(
            missing_fields,
            {
                "guidance": guidance,
                "example_data": example_data,
                "provided_fields": provided_fields,
                "all_required_fields": required_fields
            }
        )
    
    def _handle_connection_error(self, error):
        """Handle platform connection error"""
        # Implement exponential backoff retry
        if self._should_retry_connection():
            time.sleep(self._get_retry_delay())
            self.register_with_platform()
        else:
            raise PlatformConnectionError(
                self.platform_url,
                "Max retry attempts exceeded"
            )
    
    def _handle_authentication_error(self, error):
        """Handle platform authentication error"""
        # Prompt for updated credentials or token
        new_credentials = self._prompt_for_credentials()
        if new_credentials:
            self.credentials = new_credentials
            self.register_with_platform()
        else:
            raise PlatformAuthenticationError(
                self.auth_method,
                "No valid credentials provided"
            )
    
    def _handle_platform_unavailable(self, error):
        """Handle platform unavailability"""
        retry_after = error.details.get("retry_after", 60)
        if self._should_retry_platform():
            time.sleep(retry_after)
            self.register_with_platform()
        else:
            raise PlatformUnavailableError(
                self.platform_url,
                "Platform unavailable after retry attempts"
            )
```

### Error Recovery Strategies
**Automatic Recovery Patterns:**

```python
class RegistrationRecovery:
    """Handles automatic recovery from registration failures"""
    
    def __init__(self, max_retries=3, base_delay=1):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_count = 0
    
    def attempt_registration_recovery(self, error):
        """Attempt to recover from registration error"""
        if isinstance(error, AgentNameConflictError):
            return self._recover_name_conflict(error)
        elif isinstance(error, AgentCapabilityError):
            return self._recover_capability_error(error)
        elif isinstance(error, MissingRequiredFieldsError):
            return self._recover_missing_fields_error(error)
        elif isinstance(error, PlatformConnectionError):
            return self._recover_connection_error(error)
        elif isinstance(error, PlatformUnavailableError):
            return self._recover_platform_unavailable(error)
        else:
            return False  # No automatic recovery for other errors
    
    def _recover_name_conflict(self, error):
        """Recover from name conflict by generating unique name"""
        new_name = self._generate_unique_name()
        self.agent_name = new_name
        return True  # Retry registration with new name
    
    def _recover_capability_error(self, error):
        """Recover from capability error by filtering capabilities"""
        supported_caps = self._get_supported_capabilities()
        if supported_caps:
            self.capabilities = supported_caps
            return True  # Retry registration with filtered capabilities
        return False
    
    def _recover_missing_fields_error(self, error):
        """Recover from missing fields error by prompting for required fields"""
        missing_fields = error.details.get("missing_fields", [])
        required_fields = error.details.get("required_fields", [])
        
        # Try to auto-fill missing fields with defaults where possible
        auto_filled = self._auto_fill_missing_fields(missing_fields)
        
        # For fields that can't be auto-filled, prompt user
        remaining_fields = [field for field in missing_fields if field not in auto_filled]
        if remaining_fields:
            user_filled = self._prompt_for_missing_fields(remaining_fields, required_fields)
            if user_filled:
                # Update registration data with filled fields
                self._update_registration_data(user_filled)
                return True  # Retry registration with filled fields
            else:
                return False  # User didn't provide required fields
        else:
            # All fields were auto-filled
            return True  # Retry registration with auto-filled fields
    
    def _recover_connection_error(self, error):
        """Recover from connection error with exponential backoff"""
        if self.retry_count < self.max_retries:
            delay = self.base_delay * (2 ** self.retry_count)
            time.sleep(delay)
            self.retry_count += 1
            return True  # Retry connection
        return False
    
    def _recover_platform_unavailable(self, error):
        """Recover from platform unavailability"""
        retry_after = error.details.get("retry_after", 60)
        if self.retry_count < self.max_retries:
            time.sleep(retry_after)
            self.retry_count += 1
            return True  # Retry after platform delay
        return False
```

### Required Fields Validation
**Agent Registration Required Fields:**

```python
REQUIRED_REGISTRATION_FIELDS = {
    "agent_name": {
        "type": "string",
        "required": True,
        "description": "Unique identifier for the agent",
        "validation": "Must be alphanumeric with underscores, 3-50 characters",
        "example": "my_text_generation_agent"
    },
    "agent_type": {
        "type": "string", 
        "required": True,
        "description": "Type/category of the agent",
        "validation": "Must be one of predefined agent types",
        "example": "dspy, crewai, google_adk, beeai, custom"
    },
    "capabilities": {
        "type": "array",
        "required": True,
        "description": "List of agent capabilities",
        "validation": "Must be non-empty array of strings",
        "example": ["text_generation", "reasoning", "data_processing"]
    },
    "process_function": {
        "type": "function",
        "required": True,
        "description": "Function to process incoming messages",
        "validation": "Must be callable function",
        "example": "self.process_message"
    }
}

OPTIONAL_REGISTRATION_FIELDS = {
    "version": {
        "type": "string",
        "required": False,
        "description": "Agent version",
        "default": "1.0.0",
        "example": "2.1.0"
    },
    "description": {
        "type": "string",
        "required": False,
        "description": "Agent description",
        "default": "",
        "example": "A text generation agent built with DSPy"
    },
    "tags": {
        "type": "array",
        "required": False,
        "description": "Agent tags for categorization",
        "default": [],
        "example": ["nlp", "text-generation", "dspy"]
    },
    "contact": {
        "type": "string",
        "required": False,
        "description": "Contact information for agent maintainer",
        "default": "",
        "example": "developer@example.com"
    },
    "callbacks": {
        "type": "dict",
        "required": False,
        "description": "Event callback functions",
        "default": {},
        "example": {"on_register": self.on_register, "on_error": self.on_error}
    }
}

def validate_registration_fields(registration_data):
    """Validate agent registration data against required fields"""
    missing_fields = []
    invalid_fields = []
    
    # Check required fields
    for field_name, field_spec in REQUIRED_REGISTRATION_FIELDS.items():
        if field_name not in registration_data:
            missing_fields.append(field_name)
        else:
            # Validate field value
            if not _validate_field_value(registration_data[field_name], field_spec):
                invalid_fields.append(field_name)
    
    # Check for invalid optional fields
    for field_name in registration_data:
        if field_name not in REQUIRED_REGISTRATION_FIELDS and field_name not in OPTIONAL_REGISTRATION_FIELDS:
            invalid_fields.append(field_name)
    
    if missing_fields or invalid_fields:
        raise MissingRequiredFieldsError(
            missing_fields,
            list(REQUIRED_REGISTRATION_FIELDS.keys()),
            list(registration_data.keys())
        )
    
    return True

def _validate_field_value(value, field_spec):
    """Validate individual field value against specification"""
    if field_spec["type"] == "string":
        return isinstance(value, str) and len(value) > 0
    elif field_spec["type"] == "array":
        return isinstance(value, list) and len(value) > 0
    elif field_spec["type"] == "function":
        return callable(value)
    elif field_spec["type"] == "dict":
        return isinstance(value, dict)
    return True
```

### Error Reporting and Logging
**Structured Error Reporting:**

```python
class RegistrationErrorLogger:
    """Handles structured logging of registration errors"""
    
    def log_registration_error(self, error, context=None):
        """Log registration error with structured data"""
        error_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_code": getattr(error, 'error_code', None),
            "error_message": str(error),
            "error_details": getattr(error, 'details', {}),
            "agent_name": getattr(self, 'agent_name', 'unknown'),
            "platform_url": getattr(self, 'platform_url', 'unknown'),
            "context": context or {}
        }
        
        # Log to appropriate destination
        self._write_error_log(error_log)
        
        # Send error report if configured
        if self._should_report_error(error):
            self._send_error_report(error_log)
    
    def _should_report_error(self, error):
        """Determine if error should be reported to monitoring system"""
        # Report all authentication and connection errors
        if isinstance(error, (PlatformAuthenticationError, PlatformConnectionError)):
            return True
        # Report manifest errors for debugging
        if isinstance(error, AgentManifestError):
            return True
        # Don't report name conflicts (expected behavior)
        if isinstance(error, AgentNameConflictError):
            return False
        return False
```

### Protocol Versioning
**Version Compatibility:**
- Backward compatibility maintained within major versions
- Version negotiation during agent discovery
- Deprecation warnings for older protocol versions
- Migration guides for version updates

### Security Considerations
**Authentication Methods:**
- API Key authentication
- OAuth 2.0 integration
- JWT token validation
- Certificate-based authentication

**Authorization:**
- Role-based access control (RBAC)
- Capability-based permissions
- Resource-level access control
- Audit logging for all operations

## Security & Authentication

### ACP-Level Authentication
**Authentication handled by ACP protocol, not SDK:**

The Agent mesh SDK relies on the ACP (Agent Communication Protocol) for authentication. The platform handles authentication for all incoming requests, and the ACP SDK manages authentication for outgoing messages to the platform.

### Platform Authentication
**Platform-side authentication for incoming requests:**

```python
# Platform authentication middleware example
class PlatformAuthenticationMiddleware:
    """Platform middleware for authenticating incoming requests"""
    
    def __init__(self, auth_enabled: bool = True):
        self.auth_enabled = auth_enabled
    
    def authenticate_request(self, request_headers: Dict[str, str]) -> bool:
        """Authenticate incoming request to platform"""
        if not self.auth_enabled:
            return True
        
        auth_header = request_headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        return self._validate_token(token)
    
    def _validate_token(self, token: str) -> bool:
        """Validate bearer token against platform records"""
        # Platform-specific token validation logic
        # This would check against stored valid tokens
        return True  # Simplified for example
```

### ACP Client Authentication
**ACP SDK handles authentication for platform communication:**

```python
from acp_sdk.client import Client

class ACPAuthenticatedClient:
    """ACP client with authentication for platform communication"""
    
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {}
        
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
    
    async def send_message_to_platform(self, agent_name: str, message: str):
        """Send authenticated message to platform via ACP"""
        async with Client(
            base_url=self.base_url,
            headers=self.headers
        ) as client:
            run = await client.run_sync(agent=agent_name, input=message)
            return run
    
    async def register_agent_with_platform(self, agent_data: Dict):
        """Register agent with platform via ACP"""
        async with Client(
            base_url=self.base_url,
            headers=self.headers
        ) as client:
            # ACP registration logic
            registration = await client.register_agent(agent_data)
            return registration
```

### Agent SDK Integration with ACP
**Simplified Agent SDK using ACP authentication:**

```python
class AgentSDK:
    def __init__(self, agent_name: str, agent_type: str, capabilities: list, 
                 process_function: callable, acp_base_url: str, 
                 auth_token: str = None, callbacks: Optional[Dict] = None):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.process_function = process_function
        self.callbacks = callbacks or {}
        
        # ACP client with authentication
        self.acp_client = ACPAuthenticatedClient(acp_base_url, auth_token)
        
        # Validate registration fields
        self._validate_registration_fields()
    
    async def register_with_platform(self):
        """Register agent with platform via ACP"""
        try:
            registration_data = {
                "agent_name": self.agent_name,
                "agent_type": self.agent_type,
                "capabilities": self.capabilities
            }
            
            # Use ACP client for registration
            response = await self.acp_client.register_agent_with_platform(registration_data)
            
            # Handle successful registration
            self._handle_successful_registration(response)
            
        except Exception as e:
            self._handle_registration_error(e)
    
    async def send_message_to_platform(self, message: str):
        """Send message to platform via ACP"""
        try:
            response = await self.acp_client.send_message_to_platform(
                self.agent_name, 
                message
            )
            return response
        except Exception as e:
            self._handle_message_error(e)
```

### Authentication Configuration
**Simple authentication setup for agents:**

```python
# No authentication (development mode)
agent_sdk = AgentSDK(
    agent_name="my_agent",
    agent_type="dspy",
    capabilities=["text_generation"],
    process_function=process_message,
    acp_base_url="http://localhost:8000"
)

# With authentication token
agent_sdk = AgentSDK(
    agent_name="my_agent",
    agent_type="dspy",
    capabilities=["text_generation"],
    process_function=process_message,
    acp_base_url="https://platform.example.com",
    auth_token="your-bearer-token-here"
)

# Token from environment variable
import os
agent_sdk = AgentSDK(
    agent_name="my_agent",
    agent_type="dspy",
    capabilities=["text_generation"],
    process_function=process_message,
    acp_base_url="https://platform.example.com",
    auth_token=os.getenv("ACP_AUTH_TOKEN")
)
```

### Platform Token Management
**Platform-side token generation and validation:**

```python
class PlatformTokenManager:
    """Platform utility for managing authentication tokens"""
    
    @staticmethod
    def generate_agent_token(agent_name: str, capabilities: list) -> str:
        """Generate bearer token for agent authentication"""
        import secrets
        import jwt
        from datetime import datetime, timedelta
        
        # Create token payload
        payload = {
            "agent_name": agent_name,
            "capabilities": capabilities,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=90),
            "token_type": "agent_auth"
        }
        
        # Sign with platform secret
        platform_secret = os.getenv("PLATFORM_SECRET_KEY")
        token = jwt.encode(payload, platform_secret, algorithm="HS256")
        
        return token
    
    @staticmethod
    def validate_agent_token(token: str) -> Dict[str, Any]:
        """Validate agent token and extract information"""
        import jwt
        
        try:
            platform_secret = os.getenv("PLATFORM_SECRET_KEY")
            payload = jwt.decode(token, platform_secret, algorithms=["HS256"])
            
            return {
                "valid": True,
                "agent_name": payload.get("agent_name"),
                "capabilities": payload.get("capabilities"),
                "expires_at": payload.get("exp")
            }
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"valid": False, "error": "Invalid token"}
```

### Security Considerations
**Authentication security guidelines:**

```python
class SecurityGuidelines:
    """Security guidelines for ACP authentication"""
    
    @staticmethod
    def token_security_best_practices():
        """Best practices for token security"""
        return {
            "token_generation": "Use cryptographically secure random generation",
            "token_storage": "Store tokens in environment variables or secure vaults",
            "token_transmission": "Always use HTTPS for token transmission",
            "token_rotation": "Rotate tokens regularly (90 days recommended)",
            "token_scope": "Limit token scope to specific agent capabilities",
            "audit_logging": "Log all authentication attempts and token usage"
        }
    
    @staticmethod
    def platform_security_requirements():
        """Security requirements for platform implementation"""
        return {
            "authentication_middleware": "Implement authentication for all endpoints",
            "token_validation": "Validate all incoming tokens",
            "rate_limiting": "Implement rate limiting for authentication endpoints",
            "error_handling": "Provide generic error messages to prevent enumeration",
            "monitoring": "Monitor authentication failures and suspicious activity"
        }
```

**File Structure:**
```
mesh_sdk/
├── platform/
│   └── core/
│   └── util/
│   └── ...../
├── agent/
│   └── examples/
│   └── ...../
├── docs/
└── README.md
```

## Success Metrics

### Technical Metrics
- Platform - Platform success run and serve the connection with other agent
- Platform - platform able to create, manage and orchestration agents
- Agent - Agent able to connect and serving request from the Platform


## Implementation Clarifications (Updated)

### Architecture Decisions
**Platform Role:**
- Acts as **ACP Gateway** to multiple registered agents
- Implements standard ACP endpoints (`/agents`, `/runs`, etc.)
- Maintains separate agent registry in Redis
- Routes ACP requests to appropriate registered agents

**Agent Implementation:**
- Agents are **ACP Servers** using `acp_sdk.server.Server`
- Platform is **ACP Client** using `acp_sdk.client.Client`
- Agents call platform registration endpoint with their ACP server details
- Platform uses `client.run_sync(agent="name", input=messages)` to execute agents

### Port Allocation Strategy
**Multiple Agent Support:**
- Use `portpicker` package: `uv add portpicker`
- SDK auto-allocates free ports starting from 8000
- Alternative: Built-in socket binding with fallback ranges

```python
import portpicker
port = portpicker.pick_unused_port()

# Or manual implementation:
def find_free_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free port found")
```

### Authentication Design
**Simple Bearer Token Authentication:**
- Agents generate persistent auth tokens on startup
- Tokens included in registration payload for platform verification
- Platform uses tokens when calling agent ACP endpoints
- Tokens stored in Redis with agent registration data

```python
import secrets
auth_token = secrets.token_urlsafe(32)  # Generate 32-byte token
```

### Threading Model
**Auto-Registration Flow:**
1. **Main Thread:** ACP server runs and blocks with `server.run()`
2. **Background Thread:** Handles server startup detection and registration
3. **Registration Process:**
   - Wait for ACP server to be ready (port listening)
   - Call platform registration endpoint
   - Handle registration response
   - Platform immediately verifies agent connection

```python
def start(self):
    # Start ACP server in background thread
    server_thread = threading.Thread(
        target=lambda: self.server.run(port=self.port), 
        daemon=True
    )
    server_thread.start()
    
    # Wait for server ready, then register
    self._wait_for_server_ready()
    self._register_with_platform()
    
    # Main thread runs ACP server (blocks)
    self.server.run(port=self.port)
```

### Redis Usage
**Storage Responsibilities:**
- **Agent Registration Metadata:** Name, type, capabilities, ACP URL, auth token
- **Message Queuing:** Queue messages between platform and agents
- **Session State:** Maintain stateful agent session data
- **Agent Status:** Track agent health and availability

### Configuration
**Platform URL Configuration:**
- **Primary:** Environment variable `PLATFORM_BASE_URL`
- **Fallback:** SDK constructor parameter `platform_url` 
- **Default:** `http://localhost:8000` (if neither provided)

```python
import os
platform_url = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000")
```

**Error Handling:**
- **Registration failures:** Raise exception and stop (no automatic retry)
- **Platform verification failures:** Raise exception and stop
- **Connection errors:** Raise exception and stop
- **Philosophy:** Fail fast with clear error messages for debugging

### Dependencies
**Automatic Dependency Management:**
- SDK automatically installs required dependencies via `uv add`
- Required packages: `acp-sdk`, `portpicker`, `requests`
- No manual dependency management required by users

```python
# SDK handles dependency installation automatically
required_packages = ["acp-sdk", "portpicker", "requests"]
```

### Framework Integration
**Manual Adaptation Approach:**
- SDK provides generic interface only
- No framework-specific helper classes (DSPy, CrewAI, etc.)
- Users manually adapt their framework code to SDK interface
- Keeps SDK lightweight and framework-agnostic

## Complete Implementation Summary

### Final Architecture Overview
**System Components:**
1. **Platform (ACP Gateway):** 
   - Implements standard ACP endpoints (`/agents`, `/runs`)
   - Custom registration endpoint (`/platform/agents/register`)
   - Routes messages to registered agents via ACP client calls
   - Stores all data in Redis (agent metadata, queues, sessions)

2. **Agent SDK (ACP Server Wrapper):**
   - Wraps `acp_sdk.server.Server` with auto-configuration
   - Handles port allocation, auth token generation, platform registration
   - Provides simple interface: agent name, type, capabilities, process function
   - Auto-registers on startup with fail-fast error handling

3. **Communication Flow:**
   - External clients → Platform (ACP requests)
   - Platform → Agents (ACP client calls)
   - Agents → Platform (ACP responses)
   - Platform → External clients (ACP responses)

### Key Technical Decisions
- **Port Allocation:** `portpicker` package for automatic port finding
- **Authentication:** Bearer tokens generated with `secrets.token_urlsafe(32)`
- **Configuration:** Environment variable `PLATFORM_BASE_URL` preferred
- **Error Handling:** Fail-fast approach, no automatic retries
- **Dependencies:** Auto-install `acp-sdk`, `portpicker`, `requests`
- **Threading:** ACP server in main thread, registration in background
- **Framework Support:** Generic interface, manual user adaptation

### Essential File Structure
```
mesh_sdk/
├── platform/src/           # Platform core (ACP gateway)
├── agent/src/              # Agent SDK (ACP server wrapper)
├── docs/
│   └── spec.md            # This complete specification
├── CLAUDE.md              # Project instructions for AI
└── pyproject.toml         # uv package configuration
```

### Implementation Priorities
1. **Agent SDK Core:** Basic AgentSDK class with ACP server wrapping
2. **Platform Registration:** Custom endpoint for agent registration  
3. **Platform ACP Gateway:** Standard ACP endpoints implementation
4. **Redis Integration:** Agent metadata and message queue storage
5. **Error Handling:** Comprehensive exception types and fail-fast logic
6. **Testing:** Unit tests for both agent SDK and platform components

## Instructions for Generative AI

### How to Use This Specification
1. **Read the entire document** to understand the complete project scope
2. **Focus on the Technical Requirements** section for implementation details
3. **Follow the Implementation Guidelines** for coding standards and practices
4. **Reference the Dependencies** section to understand external integrations
5. **Consider the Non-Functional Requirements** for performance, security, and reliability
6. **Always create the TODO list** for each plan to implement
7. **Implement the test first** for each endpoint
8. **Continous Integration** for each component

### Key Decision Points
- **Architecture decisions** should align with the specified system architecture
- **Technology choices** should match the defined technology stack
- **API design** should follow the specified API specifications
- **Code structure** should adhere to the defined file structure
- **Testing approach** should meet the specified testing requirements

### Validation Checklist
Before implementing any feature, ensure:
- [ ] Requirements are clearly understood
- [ ] Questions need user clarify
- [ ] Technical constraints are considered
- [ ] Dependencies are identified
- [ ] Testing strategy is defined
- [ ] Documentation requirements are met
