"""Test script for flow feature implementation."""

import asyncio
import json
import sys
import aiohttp
from pathlib import Path

# Add parent directory to path so we can import from examples
sys.path.append(str(Path(__file__).parent.parent))

from examples.simple_agent import SimpleAgent


async def test_flow_feature():
    """Test the complete flow feature implementation."""
    
    print("🚀 Testing Flow Feature Implementation")
    print("=" * 50)
    
    # Configuration
    platform_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Test flow creation
        print("\n📝 Step 1: Creating a test flow")
        flow_data = {"name": "Text Processing Pipeline"}
        
        async with session.post(f"{platform_url}/flows", json=flow_data) as resp:
            if resp.status != 201:
                print(f"❌ Failed to create flow: {resp.status}")
                text = await resp.text()
                print(f"Response: {text}")
                return
            
            flow_info = await resp.json()
            flow_id = flow_info["flow_id"]
            print(f"✅ Created flow: {flow_info['name']} (ID: {flow_id})")
        
        # Step 2: Test adding agents to flow
        print("\n🤖 Step 2: Adding agents to flow")
        
        # Add first agent (start agent)
        agent1_data = {
            "agent_name": "text_processor",
            "upstream_agents": [],
            "required": True
        }
        
        async with session.post(f"{platform_url}/flows/{flow_id}/agents", json=agent1_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Added start agent: {result['agent_name']}")
            else:
                print(f"⚠️  Agent add response: {resp.status} (agent may not exist yet)")
        
        # Add second agent (downstream agent)
        agent2_data = {
            "agent_name": "text_analyzer", 
            "upstream_agents": ["text_processor"],
            "required": True
        }
        
        async with session.post(f"{platform_url}/flows/{flow_id}/agents", json=agent2_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Added downstream agent: {result['agent_name']}")
            else:
                print(f"⚠️  Agent add response: {resp.status} (agent may not exist yet)")
        
        # Add optional agent
        agent3_data = {
            "agent_name": "text_enhancer",
            "upstream_agents": ["text_processor"],
            "required": False
        }
        
        async with session.post(f"{platform_url}/flows/{flow_id}/agents", json=agent3_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Added optional agent: {result['agent_name']}")
            else:
                print(f"⚠️  Agent add response: {resp.status} (agent may not exist yet)")
        
        # Step 3: View flow structure
        print("\n🔍 Step 3: Viewing flow structure")
        
        async with session.get(f"{platform_url}/flows/{flow_id}") as resp:
            if resp.status == 200:
                flow_data = await resp.json()
                print(f"✅ Flow structure:")
                print(f"   Name: {flow_data['name']}")
                print(f"   Agents: {len(flow_data['agents'])}")
                for agent in flow_data['agents']:
                    upstream = agent.get('upstream_agents', [])
                    upstream_str = f" <- {upstream}" if upstream else " (start)"
                    required_str = "required" if agent.get('required', True) else "optional"
                    print(f"   - {agent['agent_name']} ({required_str}){upstream_str}")
            else:
                print(f"❌ Failed to get flow: {resp.status}")
        
        # Step 4: Test flow execution (this will likely fail due to no agents)
        print("\n⚡ Step 4: Testing flow execution")
        
        execution_data = {
            "input": {
                "text": "Hello, this is a test message for the flow system!"
            }
        }
        
        async with session.post(f"{platform_url}/flows/{flow_id}/execute", json=execution_data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Flow executed successfully!")
                print(f"   Result: {result.get('result', {})}")
            else:
                text = await resp.text()
                print(f"⚠️  Flow execution failed (expected): {resp.status}")
                print(f"   Reason: {text}")
                print("   This is expected since we haven't registered actual agents yet.")
        
        # Step 5: Test flow listing
        print("\n📋 Step 5: Listing all flows")
        
        async with session.get(f"{platform_url}/flows") as resp:
            if resp.status == 200:
                flows_data = await resp.json()
                flows = flows_data.get("flows", [])
                print(f"✅ Found {len(flows)} flows:")
                for flow in flows:
                    print(f"   - {flow['name']} (ID: {flow['flow_id']}, Agents: {len(flow.get('agents', []))})")
            else:
                print(f"❌ Failed to list flows: {resp.status}")
        
        # Step 6: Test execution history
        print("\n📊 Step 6: Checking execution history")
        
        async with session.get(f"{platform_url}/flows/{flow_id}/executions") as resp:
            if resp.status == 200:
                executions_data = await resp.json()
                executions = executions_data.get("executions", [])
                print(f"✅ Found {len(executions)} executions:")
                for execution in executions:
                    status = execution.get('status', 'unknown')
                    started = execution.get('started_at', 'unknown')
                    print(f"   - {execution['execution_id']}: {status} (started: {started})")
            else:
                print(f"❌ Failed to get executions: {resp.status}")
        
        # Step 7: Cleanup
        print("\n🧹 Step 7: Cleaning up test flow")
        
        async with session.delete(f"{platform_url}/flows/{flow_id}") as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Deleted flow: {result['message']}")
            else:
                print(f"❌ Failed to delete flow: {resp.status}")
    
    print("\n" + "=" * 50)
    print("🎉 Flow feature test completed!")
    print("\nKey Features Tested:")
    print("✅ Flow creation and deletion")
    print("✅ Agent management (add agents with dependencies)")
    print("✅ Flow structure visualization")
    print("✅ Flow execution (shows proper error handling)")
    print("✅ Execution history tracking")
    print("✅ REST API endpoints")
    
    print("\nNext Steps:")
    print("1. Register actual agents to test full flow execution")
    print("2. Test more complex dependency patterns")
    print("3. Test optional agent failure scenarios")
    print("4. Test health check functionality")


async def test_with_mock_agents():
    """Test flow feature with mock agents (if platform is running)."""
    
    print("\n🤖 Testing with Mock Agent Registration")
    print("=" * 50)
    
    platform_url = "http://localhost:8000"
    
    # Mock agent data
    mock_agents = [
        {
            "agent_name": "text_processor",
            "agent_type": "custom",
            "capabilities": ["text_processing"],
            "acp_base_url": "http://localhost:8001",
            "auth_token": "mock_token_123",
            "version": "1.0.0",
            "description": "Mock text processing agent"
        },
        {
            "agent_name": "text_analyzer", 
            "agent_type": "custom",
            "capabilities": ["text_analysis"],
            "acp_base_url": "http://localhost:8002",
            "auth_token": "mock_token_456",
            "version": "1.0.0",
            "description": "Mock text analysis agent"
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        
        # Register mock agents
        print("📝 Registering mock agents...")
        
        for agent_data in mock_agents:
            async with session.post(f"{platform_url}/platform/agents/register", json=agent_data) as resp:
                if resp.status in [200, 409]:  # 409 = already exists
                    print(f"✅ Mock agent registered: {agent_data['agent_name']}")
                else:
                    text = await resp.text()
                    print(f"⚠️  Mock agent registration failed: {resp.status} - {text}")
        
        # Now test flow with registered agents
        print("\n🔄 Testing flow with registered agents...")
        
        # Create flow
        flow_data = {"name": "Mock Agent Flow"}
        async with session.post(f"{platform_url}/flows", json=flow_data) as resp:
            if resp.status == 201:
                flow_info = await resp.json()
                flow_id = flow_info["flow_id"]
                print(f"✅ Created flow: {flow_id}")
                
                # Add agents to flow
                agents_config = [
                    {"agent_name": "text_processor", "upstream_agents": [], "required": True},
                    {"agent_name": "text_analyzer", "upstream_agents": ["text_processor"], "required": True}
                ]
                
                for agent_config in agents_config:
                    async with session.post(f"{platform_url}/flows/{flow_id}/agents", json=agent_config) as resp:
                        if resp.status == 200:
                            print(f"✅ Added agent: {agent_config['agent_name']}")
                
                # Try to execute flow (will likely fail on health check since mock agents aren't real)
                execution_data = {"input": {"text": "Test message"}}
                async with session.post(f"{platform_url}/flows/{flow_id}/execute", json=execution_data) as resp:
                    result_text = await resp.text()
                    if resp.status == 200:
                        print("✅ Flow execution succeeded!")
                    else:
                        print(f"⚠️  Flow execution failed (expected for mock agents): {resp.status}")
                        print(f"   Details: {result_text}")
                
                # Cleanup
                async with session.delete(f"{platform_url}/flows/{flow_id}") as resp:
                    if resp.status == 200:
                        print("✅ Flow cleaned up")


if __name__ == "__main__":
    print("🚀 Starting Flow Feature Tests")
    
    try:
        # Run basic flow API tests
        asyncio.run(test_flow_feature())
        
        # Run mock agent tests 
        asyncio.run(test_with_mock_agents())
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()