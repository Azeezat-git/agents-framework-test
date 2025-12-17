import os
import logging
import asyncio
from typing import List, Any, Dict, Optional

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


class EventLoopSafeCrew:
    """
    Wrapper around Crew that refreshes MCP tools before each kickoff to prevent
    "Event loop is closed" errors on back-to-back requests.
    
    This ensures each request gets a fresh event loop context for MCP tools.
    """
    
    def __init__(self, crew: Crew, crew_base_instance: 'TechLeadCrew'):
        self._crew = crew
        self._crew_base = crew_base_instance
        self._original_agents = list(crew.agents) if hasattr(crew, 'agents') else []
        
    def _refresh_agent_tools(self):
        """
        Refresh MCP tools for all agents in the crew before each kickoff.
        This ensures tools have a fresh event loop context.
        
        This is called before both sync and async kickoff to prevent
        "Event loop is closed" errors on back-to-back requests.
        """
        try:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, loop should be available
                logger.debug("Running in async context, event loop available")
            except RuntimeError:
                # Not in async context, check if we can get/create a loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        logger.warning("Event loop is closed, will create new one when needed")
                        # Don't create loop here - let it be created when tools are called
                except RuntimeError:
                    # No event loop in current thread
                    logger.debug("No event loop in current thread, will be created when needed")
            
            # Refresh MCP tools using the crew base instance
            # This creates fresh tool instances with current event loop context
            if hasattr(self._crew_base, 'mcp_server_params') and self._crew_base.mcp_server_params:
                logger.debug("Refreshing MCP tools before kickoff to ensure fresh event loop context...")
                try:
                    # Get fresh MCP tools - this will use the current event loop context
                    fresh_tools = self._crew_base.get_mcp_tools()
                    logger.debug(f"Refreshed {len(fresh_tools)} MCP tool(s)")
                    
                    # Update tools for each agent
                    for agent in self._crew.agents:
                        if hasattr(agent, 'tools'):
                            # Replace tools with fresh ones that have current event loop context
                            agent.tools = fresh_tools
                            logger.debug(f"Updated tools for agent: {agent.role}")
                except Exception as e:
                    logger.warning(f"Failed to refresh MCP tools: {e}. Using existing tools.")
                    # Don't fail the request if tool refresh fails - use existing tools
            else:
                logger.debug("No MCP server params configured, skipping tool refresh")
        except Exception as e:
            logger.warning(f"Error refreshing agent tools: {e}. Continuing with existing tools.")
    
    def kickoff(self, inputs: Optional[Dict[str, Any]] = None, **kwargs):
        """Wrapper for kickoff that refreshes tools before execution."""
        self._refresh_agent_tools()
        return self._crew.kickoff(inputs=inputs, **kwargs)
    
    def kickoff_async(self, inputs: Optional[Dict[str, Any]] = None, **kwargs):
        """Wrapper for kickoff_async that refreshes tools before execution."""
        self._refresh_agent_tools()
        return self._crew.kickoff_async(inputs=inputs, **kwargs)
    
    def __getattr__(self, name):
        """Delegate all other attributes to the underlying crew."""
        return getattr(self._crew, name)

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
            verbose=False,  # Disable verbose to prevent showing task descriptions to users
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

        base_crew = Crew(
            agents=[self.tech_lead_crew()],  # Single agent
            tasks=[self.analyze_and_extract()],
            process=Process.sequential,
            verbose=False,  # Disable verbose to prevent showing task descriptions to users
            output_log_file=False,  # Disable file logging; show output on console only
        )
        
        # Wrap the crew to refresh MCP tools before each kickoff
        # This prevents "Event loop is closed" errors on back-to-back requests
        return EventLoopSafeCrew(base_crew, self)
