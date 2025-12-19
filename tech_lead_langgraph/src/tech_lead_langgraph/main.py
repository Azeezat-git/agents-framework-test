"""
LangGraph-based Tech Lead agent main entry point for KAgent BYO deployment.

This follows the same pattern as CrewAI's main.py but uses kagent.langgraph.KAgentApp
instead of kagent.crewai.KAgentApp.
"""
import json
import logging
import os

import uvicorn

os.makedirs("output", exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_otel_instrumentation():
    """
    Setup OpenTelemetry instrumentation for LangGraph (traces, logs, metrics).
    OTEL is the single source of telemetry; LangSmith is intentionally disabled.

    Environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: Your OTEL collector endpoint (e.g., http://collector:4317)
    - OTEL_EXPORTER_OTLP_HEADERS: Auth headers if needed (e.g., "Authorization=Bearer TOKEN")
    - OTEL_SERVICE_NAME: Service name (defaults to tech-lead-langgraph)
    - OTEL_TRACES_EXPORTER: Set to 'otlp' to export traces
    - OTEL_LOGS_EXPORTER: Set to 'otlp' to export logs
    - OTEL_METRICS_EXPORTER: Set to 'otlp' to export metrics
    """
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otel_endpoint:
        logger.warning("⚠️  OTEL_EXPORTER_OTLP_ENDPOINT not set; telemetry will be disabled.")
        logger.warning("   Set OTEL_EXPORTER_OTLP_ENDPOINT to enable OpenTelemetry instrumentation.")
        return
    
    # Continue with instrumentation setup
    try:
        # 1. Setup LangChain/LangGraph instrumentation (traces)
        from opentelemetry.instrumentation.langchain import LangchainInstrumentor
        LangchainInstrumentor().instrument()
        logger.info("✅ OTEL LangChain instrumentation enabled")
        
        # 2. Setup Python logging to OTEL (if enabled)
        logs_exporter = os.getenv("OTEL_LOGS_EXPORTER", "").lower()
        if logs_exporter == "otlp":
            try:
                from opentelemetry.instrumentation.logging import LoggingInstrumentor
                LoggingInstrumentor().instrument(set_logging_format=True)
                logger.info("✅ OTEL logging export enabled")
            except ImportError:
                logger.warning("⚠️  opentelemetry-instrumentation-logging not installed - log export skipped")
            except Exception as e:
                logger.warning(f"⚠️  Failed to enable OTEL logging: {e}")
        
        # 3. Setup metrics export (if enabled)
        metrics_exporter = os.getenv("OTEL_METRICS_EXPORTER", "").lower()
        if metrics_exporter == "otlp":
            try:
                from opentelemetry import metrics
                from opentelemetry.sdk.metrics import MeterProvider
                from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
                
                # Parse headers if provided
                headers = {}
                if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
                    for item in os.getenv("OTEL_EXPORTER_OTLP_HEADERS").split(","):
                        if "=" in item:
                            k, v = item.split("=", 1)
                            headers[k.strip()] = v.strip()
                
                # Use HTTP exporter (port 4317 is HTTP, not gRPC)
                metric_exporter = OTLPMetricExporter(
                    endpoint=otel_endpoint,
                    headers=headers if headers else None
                )
                metric_reader = PeriodicExportingMetricReader(metric_exporter)
                metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
                logger.info("✅ OTEL metrics export enabled (HTTP)")
            except ImportError:
                logger.warning("⚠️  OTEL metrics packages not installed - metrics export skipped")
            except Exception as e:
                logger.warning(f"⚠️  Failed to enable OTEL metrics: {e}")
        
        logger.info("✅ Custom OTEL endpoint configured")
        logger.info(f"   Sending to: {otel_endpoint}")
        logger.info(f"   Traces: {'✅' if os.getenv('OTEL_TRACES_EXPORTER', 'otlp').lower() == 'otlp' else '❌'}")
        logger.info(f"   Logs: {'✅' if logs_exporter == 'otlp' else '❌'}")
        logger.info(f"   Metrics: {'✅' if metrics_exporter == 'otlp' else '❌'}")
    except ImportError:
        logger.warning("⚠️  opentelemetry-instrumentation-langchain not found - custom OTEL skipped")
    except Exception as e:
        logger.warning(f"⚠️  Failed to enable custom OTEL: {e}")


def run(inputs: dict | None = None):
    """
    Run the LangGraph agent (for local testing).
    
    Args:
        inputs: Dictionary with 'jira_issue_key' key
        
    Returns:
        Final state dictionary with 'final_output' and other fields
    """
    from tech_lead_langgraph.graph import build_graph, AgentState
    from langchain_core.messages import HumanMessage
    
    if inputs is None:
        inputs = {"jira_issue_key": "TECBAC-209"}
    
    # Build graph
    graph = build_graph()
    
    # Create initial state
    initial_state: AgentState = {
        "messages": [HumanMessage(content=f"Analyze Jira issue {inputs.get('jira_issue_key')}")],
        "jira_issue_key": inputs.get("jira_issue_key", ""),
        "jira_issue": None,
        "workspace": None,
        "repo_slug": None,
        "repo_list": None,
        "repo_files": None,
        "final_output": None,
    }
    
    # Run graph
    logger.info("Starting LangGraph execution...")
    result = graph.invoke(initial_state)
    logger.info("LangGraph execution completed")
    
    return result


def main():
    """Main entry point to run the KAgent LangGraph server."""
    # Setup OTEL instrumentation BEFORE creating the graph
    # This ensures all traces are captured from the start
    setup_otel_instrumentation()
    
    # Set KAGENT_URL if not already set
    # For local testing, port-forward: kubectl port-forward -n core-kagent svc/kagent-controller 8083:8083
    # Then set: export KAGENT_URL=http://localhost:8083
    # Or use the cluster service URL: http://kagent-controller.core-kagent.svc.cluster.local:8083
    if not os.getenv("KAGENT_URL"):
        kagent_url = os.getenv(
            "KAGENT_URL",
            "http://kagent-controller.core-kagent.svc.cluster.local:8083"
        )
        os.environ["KAGENT_URL"] = kagent_url
        logger.info(f"Using KAGENT_URL: {kagent_url}")
        logger.info("To override, set KAGENT_URL environment variable")
        logger.info("For local testing, port-forward: kubectl port-forward -n core-kagent svc/kagent-controller 8083:8083")
        logger.info("Then set: export KAGENT_URL=http://localhost:8083")
    
    # Try to import kagent.langgraph
    try:
        from kagent.langgraph import KAgentApp
        KAGENT_AVAILABLE = True
        logger.info("✅ kagent.langgraph available")
    except (ImportError, ModuleNotFoundError) as e:
        KAGENT_AVAILABLE = False
        logger.warning(f"⚠️  kagent.langgraph not available: {e}")
        logger.warning("   Will run without KAgent integration (standalone mode)")
    
    # 1. Load the agent card
    agent_card_path = os.path.join(os.path.dirname(__file__), "agent-card.json")
    agent_card = {}
    if os.path.exists(agent_card_path):
        with open(agent_card_path, "r") as f:
            agent_card = json.load(f)
        logger.info(f"✅ Loaded agent card: {agent_card.get('name', 'unknown')}")
    else:
        logger.warning(f"⚠️  Agent card not found at {agent_card_path}")
    
    # 2. Build the graph
    from tech_lead_langgraph.graph import build_graph
    graph = build_graph()
    logger.info("✅ LangGraph built successfully")
    
    # 3. Create KAgent app or fallback to standalone
    if KAGENT_AVAILABLE:
        from kagent.core._config import KAgentConfig
        config = KAgentConfig()
        app = KAgentApp(graph=graph, agent_card=agent_card, config=config)
        logger.info("✅ KAgent app created")
    else:
        # Fallback: Create a simple FastAPI wrapper
        from fastapi import FastAPI
        from tech_lead_langgraph.graph import AgentState
        from langchain_core.messages import HumanMessage
        
        app = FastAPI(title="Tech Lead LangGraph Agent")
        
        @app.post("/invoke")
        async def invoke_graph(inputs: dict):
            """Invoke the graph with inputs"""
            initial_state: AgentState = {
                "messages": [HumanMessage(content=f"Analyze Jira issue {inputs.get('jira_issue_key', '')}")],
                "jira_issue_key": inputs.get("jira_issue_key", ""),
                "jira_issue": None,
                "workspace": None,
                "repo_slug": None,
                "repo_list": None,
                "repo_files": None,
                "final_output": None,
            }
            result = graph.invoke(initial_state)
            return {"result": result.get("final_output", "N/A")}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        logger.info("✅ Created standalone FastAPI app (KAgent not available)")
    
    # 4. Build the FastAPI server and run
    if KAGENT_AVAILABLE:
        server = app.build()
    else:
        server = app
    
    # 4.5. Instrument FastAPI for HTTP route tracing
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor().instrument_app(server)
            logger.info("✅ FastAPI instrumentation enabled - HTTP routes will be traced")
        except ImportError:
            logger.warning("⚠️  opentelemetry-instrumentation-fastapi not installed - HTTP routes won't be traced")
        except Exception as e:
            logger.warning(f"⚠️  Failed to enable FastAPI instrumentation: {e}")
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        server,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
