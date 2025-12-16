import os
import logging
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Import MCPServerAdapter for explicit tool loading
MCPServerAdapter = None
try:
    from crewai_tools.adapters.mcp_adapter import MCPServerAdapter
except ImportError:
    try:
        from crewai_tools import MCPServerAdapter
    except ImportError:
        MCPServerAdapter = None

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

    # MCP server configuration for CrewBase's get_mcp_tools() method
    # This uses lazy connection and proper lifecycle management
    mcp_server_params = None  # Will be set in agent method

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
        # Use "gpt-3.5-turbo" which LiteLLM recognizes (CrewAI calls LiteLLM internally)
        # IMPORTANT: The gateway routes by URL path (/llm/bedrock/default), NOT by model name
        # So even though we use "gpt-3.5-turbo", the gateway will still route to Bedrock
        # because the base_url points to /llm/bedrock/default
        # The model name is just metadata for LiteLLM validation - it doesn't affect routing
        # Both CrewAI and LangGraph use the same gateway endpoint, so they get the same model
        custom_model = "gpt-3.5-turbo"
        
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
        
        # Remove trailing slashes - they can cause issues with URL parsing
        jira_url = jira_url.rstrip('/')
        bitbucket_url = bitbucket_url.rstrip('/')
        
        # Configure MCP server params for CrewBase's get_mcp_tools() method
        # Add connection timeout to prevent hanging during initialization
        self.mcp_server_params = [
            {
                "url": jira_url,
                "transport": "streamable-http"
            },
            {
                "url": bitbucket_url,
                "transport": "streamable-http"
            }
        ]
        
        # Set connection timeout for MCP servers (CrewBase attribute)
        # This prevents the agent from hanging if MCP servers are temporarily unavailable
        self.mcp_connect_timeout = 10  # 10 seconds timeout
        
        logger.info("Configuring MCP servers for CrewBase")
        logger.info(f"✅ Jira MCP URL: {jira_url}")
        logger.info(f"✅ Bitbucket MCP URL: {bitbucket_url}")
        logger.info(f"✅ MCP connection timeout: {self.mcp_connect_timeout}s")
        
        # Get MCP tools using CrewBase's method (handles lifecycle properly)
        # Add retry logic with exponential backoff for cluster startup scenarios
        # MCP servers might not be ready immediately when the pod starts
        mcp_tools = []
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to load MCP tools (attempt {attempt + 1}/{max_retries})...")
                mcp_tools = self.get_mcp_tools()
                logger.info(f"✅ Loaded {len(mcp_tools)} MCP tool(s) via get_mcp_tools()")
                if mcp_tools:
                    tool_names = [t.name if hasattr(t, 'name') else str(t) for t in mcp_tools[:5]]
                    logger.info(f"   Tools: {tool_names}")
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"⚠️  Failed to load MCP tools (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    logger.info(f"   Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    logger.error(f"❌ Failed to load MCP tools after {max_retries} attempts: {e}")
                    logger.error("   This will cause the agent to fail - MCP tools are required!")
                    # Re-raise the exception - we need tools to work, can't proceed without them
                    raise RuntimeError(
                        f"Failed to initialize MCP tools after {max_retries} retries. "
                        f"This is required for the agent to function. "
                        f"Last error: {e}. Please check MCP server connectivity and readiness."
                    ) from e
        
        # Create agent with explicitly loaded MCP tools (required for functionality)
        agent = Agent(
            config=self.agents_config['tech_lead_crew'],  # type: ignore[index]
            verbose=True,  # Enable verbose to see tool calls and responses
            llm=llm,
            tools=mcp_tools,  # MCP tools are required - no fallback
        )
        
        return agent

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
            verbose=False,  # Disable verbose to prevent showing task descriptions to users
            output_log_file=False,  # Disable file logging; show output on console only
        )
