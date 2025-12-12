import os
import logging
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.mcp import MCPServerHTTP
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
import litellm

logger = logging.getLogger(__name__)

# Keep LiteLLM tolerant to custom gateway params
litellm.drop_params = True

@CrewBase
class TechLeadCrew():
    """TechLeadCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def _build_llm(self):
        gateway_base_url = os.getenv(
            "GATEWAY_BASE_URL",
            "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/llm/bedrock/default"
        )
        gateway_model = os.getenv("GATEWAY_MODEL", "bedrock-default")
        gateway_api_key = os.getenv("GATEWAY_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        
        if not gateway_api_key or gateway_api_key == "dummy-key":
            gateway_api_key = "irsa-placeholder-key"
            logger.info("Using IRSA placeholder key - agentgateway authenticates via IAM role, not API key")
        
        os.environ["OPENAI_API_KEY"] = gateway_api_key
        gateway_base = gateway_base_url.rstrip("/")
        openai_base_url = f"{gateway_base}/v1"
        os.environ["OPENAI_BASE_URL"] = openai_base_url
        os.environ["OPENAI_API_BASE"] = openai_base_url  # safety for variants
        
        litellm.suppress_debug_info = True
        custom_model = "just-dummy"
        
        class ModelLoggingHandler(BaseCallbackHandler):
            def on_llm_end(self, response, **kwargs):  # type: ignore[override]
                try:
                    model = None
                    if hasattr(response, "llm_output") and isinstance(response.llm_output, dict):
                        model = response.llm_output.get("model")
                    if not model and hasattr(response, "model"):
                        model = getattr(response, "model", None)
                    if model:
                        logger.info(f"[LLM] Gateway returned model: {model}")
                except Exception as exc:  # pragma: no cover - logging only
                    logger.debug(f"[LLM] Failed to log model: {exc}")

        llm = ChatOpenAI(
            model=custom_model,
            base_url=openai_base_url,
            api_key=gateway_api_key,
            temperature=0.0,
            timeout=60,
            callbacks=[ModelLoggingHandler()],
        )
        return llm
        
    @agent
    def tech_lead_crew(self) -> Agent:
        """Tech Lead agent that uses Jira MCP over HTTP and Bedrock via gateway"""
        llm = self._build_llm()
        return Agent(
            config=self.agents_config['tech_lead_crew'],  # type: ignore[index]
            verbose=True,
            llm=llm,
            mcps=[
                MCPServerHTTP(
                    url=os.getenv("JIRA_MCP_URL", "http://localhost:3001/mcp"),
                    streamable=True,
                    cache_tools_list=True,
                ),
                MCPServerHTTP(
                    url=os.getenv("BITBUCKET_MCP_URL", "http://localhost:3000/mcp"),
                    streamable=True,
                    cache_tools_list=True,
                ),
            ],
        )

    @task
    def analyze_and_extract(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_and_extract'],  # type: ignore[index]
            agent=self.tech_lead_crew(),
        )

    @crew
    def crew(self) -> Crew:
        """Creates the TechLeadCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=[self.tech_lead_crew()],  # Single agent
            tasks=[self.analyze_and_extract()],
            process=Process.sequential,
            verbose=True,
            output_log_file=False,  # Disable file logging; show output on console only
        )
