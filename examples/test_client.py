"""Test client to demonstrate platform API usage."""

import time

import requests


def main():
    """Test the platform API endpoints."""
    platform_url = "http://localhost:8000"

    print("🧪 Testing Agent Mesh Platform API")
    print(f"   Platform URL: {platform_url}")
    print("=" * 50)

    # Test 1: List agents (should be empty initially)
    print("\n1. Testing GET /agents (list all agents)")
    try:
        response = requests.get(f"{platform_url}/agents")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            agents = response.json()
            print(f"   Agents found: {len(agents.get('agents', []))}")
            for agent in agents.get("agents", []):
                print(f"     - {agent['name']} ({agent.get('agent_type', 'unknown')})")
        else:
            print(f"   Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Connection failed - is the platform running?")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Try to get a specific agent (should fail)
    print("\n2. Testing GET /agents/nonexistent (get specific agent)")
    try:
        response = requests.get(f"{platform_url}/agents/nonexistent")
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ Correctly returned 404 for non-existent agent")
        else:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Try to create a run without agents
    print("\n3. Testing POST /runs (create run without agents)")
    try:
        run_data = {
            "agent": "nonexistent_agent",
            "input": [{"content": "Hello, agent!"}],
        }
        response = requests.post(f"{platform_url}/runs", json=run_data)
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ Correctly returned 404 for non-existent agent")
        else:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Wait for agent to potentially register
    print("\n4. Waiting for agents to register...")
    print("   (Start an agent in another terminal to see it appear)")

    for i in range(30):  # Wait up to 30 seconds
        time.sleep(1)
        try:
            response = requests.get(f"{platform_url}/agents")
            if response.status_code == 200:
                agents = response.json().get("agents", [])
                if agents:
                    print(f"\n   ✅ Found {len(agents)} agent(s):")
                    for agent in agents:
                        print(
                            f"     - {agent['name']} ({agent.get('version', '1.0.0')})"
                        )
                        print(f"       Capabilities: {agent.get('capabilities', [])}")
                        print(
                            f"       Description: {agent.get('description', 'No description')}"
                        )

                    # Test with the first agent
                    first_agent = agents[0]
                    agent_name = first_agent["name"]

                    print(f"\n5. Testing agent run with '{agent_name}'")
                    run_data = {
                        "agent": agent_name,
                        "input": [{"content": "Hello, this is a test message!"}],
                    }

                    try:
                        response = requests.post(f"{platform_url}/runs", json=run_data)
                        print(f"   Status: {response.status_code}")
                        if response.status_code == 200:
                            result = response.json()
                            print("   ✅ Run created successfully!")
                            print(f"   Run ID: {result.get('run_id')}")
                            print(f"   Status: {result.get('status')}")
                            print(f"   Output: {result.get('output')}")
                        else:
                            print(f"   ❌ Run failed: {response.json()}")
                    except Exception as e:
                        print(f"   ❌ Error creating run: {e}")

                    break
        except Exception:
            pass
    else:
        print("   ⏰ No agents registered within 30 seconds")

    print("\n" + "=" * 50)
    print("🎉 API testing complete!")
    print("\nTo test with an agent:")
    print("1. Keep this platform running")
    print("2. In another terminal, run: python examples/simple_agent.py")
    print("3. The agent should register and be available for runs")


if __name__ == "__main__":
    main()
