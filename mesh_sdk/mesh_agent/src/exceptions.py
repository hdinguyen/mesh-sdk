"""Agent registration and communication exceptions."""


class AgentRegistrationError(Exception):
    """Base exception for agent registration failures."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class AgentNameConflictError(AgentRegistrationError):
    """Raised when agent name already exists in platform."""

    def __init__(self, agent_name: str, existing_agent_info: dict = None):
        message = f"Agent name '{agent_name}' is already registered"
        super().__init__(message, "REG_001", {"existing_agent": existing_agent_info})


class AgentCapabilityError(AgentRegistrationError):
    """Raised when agent capabilities are invalid or unsupported."""

    def __init__(self, invalid_capabilities: list, supported_capabilities: list = None):
        message = f"Invalid capabilities: {invalid_capabilities}"
        super().__init__(message, "REG_002", {"supported": supported_capabilities})


class AgentManifestError(AgentRegistrationError):
    """Raised when agent manifest is malformed or incomplete."""

    def __init__(self, missing_fields: list, manifest_data: dict = None):
        message = f"Invalid manifest - missing fields: {missing_fields}"
        super().__init__(message, "REG_003", {"manifest": manifest_data})


class MissingRequiredFieldsError(AgentRegistrationError):
    """Raised when required fields are missing from agent registration."""

    def __init__(
        self,
        missing_fields: list,
        required_fields: list = None,
        provided_fields: list = None,
    ):
        message = f"Missing required fields: {missing_fields}"
        super().__init__(
            message,
            "REG_004",
            {
                "missing_fields": missing_fields,
                "required_fields": required_fields,
                "provided_fields": provided_fields,
            },
        )


class PlatformConnectionError(AgentRegistrationError):
    """Raised when unable to connect to platform."""

    def __init__(self, platform_url: str, connection_error: Exception = None):
        message = f"Unable to connect to platform at {platform_url}"
        super().__init__(
            message, "REG_005", {"connection_error": str(connection_error)}
        )


class PlatformAuthenticationError(AgentRegistrationError):
    """Raised when platform authentication fails."""

    def __init__(self, auth_method: str, auth_error: str = None):
        message = f"Platform authentication failed using {auth_method}"
        super().__init__(message, "REG_006", {"auth_error": auth_error})


class PlatformUnavailableError(AgentRegistrationError):
    """Raised when platform is temporarily unavailable."""

    def __init__(self, platform_url: str, retry_after: int = None):
        message = f"Platform at {platform_url} is temporarily unavailable"
        super().__init__(message, "REG_007", {"retry_after": retry_after})
