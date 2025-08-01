# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Project: LLM Agent SDK (Agent Mesh SDK)

## Project Overview
This SDK enables seamless integration between agents and platforms using the Agent Communication Protocol (ACP). The platform manages agent orchestration, registration, and workflow control, while agents connect to receive and process messages from the platform.

## Tech Stack
- **Language:** Python 3.12+
- **Package Management:** uv (https://docs.astral.sh/uv/)
- **Database:** Redis
- **Protocol:** ACP (Agent Communication Protocol) - REST-based HTTP API
- **Linting:** Ruff (https://docs.astral.sh/ruff/)

## Architecture Overview

### Core Components
1. **Platform Core** (`platform/src/`) - Manages agent registration, message routing, and workflow orchestration
2. **Agent SDK** (`agent/src/`) - Provides interface for agents to connect and communicate with platform
3. **ACP Protocol** - Standard communication protocol handling authentication, message routing, and error handling

### Key Architecture Patterns
- **Framework Agnostic:** Supports DSPy, CrewAI, Google ADK, BeeAI, and custom frameworks
- **ACP Protocol Abstraction:** SDK handles all ACP communication details
- **Callback-Driven:** Event-driven architecture with configurable callbacks
- **Multi-modal Support:** Handles text, images, audio, video via MimeTypes
- **Stateful/Stateless:** Supports both session-based and request-response patterns

## Development Commands

Since this is an early-stage project, standard uv commands should be used:

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check .

# Format code  
uv run ruff format .

# Run tests (when implemented)
uv run pytest

# Development server (when implemented)
uv run python -m platform
uv run python -m agent
```

## Core Data Models

### Agent Registration
```python
{
    "agent_name": "string",           # Required: Unique identifier
    "agent_type": "string",           # Required: dspy, crewai, google_adk, beeai, custom
    "capabilities": ["array"],        # Required: List of agent capabilities
    "version": "string",              # Optional: Agent version
    "description": "string",          # Optional: Agent description
    "tags": ["array"],               # Optional: Categorization tags
    "contact": "string"              # Optional: Maintainer contact
}
```

### Message Structure (ACP)
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

## Integration Patterns

### Basic Agent Implementation
```python
from mesh_sdk import AgentSDK

class MyAgent:
    def __init__(self):
        self.sdk = AgentSDK(
            agent_name="my_agent",
            agent_type="custom", 
            capabilities=["text_generation"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_error": self.on_error
            }
        )
    
    def process_message(self, message):
        # Core agent logic here
        result = self.my_processing_logic(message.content)
        return {"content": result, "metadata": {}}
    
    def start(self):
        self.sdk.start()
```

### Required Registration Fields
- `agent_name`: Unique identifier (3-50 alphanumeric chars + underscores)
- `agent_type`: Framework type (dspy, crewai, google_adk, beeai, custom)  
- `capabilities`: Non-empty array of capability strings
- `process_function`: Callable function to handle messages

### Available Callbacks
- `on_register`: Called after successful platform registration
- `on_message`: Called when message received (before processing)
- `on_error`: Called when error occurs during processing
- `on_shutdown`: Called during agent shutdown
- `on_health_check`: Called during platform health checks
- `on_session_start/end`: Called for stateful session management

## Error Handling

### Registration Exceptions
- `AgentNameConflictError`: Agent name already exists
- `AgentCapabilityError`: Invalid/unsupported capabilities  
- `AgentManifestError`: Malformed registration manifest
- `MissingRequiredFieldsError`: Required fields missing
- `PlatformConnectionError`: Unable to connect to platform
- `PlatformAuthenticationError`: Authentication failed

### ACP Error Codes
- `ACP_001`: Agent not found
- `ACP_002`: Invalid message format
- `ACP_003`: Agent busy/unavailable
- `ACP_004`: Authentication failed
- `ACP_005`: Rate limit exceeded

## Authentication

Authentication is handled by the ACP protocol. For development:

```python
# No authentication (development)
sdk = AgentSDK(..., acp_base_url="http://localhost:8000")

# With bearer token
sdk = AgentSDK(..., acp_base_url="https://platform.example.com", 
               auth_token="your-token")

# From environment
sdk = AgentSDK(..., auth_token=os.getenv("ACP_AUTH_TOKEN"))
```

## Code Style Guidelines

- Follow Ruff linting rules
- Use `str.join()` instead of `+` for string concatenation in loops
- Implement type hints for all public APIs
- Use async/await for I/O operations
- Handle errors with specific exception types
- Document all public methods and classes

## Testing Strategy

When implementing tests:
- Write tests first for each endpoint/component
- Test both success and error scenarios  
- Mock external dependencies (Redis, HTTP calls)
- Use pytest for test framework
- Test callback invocation and error handling
- Validate ACP protocol compliance

## Project Structure
```
mesh_sdk/
├── platform/src/           # Platform core implementation
├── agent/src/              # Agent SDK implementation  
├── docs/                   # Project documentation
│   └── spec.md            # Detailed technical specification
├── tmp/                   # Generated development files
└── CLAUDE.md              # This file
```

## Development Guidelines

1. **Always create TODO lists** for implementation planning
2. **Read docs/spec.md** for comprehensive technical details
3. **Implement tests first** for each component
4. **Follow ACP protocol** specifications for communication
5. **Support multiple frameworks** (DSPy, CrewAI, etc.)
6. **Handle errors gracefully** with proper exception types
7. **Use callbacks** for event-driven architecture
8. **Maintain backward compatibility** within major versions
