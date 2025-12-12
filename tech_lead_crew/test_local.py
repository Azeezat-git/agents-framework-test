"""
Local testing script for tech-lead-crew without KAgentApp.
This allows testing the crew directly before deploying as a BYO agent.

Run from the project root:
  cd /Users/abisolaazeezat_awoniyi/Documents/for-tech-crew/tech_lead_crew
  source venv313/bin/activate
  python test_local.py
"""
import os
import sys
import json

# Add src directory to Python path so we can import tech_lead_crew
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from tech_lead_crew.crew import TechLeadCrew

# OTEL Instrumentation (if environment variables are set)
# CrewAI should auto-instrument when CREWAI_TRACING_ENABLED=true,
# but we manually instrument as a fallback to ensure it works
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("CREWAI_TRACING_ENABLED", "").lower() == "true":
    try:
        from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
        CrewAIInstrumentor().instrument()
        print("✅ OTEL instrumentation enabled")
    except ImportError:
        print("⚠️  opentelemetry-instrumentation-crewai not found - OTEL instrumentation skipped")

# Set environment variables for local testing
# These should match your port-forwarded services

# MCP Servers (port-forward from EC2 SSM)
os.environ["JIRA_MCP_URL"] = os.getenv("JIRA_MCP_URL", "http://localhost:3001/mcp/")
os.environ["BITBUCKET_MCP_URL"] = os.getenv("BITBUCKET_MCP_URL", "http://localhost:3000/mcp")

# LLM Gateway (port-forward agentgateway or use cluster URL)
# For local testing, port-forward: kubectl port-forward -n core-gloogateway svc/agentgateway-enterprise 8080:8080
# Then use: http://localhost:8080/llm/bedrock/default
os.environ["GATEWAY_BASE_URL"] = os.getenv(
    "GATEWAY_BASE_URL",
    "http://localhost:8080/llm/bedrock/default"  # Default to localhost for local testing (requires port-forward)
)
os.environ["GATEWAY_MODEL"] = os.getenv("GATEWAY_MODEL", "bedrock-default")
# Get API key from environment or try to get from kubectl secret
gateway_api_key = os.getenv("GATEWAY_API_KEY", "")
if not gateway_api_key:
    # Try to get from kubectl if available
    import subprocess
    import base64
    try:
        result = subprocess.run(
            ["kubectl", "get", "secret", "secret-bedrock", "-n", "core-kagent", "-o", "jsonpath={.data.api-key}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0 and result.stdout and result.stdout.strip():
            decoded_key = base64.b64decode(result.stdout.strip()).decode('utf-8')
            if decoded_key and decoded_key != "dummy-key":  # Only use if it's a real key
                gateway_api_key = decoded_key
                print(f"✅ Retrieved API key from secret-bedrock")
            elif decoded_key == "dummy-key":
                print(f"⚠️  Secret contains 'dummy-key' - this may not work. You may need a real API key.")
                gateway_api_key = decoded_key  # Use it anyway for testing
    except FileNotFoundError:
        pass  # kubectl not found
    except Exception as e:
        pass  # Other errors, will show warning below

# IMPORTANT: agentgateway uses IRSA (IAM Roles for Service Accounts) for Bedrock authentication.
# The API key from secret-bedrock is just a placeholder - agentgateway authenticates via IAM role.
# However, LiteLLM requires a non-empty API key in the request header, even if the backend ignores it.
if not gateway_api_key or gateway_api_key == "dummy-key":
    # Use a placeholder that looks valid to LiteLLM but agentgateway will ignore (uses IRSA)
    gateway_api_key = "irsa-placeholder-key"
    print("ℹ️  Using IRSA placeholder key - agentgateway authenticates via IAM role, not API key")
    print("   (The secret contains 'dummy-key' which is just a placeholder)\n")
else:
    print(f"✅ Using API key from secret (first 10 chars: {gateway_api_key[:10]}...)\n")

# Set both environment variables
os.environ["GATEWAY_API_KEY"] = gateway_api_key
os.environ["OPENAI_API_KEY"] = gateway_api_key  # Also set for LiteLLM compatibility

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Tech Lead Crew Locally")
    print("=" * 60)
    print("\nEnvironment Variables:")
    print(f"  JIRA_MCP_URL: {os.getenv('JIRA_MCP_URL')}")
    print(f"  BITBUCKET_MCP_URL: {os.getenv('BITBUCKET_MCP_URL')}")
    print(f"  GATEWAY_BASE_URL: {os.getenv('GATEWAY_BASE_URL')}")
    print(f"  GATEWAY_MODEL: {os.getenv('GATEWAY_MODEL')}")
    api_key = os.getenv('GATEWAY_API_KEY', '')
    print(f"  GATEWAY_API_KEY: {'***SET***' if api_key else '❌ NOT SET - LLM calls will fail!'}")
    
    # Show tracing status
    tracing_enabled = os.getenv('CREWAI_TRACING_ENABLED', '').lower() == 'true'
    print(f"  CREWAI_TRACING_ENABLED: {tracing_enabled}")
    if tracing_enabled:
        otel_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
        if otel_endpoint:
            print(f"  OTEL_EXPORTER_OTLP_ENDPOINT: {otel_endpoint}")
            print(f"  OTEL_SERVICE_NAME: {os.getenv('OTEL_SERVICE_NAME', 'not set')}")
        else:
            print(f"  OTEL_EXPORTER_OTLP_ENDPOINT: not set (will use CrewAI Cloud only)")
    
    print("\n" + "=" * 60)
    
    # Create and run the crew
    crew = TechLeadCrew().crew()
    
    # Test with a sample Jira issue
    test_input = {
        "jira_issue_key": "TECBAC-131"  # Replace with a real issue key
    }
    
    print(f"\nRunning crew with input: {test_input}")
    print("=" * 60 + "\n")
    
    try:
        result = crew.kickoff(inputs=test_input)
        print("\n" + "=" * 60)
        print("Crew Execution Complete!")
        print("=" * 60)
        print(f"\nResult:\n{result}")
        
        # Access and display usage metrics
        if hasattr(crew, 'usage_metrics') and crew.usage_metrics:
            print("\n" + "=" * 60)
            print("📊 Usage Metrics:")
            print("=" * 60)
            # UsageMetrics is a Pydantic model, convert to dict first
            if hasattr(crew.usage_metrics, 'dict'):
                print(json.dumps(crew.usage_metrics.dict(), indent=2))
            else:
                print(json.dumps(crew.usage_metrics, indent=2, default=str))
        
        # Check for log file
        log_file = "logs.txt"
        if os.path.exists(log_file):
            print("\n" + "=" * 60)
            print(f"📝 Log file saved to: {os.path.abspath(log_file)}")
            print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

