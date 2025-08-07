#!/usr/bin/env python3
"""
Example demonstrating flow import/export functionality.

This example shows how to:
1. Create a flow with agents
2. Export the flow to JSON
3. Import a flow from JSON
4. Handle validation and error cases
"""

import json
import requests
from typing import Dict, Any


def create_sample_flow(base_url: str = "http://localhost:8000") -> str:
    """Create a sample flow with agents."""
    print("Creating sample flow...")
    
    # Create flow
    flow_data = {
        "name": "Document Processing Workflow",
        "description": "A workflow that processes documents through extraction and analysis"
    }
    
    response = requests.post(f"{base_url}/flows", json=flow_data)
    response.raise_for_status()
    
    flow_id = response.json()["flow_id"]
    print(f"Created flow: {flow_id}")
    
    # Add agents to flow
    agents = [
        {
            "agent_name": "text_extractor",
            "upstream_agents": [],
            "required": True,
            "description": "Extracts text content from various document formats"
        },
        {
            "agent_name": "preprocessor",
            "upstream_agents": ["text_extractor"],
            "required": True,
            "description": "Cleans and preprocesses extracted text"
        },
        {
            "agent_name": "sentiment_analyzer",
            "upstream_agents": ["preprocessor"],
            "required": True,
            "description": "Analyzes sentiment of processed text"
        },
        {
            "agent_name": "summarizer",
            "upstream_agents": ["preprocessor"],
            "required": False,
            "description": "Creates summaries of processed text"
        }
    ]
    
    for agent in agents:
        print(f"Adding agent: {agent['agent_name']}")
        response = requests.post(f"{base_url}/flows/{flow_id}/agents", json=agent)
        response.raise_for_status()
    
    return flow_id


def export_flow(flow_id: str, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Export flow to JSON."""
    print(f"Exporting flow: {flow_id}")
    
    response = requests.get(f"{base_url}/flows/{flow_id}/export")
    response.raise_for_status()
    
    flow_export = response.json()
    
    # Pretty print the export
    print("Exported flow definition:")
    print(json.dumps(flow_export, indent=2))
    
    return flow_export


def import_flow(flow_export: Dict[str, Any], base_url: str = "http://localhost:8000") -> str:
    """Import flow from JSON."""
    print("Importing flow...")
    
    # Modify the name to avoid conflicts
    flow_export["name"] = flow_export["name"] + " (Imported)"
    
    import_request = {
        "flow_data": flow_export,
        "validate_agents": True,
        "overwrite_existing": False
    }
    
    response = requests.post(f"{base_url}/flows/import", json=import_request)
    response.raise_for_status()
    
    result = response.json()
    print(f"Imported flow: {result['flow_id']}")
    print(f"Agents added: {result['agents_added']}")
    
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")
    
    return result["flow_id"]


def test_import_with_name_conflict(flow_export: Dict[str, Any], base_url: str = "http://localhost:8000"):
    """Test importing flow with name conflict."""
    print("\nTesting name conflict handling...")
    
    import_request = {
        "flow_data": flow_export,
        "validate_agents": False,
        "overwrite_existing": False
    }
    
    response = requests.post(f"{base_url}/flows/import", json=import_request)
    
    if response.status_code == 409:
        print("✓ Name conflict correctly detected")
        print(f"  Error: {response.json()['detail']}")
    else:
        print("✗ Expected name conflict error")


def test_import_with_overwrite(flow_export: Dict[str, Any], base_url: str = "http://localhost:8000"):
    """Test importing flow with overwrite enabled."""
    print("\nTesting overwrite functionality...")
    
    import_request = {
        "flow_data": flow_export,
        "validate_agents": False,
        "overwrite_existing": True
    }
    
    response = requests.post(f"{base_url}/flows/import", json=import_request)
    response.raise_for_status()
    
    result = response.json()
    print(f"✓ Flow overwritten: {result['flow_id']}")


def list_flows(base_url: str = "http://localhost:8000"):
    """List all flows to see the results."""
    print("\nListing all flows:")
    
    response = requests.get(f"{base_url}/flows")
    response.raise_for_status()
    
    flows = response.json()["flows"]
    for flow in flows:
        print(f"  - {flow['name']} ({flow['flow_id']})")
        if flow.get("description"):
            print(f"    Description: {flow['description']}")
        print(f"    Agents: {len(flow.get('agents', []))}")


def main():
    """Main example function."""
    base_url = "http://localhost:8000"
    
    try:
        print("Flow Import/Export Example")
        print("=" * 50)
        
        # Step 1: Create a sample flow
        flow_id = create_sample_flow(base_url)
        
        # Step 2: Export the flow
        flow_export = export_flow(flow_id, base_url)
        
        # Step 3: Import the flow (with new name)
        imported_flow_id = import_flow(flow_export, base_url)
        
        # Step 4: Test error cases
        test_import_with_name_conflict(flow_export, base_url)
        test_import_with_overwrite(flow_export, base_url)
        
        # Step 5: List all flows
        list_flows(base_url)
        
        print("\n✓ Example completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to platform. Make sure the platform is running at http://localhost:8000")
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP error: {e}")
        if e.response:
            print(f"  Response: {e.response.text}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


if __name__ == "__main__":
    main()