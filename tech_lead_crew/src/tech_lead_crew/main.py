import json
import logging
import os

import uvicorn
from kagent.crewai import KAgentApp

from tech_lead_crew.crew import TechLeadCrew

os.makedirs("output", exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_otel_instrumentation():
    """
    Setup OpenTelemetry instrumentation for CrewAI (traces, logs, metrics).
    
    This should be called before creating the crew to ensure all telemetry
    is captured. Works with both CrewAI Cloud and custom OTEL endpoints.
    
    Environment variables needed:
    - OTEL_EXPORTER_OTLP_ENDPOINT: Your OTEL collector endpoint (optional)
    - OTEL_SERVICE_NAME: Service name for filtering (optional, defaults to tech-lead-crew)
    - OTEL_EXPORTER_OTLP_HEADERS: Auth headers if needed (optional)
    - OTEL_TRACES_EXPORTER: Set to 'otlp' to export traces (default: otlp if endpoint set)
    - OTEL_LOGS_EXPORTER: Set to 'otlp' to export logs (optional)
    - OTEL_METRICS_EXPORTER: Set to 'otlp' to export metrics (optional)
    - CREWAI_TRACING_ENABLED: Set to 'true' to enable tracing (optional)
    - OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: Set to 'true' for auto log export (optional)
    """
    # Only instrument if OTEL endpoint is set OR CrewAI tracing is enabled
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    tracing_enabled = os.getenv("CREWAI_TRACING_ENABLED", "").lower() == "true"
    
    if otel_endpoint or tracing_enabled:
        try:
            # 1. Setup CrewAI instrumentation (traces)
            from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
            CrewAIInstrumentor().instrument()
            
            # 2. Setup Python logging to OTEL (if enabled)
            logs_exporter = os.getenv("OTEL_LOGS_EXPORTER", "").lower()
            if logs_exporter == "otlp" and otel_endpoint:
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
            if metrics_exporter == "otlp" and otel_endpoint:
                try:
                    from opentelemetry import metrics
                    from opentelemetry.sdk.metrics import MeterProvider
                    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
                    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
                    
                    # Parse headers if provided
                    headers = {}
                    if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
                        for item in os.getenv("OTEL_EXPORTER_OTLP_HEADERS").split(","):
                            if "=" in item:
                                k, v = item.split("=", 1)
                                headers[k.strip()] = v.strip()
                    
                    metric_exporter = OTLPMetricExporter(
                        endpoint=otel_endpoint,
                        headers=headers if headers else None
                    )
                    metric_reader = PeriodicExportingMetricReader(metric_exporter)
                    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
                    logger.info("✅ OTEL metrics export enabled")
                except ImportError:
                    logger.warning("⚠️  OTEL metrics packages not installed - metrics export skipped")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to enable OTEL metrics: {e}")
            
            logger.info("✅ OTEL instrumentation enabled for CrewAI")
            if otel_endpoint:
                logger.info(f"   Sending to: {otel_endpoint}")
                logger.info(f"   Traces: {'✅' if os.getenv('OTEL_TRACES_EXPORTER', 'otlp').lower() == 'otlp' else '❌'}")
                logger.info(f"   Logs: {'✅' if logs_exporter == 'otlp' else '❌'}")
                logger.info(f"   Metrics: {'✅' if metrics_exporter == 'otlp' else '❌'}")
            else:
                logger.info("   Using CrewAI Cloud (set OTEL_EXPORTER_OTLP_ENDPOINT for custom endpoint)")
        except ImportError:
            logger.warning("⚠️  opentelemetry-instrumentation-crewai not found - OTEL instrumentation skipped")
        except Exception as e:
            logger.warning(f"⚠️  Failed to enable OTEL instrumentation: {e}")


def main():
    """Main entry point to run the KAgent CrewAI server."""
    # Setup OTEL instrumentation BEFORE creating the crew
    # This ensures all traces are captured from the start
    setup_otel_instrumentation()
    
    # KAGENT_URL should be set by KAgent controller automatically
    # In cluster: http://kagent-controller.core-kagent:8083
    # For local testing: kubectl port-forward -n core-kagent svc/kagent-controller 8083:8083
    # Then set: export KAGENT_URL=http://localhost:8083
    if not os.getenv("KAGENT_URL"):
        # Fallback only if KAgent controller didn't inject it (shouldn't happen in cluster)
        kagent_url = "http://kagent-controller.core-kagent:8083"
        os.environ["KAGENT_URL"] = kagent_url
        logger.warning(f"⚠️  KAGENT_URL not set by KAgent controller, using fallback: {kagent_url}")
        logger.info("For local testing, port-forward: kubectl port-forward -n core-kagent svc/kagent-controller 8083:8083")
        logger.info("Then set: export KAGENT_URL=http://localhost:8083")
    else:
        logger.info(f"✅ Using KAGENT_URL from environment: {os.getenv('KAGENT_URL')}")
    
    # 1. Load the agent card
    # Try installed package location first, then source location (for Docker builds)
    agent_card_paths = [
        os.path.join(os.path.dirname(__file__), "agent-card.json"),  # Installed package
        os.path.join("/app", "src", "tech_lead_crew", "agent-card.json"),  # Docker source location
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tech_lead_crew", "agent-card.json"),  # Local dev
    ]
    
    agent_card = {}
    for path in agent_card_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                agent_card = json.load(f)
            logger.info(f"✅ Loaded agent card from: {path}")
            break
    else:
        logger.warning("⚠️  Agent card not found, using empty dict")
        agent_card = {}

    # 2. Load the Crew, then create the kagent app
    app = KAgentApp(crew=TechLeadCrew().crew(), agent_card=agent_card)

    # 3. Build the FastAPI app and run the server
    server = app.build()
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
