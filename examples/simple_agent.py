"""Simple agent example using the Agent SDK."""

from mesh_agent import AgentSDK
from mesh_agent.src.exceptions import AgentRegistrationError


class SimpleEchoAgent:
    """A simple echo agent that repeats messages back."""

    def __init__(self):
        """Initialize the echo agent."""
        self.sdk = AgentSDK(
            agent_name="simple_echo_agent",
            agent_type="custom",
            capabilities=["echo", "text_processing"],
            process_function=self.process_message,
            callbacks={
                "on_register": self.on_register,
                "on_message": self.on_message_received,
                "on_error": self.on_error,
                "on_shutdown": self.on_shutdown,
            },
            description="A simple echo agent for testing",
            tags=["demo", "echo", "testing"],
            contact="demo@mesh-sdk.dev",
        )

    def process_message(self, messages):
        """Process incoming ACP messages.

        Args:
            messages: List of ACP Message objects

        Returns:
            Dict with response content
        """
        if not messages:
            return {"content": "No messages received"}

        # Get content from first message
        first_message = messages[0]
        if hasattr(first_message, "parts") and first_message.parts:
            content = first_message.parts[0].content
        else:
            content = str(first_message)

        # Echo the message back with a prefix
        response = f"Echo: {content}"

        print(f"Processed message: '{content}' -> '{response}'")

        return {"content": response}

    def on_register(self, registration_data):
        """Called when agent successfully registers with platform."""
        print("✅ Agent registered successfully!")
        print(f"   Registration data: {registration_data}")

    def on_message_received(self, messages):
        """Called when message is received (before processing)."""
        print(f"📨 Received {len(messages)} message(s)")
        for i, msg in enumerate(messages):
            if hasattr(msg, "parts") and msg.parts:
                content = msg.parts[0].content
            else:
                content = str(msg)
            print(
                f"   Message {i + 1}: {content[:100]}{'...' if len(content) > 100 else ''}"
            )

    def on_error(self, error):
        """Called when an error occurs."""
        print(f"❌ Error occurred: {error}")
        if hasattr(error, "error_code"):
            print(f"   Error code: {error.error_code}")
        if hasattr(error, "details"):
            print(f"   Error details: {error.details}")

    def on_shutdown(self, reason):
        """Called during agent shutdown."""
        print(f"🛑 Agent shutting down. Reason: {reason}")

    def start(self):
        """Start the agent."""
        try:
            print("🚀 Starting Simple Echo Agent...")
            print(f"   Agent Name: {self.sdk.agent_name}")
            print(f"   Agent Type: {self.sdk.agent_type}")
            print(f"   Capabilities: {self.sdk.capabilities}")
            print(f"   Platform URL: {self.sdk.platform_url}")
            print(f"   ACP Server: {self.sdk.acp_base_url}")
            print()

            self.sdk.start()

        except AgentRegistrationError as e:
            print(f"❌ Registration failed: {e}")
            if hasattr(e, "error_code"):
                print(f"   Error code: {e.error_code}")
            if hasattr(e, "details"):
                print(f"   Details: {e.details}")
        except KeyboardInterrupt:
            print("\n🛑 Shutting down agent...")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    agent = SimpleEchoAgent()
    agent.start()
