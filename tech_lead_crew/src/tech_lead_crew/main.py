import json
import logging
import os

import uvicorn
from kagent.crewai import KAgentApp

from tech_lead_crew.crew import TechLeadCrew

os.makedirs("output", exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Main entry point to run the KAgent CrewAI server."""
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
    
    # 1. Load the agent card or define it inline
    with open(os.path.join(os.path.dirname(__file__), "agent-card.json"), "r") as f:
        agent_card = json.load(f)

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
