"""
Mesh SDK - Agent Communication Protocol Integration

This SDK enables seamless integration between agents and platforms using the 
Agent Communication Protocol (ACP). The platform manages agent orchestration, 
registration, and workflow control, while agents connect to receive and process 
messages from the platform.

Usage:
    # Import submodules
    from mesh_sdk import mesh_agent, mesh_platform
    
    # Or import directly
    import mesh_sdk.mesh_agent
    import mesh_sdk.mesh_platform
    
    # Access main classes
    from mesh_sdk.mesh_agent import AgentSDK
    from mesh_sdk.mesh_platform import PlatformCore, RedisClient
"""

# Import submodules to make them available
from . import mesh_agent
from . import mesh_platform

# Import main classes for convenience
from .mesh_agent import AgentSDK
from .mesh_platform import PlatformCore, RedisClient

# Import exceptions for comprehensive error handling
from .mesh_agent.src.exceptions import (
    AgentRegistrationError,
    AgentNameConflictError,
    AgentCapabilityError,
    AgentManifestError,
    MissingRequiredFieldsError,
    PlatformConnectionError,
    PlatformAuthenticationError,
    PlatformUnavailableError,
)

# Version and metadata
__version__ = "0.1.0"
__author__ = "Mesh SDK Team"
__email__ = "team@mesh-sdk.dev"

# All exports
__all__ = [
    # Submodules
    "mesh_agent",
    "mesh_platform",
    
    # Core classes
    "AgentSDK",
    "PlatformCore", 
    "RedisClient",
    
    # Exceptions
    "AgentRegistrationError",
    "AgentNameConflictError", 
    "AgentCapabilityError",
    "AgentManifestError",
    "MissingRequiredFieldsError",
    "PlatformConnectionError",
    "PlatformAuthenticationError",
    "PlatformUnavailableError",
    
    # Metadata
    "__version__",
]