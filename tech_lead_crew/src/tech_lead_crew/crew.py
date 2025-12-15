import os
import logging
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Try to import MCPServerAdapter first (newer API), then fallback to MCPServerHTTP
# Note: Don't use logger here as it's not defined yet - will log later when used
MCPServerAdapter = None
MCPServerHTTP = None

try:
    from crewai_tools.adapters.mcp_adapter import MCPServerAdapter
except ImportError:
    try:
        from crewai_tools import MCPServerAdapter
    except ImportError:
        try:
            from crewai.mcp import MCPServerHTTP
        except ImportError:
            try:
                from crewai_tools.mcp import MCPServerHTTP
            except ImportError:
                try:
                    from crewai import MCPServerHTTP
                except ImportError:
                    raise ImportError(
                        "Neither MCPServerAdapter nor MCPServerHTTP found. "
                        "Please ensure crewai-tools[mcp] is installed. "
                        "Try: pip install 'crewai-tools[mcp]>=0.10.0'"
                    )
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
        # Use "just-dummy" to match LangGraph implementation
        # The gateway routes by URL path (/llm/bedrock/default), NOT by model name
        # ChatOpenAI accepts any model name when using custom base_url
        # If CrewAI calls LiteLLM directly and it fails, we'll handle it gracefully
        custom_model = "just-dummy"
        
        # Configure LiteLLM to recognize "just-dummy" (helps if CrewAI calls LiteLLM directly)
        # Add to model_cost_map so LiteLLM doesn't reject it
        if not hasattr(litellm, 'model_cost_map') or not litellm.model_cost_map:
            litellm.model_cost_map = {}
        # Add just-dummy to model cost map (LiteLLM uses this for validation)
        if "just-dummy" not in litellm.model_cost_map:
            litellm.model_cost_map["just-dummy"] = {
                "input_cost_per_token": 0.0000015,
                "output_cost_per_token": 0.000002
            }
        
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
        # Build MCP server instances - handle both MCPServerHTTP and MCPServerAdapter APIs
        jira_url = os.getenv("JIRA_MCP_URL")
        if not jira_url:
            raise ValueError(
                "JIRA_MCP_URL must be set (no default). "
                "For cluster via gateway, use e.g.: "
                "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/jira-mcp/"
            )
        bitbucket_url = os.getenv("BITBUCKET_MCP_URL")
        if not bitbucket_url:
            raise ValueError(
                "BITBUCKET_MCP_URL must be set (no default). "
                "For cluster via gateway, use e.g.: "
                "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/bitbucket-mcp/"
            )
        
        # Initialize MCP servers - create them but don't connect yet (lazy connection)
        # This allows the agent to start even if MCP servers are temporarily unavailable
        jira_mcp = None
        bitbucket_mcp = None
        
        # Try to create MCP server instances without connecting
        # They will connect when tools are actually called
        if MCPServerAdapter:
            # Strategy 1: Use MCPServerAdapter (newer API, preferred)
            logger.info("Creating MCPServerAdapter instances")
            try:
                # MCPServerAdapter connects immediately, so we need to handle connection errors
                # Try to create adapters - they will attempt to connect
                jira_mcp = MCPServerAdapter(
                    serverparams={"url": jira_url}
                )
                logger.info("✅ Created Jira MCPServerAdapter")
            except Exception as jira_error:
                logger.warning(f"Jira MCPServerAdapter creation failed: {jira_error}")
                jira_mcp = None
            
            try:
                bitbucket_mcp = MCPServerAdapter(
                    serverparams={"url": bitbucket_url}
                )
                logger.info("✅ Created Bitbucket MCPServerAdapter")
            except Exception as bitbucket_error:
                logger.warning(f"Bitbucket MCPServerAdapter creation failed: {bitbucket_error}")
                bitbucket_mcp = None
            
            # If both failed, try fallback
            if not jira_mcp and not bitbucket_mcp and MCPServerHTTP:
                logger.info("Both MCPServerAdapter instances failed, falling back to MCPServerHTTP")
        
        # Strategy 2: Fallback to MCPServerHTTP if MCPServerAdapter failed or not available
        if (not jira_mcp or not bitbucket_mcp) and MCPServerHTTP:
            logger.info("Attempting to use MCPServerHTTP (fallback)")
            try:
                import inspect
                sig = inspect.signature(MCPServerHTTP.__init__)
                if 'url' in sig.parameters:
                    # Create without connecting - should be lazy
                    jira_mcp = MCPServerHTTP(
                        url=jira_url,
                        streamable=True,
                        cache_tools_list=True,
                    )
                    bitbucket_mcp = MCPServerHTTP(
                        url=bitbucket_url,
                        streamable=True,
                        cache_tools_list=True,
                    )
                    logger.info("✅ Created MCPServerHTTP instances (will connect when tools are used)")
                else:
                    raise AttributeError("MCPServerHTTP doesn't support 'url' parameter")
            except Exception as http_api_error:
                logger.warning(f"MCPServerHTTP creation failed: {http_api_error}")
                logger.warning("⚠️  Agent will start without MCP tools - they may fail when called")
        
        # Don't fail if MCP creation fails - agent can still start
        # MCP tools will fail when called, but that's better than crashing on startup
        if not jira_mcp or not bitbucket_mcp:
            logger.warning(
                "⚠️  Could not create MCP server instances. "
                "Agent will start but MCP tools will not be available. "
                f"MCPServerAdapter available: {MCPServerAdapter is not None}, "
                f"MCPServerHTTP available: {MCPServerHTTP is not None}"
            )
            # Create empty list instead of failing
            jira_mcp = None
            bitbucket_mcp = None
        
        # Only include MCP servers if they were successfully created
        mcp_list = []
        if jira_mcp:
            mcp_list.append(jira_mcp)
        if bitbucket_mcp:
            mcp_list.append(bitbucket_mcp)
        
        if not mcp_list:
            logger.warning("⚠️  No MCP servers available - agent will work without MCP tools")
        
        return Agent(
            config=self.agents_config['tech_lead_crew'],  # type: ignore[index]
            verbose=True,
            llm=llm,
            mcps=mcp_list if mcp_list else None,  # Pass None or empty list if no MCPs
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
