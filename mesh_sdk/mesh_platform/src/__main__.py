"""Main entry point for running the platform."""

import os

from .platform import PlatformCore

if __name__ == "__main__":
    # Get Redis configuration from environment
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6380"))

    # Get platform configuration
    platform_host = os.getenv("PLATFORM_HOST", "0.0.0.0")
    platform_port = int(os.getenv("PLATFORM_PORT", "8000"))

    # Create and run platform
    platform = PlatformCore(redis_host=redis_host, redis_port=redis_port)
    platform.run(host=platform_host, port=platform_port)
