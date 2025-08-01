# Agent Mesh SDK

Agent Mesh SDK enables seamless integration between agents and platforms using the Agent Communication Protocol (ACP). The platform manages agent orchestration, registration, and workflow control, while agents connect to receive and process messages from the platform.

## Features

- **Framework Agnostic**: Supports DSPy, CrewAI, Google ADK, BeeAI, and custom frameworks
- **ACP Protocol Abstraction**: SDK handles all ACP communication details
- **Callback-Driven**: Event-driven architecture with configurable callbacks
- **Multi-modal Support**: Handles text, images, audio, video via MimeTypes
- **Stateful/Stateless**: Supports both session-based and request-response patterns
- **Auto-Registration**: Agents automatically register with platform on startup
- **Fail-Fast Error Handling**: Clear error messages for debugging

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (for Redis)
- uv package manager

### 1. Install Dependencies

```bash
# Install the package dependencies
uv sync

# Start Redis using Docker
docker-compose up -d redis
```

### 2. Start the Platform

```bash
# Run the platform server
python examples/run_platform.py
```

The platform will start on `http://localhost:8000` with the following endpoints:

- `POST /platform/agents/register` - Agent registration
- `GET /agents` - List all agents (ACP standard)
- `GET /agents/{name}` - Get agent manifest (ACP standard)  
- `POST /runs` - Create agent run (ACP standard)
- `GET /runs/{run_id}` - Get run status (ACP standard)

### 3. Start an Agent

In a separate terminal:

```bash
# Run the example echo agent
python examples/simple_agent.py
```

### 4. Test the System

In another terminal:

```bash
# Run the test client to verify everything works
python examples/test_client.py
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   External      │    │    Platform     │    │     Agents      │
│   Clients       │    │   (ACP Gateway) │    │  (ACP Servers)  │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│                 │    │                 │    │                 │
│  - Web Apps     │◄──►│  - Registration │◄──►│  - Agent SDK    │
│  - APIs         │    │  - Routing      │    │  - Custom Logic │
│  - CLI Tools    │    │  - ACP Gateway  │    │  - Frameworks   │
│  - Other        │    │  - Redis Store  │    │  - ACP Server   │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        └───────ACP Protocol────┴───────ACP Protocol────┘
```

### Key Components

1. **Platform Core** (`platform/src/`) - Acts as ACP gateway, manages agent registration, message routing, and workflow orchestration
2. **Agent SDK** (`agent/src/`) - Provides interface for agents to connect and communicate with platform via ACP protocol
3. **Redis Storage** - Stores agent metadata, message queues, and session state

## Agent SDK Usage

### Basic Agent Implementation

```python
from agent.src import AgentSDK

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
    
    def process_message(self, messages):
        # Your agent logic here
        content = messages[0].parts[0].content
        result = f"Processed: {content}"
        return {"content": result}
    
    def start(self):
        self.sdk.start()  # Starts ACP server and auto-registers

agent = MyAgent()
agent.start()
```

### Framework Integration Examples

#### DSPy Integration

```python
from agent.src import AgentSDK

class MyDSPyAgent:
    def __init__(self):
        # Initialize your DSPy components
        self.dspy_agent = YourDSPyImplementation()
        
        self.sdk = AgentSDK(
            agent_name="my_dspy_agent",
            agent_type="dspy",
            capabilities=["text_generation", "reasoning"],
            process_function=self.process_message
        )
    
    def process_message(self, messages):
        content = messages[0].parts[0].content
        result = self.dspy_agent(content)
        return {"content": result}
    
    def start(self):
        self.sdk.start()
```

#### CrewAI Integration

```python
from agent.src import AgentSDK

class MyCrewAIAgent:
    def __init__(self):
        self.crew_agent = YourCrewAIImplementation()
        
        self.sdk = AgentSDK(
            agent_name="my_crewai_agent",
            agent_type="crewai",
            capabilities=["task_execution", "team_coordination"],
            process_function=self.process_message
        )
    
    def process_message(self, messages):
        task = messages[0].parts[0].content
        result = self.crew_agent.execute(task)
        return {"content": result}
    
    def start(self):
        self.sdk.start()
```

### Configuration

#### Platform URL Priority

1. **Environment Variable**: `PLATFORM_BASE_URL` (highest priority)
2. **Constructor Parameter**: `platform_url` parameter
3. **Default Value**: `http://localhost:8000` (fallback)

```python
# Using environment variable
export PLATFORM_BASE_URL=https://my-platform.com

# Using constructor parameter
sdk = AgentSDK(
    ...,
    platform_url="https://my-platform.com"
)
```

#### Available Callbacks

```python
callbacks = {
    "on_register": callback_function,      # Called after successful registration
    "on_message": callback_function,       # Called when message received
    "on_error": callback_function,         # Called when error occurs
    "on_shutdown": callback_function,      # Called during shutdown
}
```

## Error Handling

### Registration Exceptions

- `AgentNameConflictError` - Agent name already exists
- `AgentCapabilityError` - Invalid/unsupported capabilities
- `AgentManifestError` - Malformed registration manifest
- `MissingRequiredFieldsError` - Required fields missing
- `PlatformConnectionError` - Unable to connect to platform
- `PlatformAuthenticationError` - Authentication failed

### Example Error Handling

```python
from agent.src import AgentSDK
from agent.src.exceptions import AgentRegistrationError

try:
    agent = MyAgent()
    agent.start()
except AgentRegistrationError as e:
    print(f"Registration failed: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Details: {e.details}")
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=agent --cov=platform

# Run specific test file
uv run pytest tests/test_agent_sdk.py
```

### Code Quality

```bash
# Run linting
uv run ruff check .

# Format code
uv run ruff format .

# Type checking (if using mypy)
uv run mypy agent platform
```

### Project Structure

```
mesh_sdk/
├── agent/src/                 # Agent SDK implementation
│   ├── __init__.py
│   ├── sdk.py                # Main AgentSDK class
│   └── exceptions.py         # Custom exceptions
├── platform/src/             # Platform core implementation
│   ├── __init__.py
│   ├── platform.py          # Platform server
│   └── redis_client.py      # Redis data layer
├── examples/                 # Example implementations
│   ├── simple_agent.py      # Basic echo agent
│   ├── run_platform.py      # Platform server
│   └── test_client.py       # API test client
├── tests/                    # Test suite
│   ├── test_agent_sdk.py    # Agent SDK tests
│   └── test_platform.py     # Platform tests
├── docs/                     # Documentation
│   └── spec.md              # Technical specification
├── docker-compose.yml        # Redis container setup
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## API Reference

### Agent Registration

```http
POST /platform/agents/register
Content-Type: application/json

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

### List Agents (ACP Standard)

```http
GET /agents
```

### Create Agent Run (ACP Standard)

```http
POST /runs
Content-Type: application/json

{
    "agent": "my_agent",
    "input": [{"content": "Hello, agent!"}]
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite and linting
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- Documentation: See `docs/spec.md` for detailed technical specification
- Issues: Please report issues on the project repository
- Examples: Check the `examples/` directory for usage examples