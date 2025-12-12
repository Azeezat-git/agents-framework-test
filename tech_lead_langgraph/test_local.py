#!/usr/bin/env python3
"""
Local test script for LangGraph Tech Lead agent.
Tests the graph execution with MCP tools.
"""
import os
import sys
import logging
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    """Test the LangGraph agent locally"""
    print("=" * 60)
    print("Testing Tech Lead LangGraph Agent Locally")
    print("=" * 60)
    
    # Check environment variables
    print("\nEnvironment Variables:")
    print(f"JIRA_MCP_URL: {os.getenv('JIRA_MCP_URL', 'not set')}")
    print(f"BITBUCKET_MCP_URL: {os.getenv('BITBUCKET_MCP_URL', 'not set')}")
    print(f"GATEWAY_BASE_URL: {os.getenv('GATEWAY_BASE_URL', 'not set')}")
    print(f"GATEWAY_API_KEY: {'***SET***' if os.getenv('GATEWAY_API_KEY') else 'not set'}")
    print(f"LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2', 'not set (set to true to enable LangSmith tracing)')}")
    print(f"LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT', 'not set (optional)')}")
    print(f"OTEL_EXPORTER_OTLP_ENDPOINT: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'not set (optional)')}")
    
    # Import and run
    from tech_lead_langgraph.main import run
    
    inputs = {"jira_issue_key": "TECBAC-209"}
    
    print(f"\nRunning graph with input: {inputs}")
    print("=" * 60)
    
    try:
        result = run(inputs)
        
        print("\n" + "=" * 60)
        print("Execution Complete")
        print("=" * 60)
        
        print(f"\nFinal Output:")
        print("-" * 60)
        if result.get("final_output"):
            # Print full output, no truncation
            print(result["final_output"])
        else:
            print("No final output generated")
        
        print(f"\nState Summary:")
        print(f"- Jira Issue Key: {result.get('jira_issue_key')}")
        print(f"- Workspace: {result.get('workspace')}")
        print(f"- Repo Slug: {result.get('repo_slug')}")
        print(f"- Jira Issue Fetched: {'Yes' if result.get('jira_issue') else 'No'}")
        print(f"- Repo List: {'Yes' if result.get('repo_list') else 'No'}")
        print(f"- Repo Files: {'Yes' if result.get('repo_files') else 'No'}")
        
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

