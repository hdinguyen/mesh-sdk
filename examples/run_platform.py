"""Script to run the platform for demo purposes."""

from mesh_platform import PlatformCore


def main():
    """Run the platform server."""
    print("🚀 Starting Agent Mesh Platform...")
    print("   Platform URL: http://localhost:8000")
    print("   Redis: localhost:6380")
    print("   Endpoints:")
    print("     - POST /platform/agents/register (Agent registration)")
    print("     - GET /agents (List agents - ACP standard)")
    print("     - GET /agents/{name} (Get agent manifest - ACP standard)")
    print("     - POST /runs (Create agent run - ACP standard)")
    print("     - GET /runs/{run_id} (Get run status - ACP standard)")
    print()
    print("Press Ctrl+C to stop the platform")
    print("=" * 50)

    try:
        # Create platform with Redis on port 6380 (Docker)
        platform = PlatformCore(redis_host="localhost", redis_port=6380)

        # Run platform on default port 8000
        platform.run(host="0.0.0.0", port=8000)

    except KeyboardInterrupt:
        print("\n🛑 Platform shutting down...")
    except Exception as e:
        print(f"❌ Platform error: {e}")
        raise


if __name__ == "__main__":
    main()
