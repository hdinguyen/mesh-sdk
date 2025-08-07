"""
Mesh SDK - Convenience module for easy importing.

Usage:
    # For agents
    from mesh_sdk import AgentSDK
    
    # For platform
    from mesh_sdk import PlatformCore
    
    # For Redis operations
    from mesh_sdk import RedisClient
"""

# Import the main classes from their respective packages
from mesh_agent import AgentSDK
from mesh_platform import PlatformCore, RedisClient

# Import exceptions for comprehensive error handling
from mesh_agent.src.exceptions import (
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