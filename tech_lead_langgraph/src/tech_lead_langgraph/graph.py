"""
LangGraph-based Tech Lead agent graph definition.
Maps CrewAI components to LangGraph nodes and state.
"""
import os
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from fastmcp.client import Client
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State schema for the Tech Lead agent graph"""
    messages: Annotated[Sequence[BaseMessage], "Chat message history"]
    jira_issue_key: str
    jira_issue: dict | None
    workspace: str | None
    repo_slug: str | None
    repo_list: list | None
    repo_files: dict | None
    final_output: str | None


class MCPToolWrapper:
    """Wrapper to convert MCP tools to LangChain tools"""
    
    def __init__(self, mcp_url: str, tool_name: str):
        self.mcp_url = mcp_url
        self.tool_name = tool_name
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            self._client = Client(self.mcp_url)
            await self._client.__aenter__()
        return self._client
    
    async def call(self, **kwargs):
        """Call the MCP tool asynchronously"""
        client = await self._get_client()
        return await client.call_tool(self.tool_name, kwargs)


def build_llm():
    """Build LLM pointing to agent gateway (same as CrewAI version)"""
    gateway_base_url = os.getenv(
        "GATEWAY_BASE_URL",
        "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/llm/bedrock/default"
    )
    gateway_api_key = os.getenv("GATEWAY_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    
    if not gateway_api_key or gateway_api_key == "dummy-key":
        gateway_api_key = "irsa-placeholder-key"
        logger.info("Using IRSA placeholder key")
    
    gateway_base = gateway_base_url.rstrip("/")
    openai_base_url = f"{gateway_base}/v1"
    
    return ChatOpenAI(
        model="just-dummy",  # Same placeholder as CrewAI
        base_url=openai_base_url,
        api_key=gateway_api_key,
        temperature=0.0,
        timeout=60,
    )


def create_mcp_tools():
    """Create LangChain tools from MCP servers"""
    # TODO: Convert MCP tools to LangChain BaseTool instances
    # For now, return empty list - will implement MCP tool integration
    jira_mcp_url = os.getenv("JIRA_MCP_URL")
    bitbucket_mcp_url = os.getenv("BITBUCKET_MCP_URL")

    if not jira_mcp_url or not bitbucket_mcp_url:
        raise ValueError(
            "JIRA_MCP_URL and BITBUCKET_MCP_URL must be set (no defaults). "
            "For cluster via gateway, use e.g.: "
            "JIRA_MCP_URL=http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/jira-mcp/ "
            "BITBUCKET_MCP_URL=http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/bitbucket-mcp/"
        )
    
    # Placeholder - will implement proper MCP tool wrapping
    return []


def process_input(state: AgentState) -> AgentState:
    """Node: Process initial input and extract Jira issue key from messages"""
    messages = state.get("messages", [])
    
    # Ensure messages are BaseMessage objects, not tuples
    normalized_messages = []
    for msg in messages:
        if isinstance(msg, tuple):
            # Convert tuple to proper message object
            # Tuples from LangGraph are typically (message_type, content) or just content
            if len(msg) == 2:
                msg_type, content = msg
                if msg_type == "human" or msg_type == "user":
                    normalized_messages.append(HumanMessage(content=str(content)))
                elif msg_type == "ai" or msg_type == "assistant":
                    normalized_messages.append(AIMessage(content=str(content)))
                else:
                    # Default to HumanMessage
                    normalized_messages.append(HumanMessage(content=str(content)))
            else:
                # Single element tuple, treat as content
                normalized_messages.append(HumanMessage(content=str(msg[0])))
        elif isinstance(msg, BaseMessage):
            normalized_messages.append(msg)
        else:
            # Convert other types to HumanMessage
            normalized_messages.append(HumanMessage(content=str(msg)))
    
    # Update state with normalized messages
    state["messages"] = normalized_messages
    
    # Extract Jira issue key from the last user message
    jira_issue_key = None
    if normalized_messages:
        last_message = normalized_messages[-1]
        content = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Extract Jira issue key (format: PROJ-123)
        import re
        match = re.search(r'([A-Z]+-\d+)', content)
        if match:
            jira_issue_key = match.group(1)
            logger.info(f"Extracted Jira issue key from message: {jira_issue_key}")
        else:
            # If no issue key found, try to use the whole content as issue key
            content_stripped = content.strip()
            if re.match(r'^[A-Z]+-\d+$', content_stripped):
                jira_issue_key = content_stripped
                logger.info(f"Using entire message as Jira issue key: {jira_issue_key}")
    
    if jira_issue_key:
        state["jira_issue_key"] = jira_issue_key
        logger.info(f"✅ Processed input, extracted issue key: {jira_issue_key}")
    else:
        logger.warning("No Jira issue key found in messages")
        # Try to use existing jira_issue_key from state
        if not state.get("jira_issue_key"):
            state["jira_issue_key"] = ""
    
    return state


def fetch_jira_issue(state: AgentState) -> AgentState:
    """Node: Fetch Jira issue using MCP tool"""
    issue_key = state.get("jira_issue_key")
    if not issue_key:
        return state
    
    logger.info(f"Fetching Jira issue: {issue_key}")
    try:
        from .mcp_tools import create_jira_tools
        jira_tools = create_jira_tools()
        jira_get_issue_tool = jira_tools[0]  # First tool is jira_get_issue
        
        # Call MCP tool (jira_get_issue expects issue_key as positional or keyword)
        result_str = jira_get_issue_tool._run(issue_key=issue_key)
        
        # Parse result (it's a JSON string from MCP tool)
        import json
        try:
            if isinstance(result_str, str):
                # Try to parse JSON
                if result_str.strip().startswith('{') or result_str.strip().startswith('['):
                    state["jira_issue"] = json.loads(result_str)
                else:
                    # Not JSON, might be error message
                    logger.warning(f"Unexpected result format: {result_str[:100]}")
                    state["jira_issue"] = None
            else:
                state["jira_issue"] = result_str
            logger.info(f"✅ Fetched Jira issue: {issue_key}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Jira issue result as JSON: {e}. Result: {result_str[:200]}")
            state["jira_issue"] = None
    except Exception as e:
        logger.error(f"Error fetching Jira issue: {e}")
        state["jira_issue"] = None
    return state


def extract_repo_info(state: AgentState) -> AgentState:
    """Node: Extract workspace/repo from Jira issue"""
    jira_issue = state.get("jira_issue")
    if not jira_issue:
        logger.warning("No Jira issue data to extract repo info from")
        return state
    
    logger.info("Extracting repository information from Jira issue")
    try:
        # Extract Bitbucket URL from Jira issue description or links
        description = jira_issue.get("description", "")
        url = jira_issue.get("url", "")
        
        # Look for Bitbucket URL pattern: https://source.app.pconnect.biz/projects/{workspace}/repos/{repo}/browse
        import re
        bitbucket_pattern = r"https://source\.app\.pconnect\.biz/projects/([^/]+)/repos/([^/]+)"
        
        workspace = None
        repo_slug = None
        
        # Try description first
        match = re.search(bitbucket_pattern, description)
        if match:
            workspace = match.group(1)
            repo_slug = match.group(2)
        else:
            # Try URL field
            match = re.search(bitbucket_pattern, url)
            if match:
                workspace = match.group(1)
                repo_slug = match.group(2)
            else:
                # Fallback: use project key as workspace
                project_key = jira_issue.get("project", {}).get("key") if isinstance(jira_issue.get("project"), dict) else None
                if project_key:
                    workspace = project_key
                    logger.info(f"Using project key as workspace fallback: {workspace}")
        
        if workspace:
            state["workspace"] = workspace
            logger.info(f"✅ Extracted workspace: {workspace}")
        if repo_slug:
            state["repo_slug"] = repo_slug
            logger.info(f"✅ Extracted repo_slug: {repo_slug}")
    except Exception as e:
        logger.error(f"Error extracting repo info: {e}")
    
    return state


def list_repositories(state: AgentState) -> AgentState:
    """Node: List repositories in workspace"""
    workspace = state.get("workspace")
    if not workspace:
        logger.warning("No workspace available to list repositories")
        return state
    
    logger.info(f"Listing repositories in workspace: {workspace}")
    try:
        from .mcp_tools import create_bitbucket_tools
        bitbucket_tools = create_bitbucket_tools()
        list_repos_tool = bitbucket_tools[0]  # First tool is listRepositories
        
        # Call MCP tool
        result = list_repos_tool._run(workspace=workspace)
        
        # Parse result
        import json
        if isinstance(result, str):
            state["repo_list"] = json.loads(result)
        else:
            state["repo_list"] = result
        
        # If we have a repo_slug, find it in the list
        repo_slug = state.get("repo_slug")
        if repo_slug and state["repo_list"]:
            for repo in state["repo_list"]:
                if isinstance(repo, dict) and repo.get("slug") == repo_slug:
                    logger.info(f"✅ Found repository: {repo_slug}")
                    break
        
        logger.info(f"✅ Listed {len(state['repo_list']) if state['repo_list'] else 0} repositories")
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        state["repo_list"] = None
    return state


def list_repo_files(state: AgentState) -> AgentState:
    """Node: List repository files"""
    workspace = state.get("workspace")
    repo_slug = state.get("repo_slug")
    if not workspace or not repo_slug:
        logger.warning(f"Missing workspace or repo_slug: workspace={workspace}, repo_slug={repo_slug}")
        return state
    
    logger.info(f"Listing files in {workspace}/{repo_slug}")
    try:
        from .mcp_tools import create_bitbucket_tools
        bitbucket_tools = create_bitbucket_tools()
        list_files_tool = bitbucket_tools[1]  # Second tool is listRepositoryFiles
        
        # First, list root directory (listRepositoryFiles expects workspace, repo_slug, path)
        result = list_files_tool._run(workspace=workspace, repo_slug=repo_slug, path="")
        
        import json
        if isinstance(result, str):
            root_files = json.loads(result)
        else:
            root_files = result
        
        # Look for web-store directory
        web_store_path = None
        if isinstance(root_files, dict) and "files" in root_files:
            for file_info in root_files["files"]:
                if isinstance(file_info, dict) and file_info.get("path") == "web-store" and file_info.get("type") == "directory":
                    web_store_path = "web-store"
                    break
        
        # If web-store found, list its contents
        if web_store_path:
            result = list_files_tool._run(workspace=workspace, repo_slug=repo_slug, path=web_store_path)
            if isinstance(result, str):
                state["repo_files"] = {"root": root_files, "web_store": json.loads(result)}
            else:
                state["repo_files"] = {"root": root_files, "web_store": result}
            logger.info(f"✅ Listed files in {workspace}/{repo_slug}/{web_store_path}")
        else:
            state["repo_files"] = {"root": root_files}
            logger.info(f"✅ Listed root files in {workspace}/{repo_slug}")
    except Exception as e:
        logger.error(f"Error listing repository files: {e}")
        state["repo_files"] = None
    return state


def synthesize_output(state: AgentState) -> AgentState:
    """Node: Synthesize final output using LLM (matching CrewAI format)"""
    llm = build_llm()
    
    logger.info("Synthesizing final output")
    try:
        # Build comprehensive prompt matching CrewAI task format
        jira_issue = state.get("jira_issue", {})
        repo_files = state.get("repo_files", {})
        repo_list = state.get("repo_list", [])
        workspace = state.get("workspace")
        repo_slug = state.get("repo_slug")
        
        # Extract Jira issue details
        issue_key = state.get("jira_issue_key", "N/A")
        issue_summary = ""
        issue_description = ""
        issue_status = ""
        issue_priority = ""
        issue_assignee = ""
        issue_reporter = ""
        issue_labels = []
        issue_url = ""
        project_key = ""
        acceptance_criteria = ""
        
        if isinstance(jira_issue, dict):
            issue_summary = jira_issue.get("summary", "N/A")
            issue_description = jira_issue.get("description", "N/A")
            issue_status = jira_issue.get("status", {}).get("name", "N/A") if isinstance(jira_issue.get("status"), dict) else "N/A"
            issue_priority = jira_issue.get("priority", {}).get("name", "N/A") if isinstance(jira_issue.get("priority"), dict) else "N/A"
            
            # Assignee
            assignee_obj = jira_issue.get("assignee")
            if assignee_obj:
                if isinstance(assignee_obj, dict):
                    issue_assignee = assignee_obj.get("displayName", "Unassigned")
                else:
                    issue_assignee = str(assignee_obj)
            else:
                issue_assignee = "Unassigned"
            
            # Reporter
            reporter_obj = jira_issue.get("reporter")
            if reporter_obj and isinstance(reporter_obj, dict):
                issue_reporter = f"{reporter_obj.get('displayName', 'N/A')} ({reporter_obj.get('emailAddress', 'N/A')})"
            
            # Labels
            labels = jira_issue.get("labels", [])
            issue_labels = labels if isinstance(labels, list) else []
            
            # URL
            issue_url = jira_issue.get("url", "")
            
            # Project
            project = jira_issue.get("project", {})
            if isinstance(project, dict):
                project_key = project.get("key", "")
            
            # Fallback: extract project key from issue key (e.g., "TECBAC" from "TECBAC-209")
            if not project_key and issue_key:
                parts = issue_key.split("-")
                if len(parts) > 0:
                    project_key = parts[0]
            
            # Acceptance criteria (often in description or custom fields)
            # Try to extract from description if it contains acceptance criteria
            if "acceptance criteria" in issue_description.lower() or "acceptance" in issue_description.lower():
                # Extract acceptance criteria section if present
                import re
                ac_match = re.search(r'(?i)(acceptance criteria|acceptance):\s*(.+?)(?:\n\n|\n#|$)', issue_description, re.DOTALL)
                if ac_match:
                    acceptance_criteria = ac_match.group(2).strip()
                else:
                    acceptance_criteria = "See description"
            else:
                acceptance_criteria = "See description"
        
        # Build repository context
        repo_context_parts = []
        if workspace:
            repo_context_parts.append(f"- Bitbucket Workspace: {workspace}")
        if repo_slug:
            repo_context_parts.append(f"- Repository: {repo_slug}")
        if issue_url:
            repo_context_parts.append(f"- Linked Repository: {issue_url}")
        if project_key:
            repo_context_parts.append(f"- Project Key: {project_key}")
        
        # Extract repository structure info
        repo_structure = ""
        if repo_files:
            import json
            # Extract key information about project structure
            if isinstance(repo_files, dict):
                if "web_store" in repo_files:
                    web_store_files = repo_files["web_store"]
                    if isinstance(web_store_files, dict) and "files" in web_store_files:
                        files_list = web_store_files["files"]
                        file_names = [f.get("path", "") for f in files_list if isinstance(f, dict)][:20]
                        repo_structure = f"Key files in web-store: {', '.join(file_names[:10])}"
        
        # Build comprehensive prompt matching CrewAI format
        prompt_parts = [
            "You are a Senior Technical Lead and Requirements Architect.",
            "Analyze the Jira issue and extract requirements, then produce a comprehensive implementation specification.",
            "",
            "=== JIRA ISSUE DATA ===",
            f"Issue Key: {issue_key}",
            f"Title: {issue_summary}",
            f"Status: {issue_status}",
            f"Priority: {issue_priority}",
            f"Assignee: {issue_assignee}",
            f"Reporter: {issue_reporter}",
            f"Labels: {', '.join(issue_labels) if issue_labels else 'None specified'}",
            "",
            "Project Information:",
            *repo_context_parts,
            "",
            f"Acceptance Criteria:",
            acceptance_criteria if acceptance_criteria else "See description below",
            "",
            f"Description:",
            issue_description,
            "",
            "=== REPOSITORY CONTEXT ===",
        ]
        
        if repo_structure:
            prompt_parts.append(repo_structure)
        
        if repo_files:
            import json
            prompt_parts.append("\nRepository file structure:")
            prompt_parts.append(json.dumps(repo_files, indent=2)[:2000])  # Limit size
        
        prompt_parts.extend([
            "",
            "=== YOUR TASK ===",
            "",
            "You are a Senior Technical Lead and Requirements Architect. Your goal is to analyze Jira tasks and create comprehensive implementation plans.",
            "",
            "Produce output in EXACTLY this format (matching CrewAI output format):",
            "",
            "# Issue Summary",
            "",
            "**Issue Key:** " + issue_key,
            "**Title:** " + issue_summary,
            "**Status:** " + issue_status,
            "**Priority:** " + issue_priority,
            "**Assignee:** " + issue_assignee,
            "**Reporter:** " + issue_reporter,
            "**Labels:** " + (', '.join(issue_labels) if issue_labels else 'None specified'),
            "**Linked Repository:** " + (issue_url if issue_url else 'Not specified'),
            "",
            "**Project Information:**",
            f"- Project Key: {project_key if project_key else 'N/A'}",
            f"- Bitbucket Workspace: {workspace if workspace else 'N/A'}",
            f"- Repository: {repo_slug if repo_slug else 'N/A'}",
            "",
            "**Acceptance Criteria:**",
            "- " + acceptance_criteria.replace('\\n', '\\n- ') if acceptance_criteria else "See description",
            "",
            "**Description:**",
            issue_description,
            "",
            "---",
            "",
            "# Implementation Specification",
            "",
            "## Deliverables",
            "",
            "List WHAT needs to be created or modified (not HOW). Be specific about the concrete outputs.",
            "",
            "## Required Functionality",
            "",
            "Describe the specific behaviors, operations, or capabilities that must be implemented. Focus on functional requirements.",
            "",
            "## Input/Output Specifications",
            "",
            "**Inputs:**",
            "List all data inputs, user interactions, or triggers required.",
            "",
            "**Outputs:**",
            "List all expected outputs, responses, or results.",
            "",
            "**Data Requirements:**",
            "Describe the data structures, formats, or data flow requirements.",
            "",
            "## Constraints & Validations",
            "",
            "List all rules, limitations, validation requirements, or constraints that must be followed.",
            "",
            "## Integration Requirements",
            "",
            "Describe external systems, APIs, existing components, or integration points that must be considered.",
            "",
            "## Repository Context",
            "",
            "**Project Type:** [Identify from repository structure - e.g., Frontend Web Application, Backend Service, etc.]",
            "",
            "**Technology Stack Indicators:**",
            "[List technologies identified from repository files - e.g., Next.js, TypeScript, React, etc.]",
            "",
            "**Project Structure:**",
            "[Describe the directory structure and organization]",
            "",
            "**Key Files Present:**",
            "[List important configuration and source files]",
            "",
            "[Provide additional context about the project architecture and patterns]",
            "",
            "CRITICAL INSTRUCTIONS:",
            "- Extract acceptance criteria from the description and list them as bullet points",
            "- Be comprehensive and detailed - this specification will be used by developers",
            "- Focus on WHAT needs to be built, NOT HOW to implement it",
            "- Include all relevant details from the Jira issue",
            "- Analyze the repository structure to provide accurate technology stack and project context",
            "- Do NOT include code examples or implementation details",
        ])
        
        prompt = "\n".join(prompt_parts)
        
        # Call LLM
        from langchain_core.messages import HumanMessage, AIMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Extract response content properly
        if hasattr(response, "content"):
            response_content = response.content
        elif isinstance(response, (str, dict)):
            response_content = str(response)
        else:
            response_content = str(response)
        
        state["final_output"] = response_content
        
        # Add the AI response to messages for proper state management
        if "messages" not in state:
            state["messages"] = []
        state["messages"] = list(state["messages"]) + [AIMessage(content=response_content)]
        
        logger.info("✅ Synthesized final output")
    except Exception as e:
        logger.error(f"Error synthesizing output: {e}")
        import traceback
        logger.error(traceback.format_exc())
        state["final_output"] = f"Error: {str(e)}"
    return state


def build_graph(checkpointer=None):
    """Build the LangGraph state machine
    
    Args:
        checkpointer: Optional checkpointer for state persistence (e.g., KAgentCheckpointer)
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes (mapping from CrewAI tasks)
    workflow.add_node("process_input", process_input)
    workflow.add_node("fetch_jira", fetch_jira_issue)
    workflow.add_node("extract_repo", extract_repo_info)
    workflow.add_node("list_repos", list_repositories)
    workflow.add_node("list_files", list_repo_files)
    workflow.add_node("synthesize", synthesize_output)
    
    # Define edges (sequential flow like CrewAI Process.sequential)
    workflow.set_entry_point("process_input")
    workflow.add_edge("process_input", "fetch_jira")
    workflow.add_edge("fetch_jira", "extract_repo")
    workflow.add_edge("extract_repo", "list_repos")
    workflow.add_edge("list_repos", "list_files")
    workflow.add_edge("list_files", "synthesize")
    workflow.add_edge("synthesize", END)
    
    # Compile with checkpointer if provided (for KAgent integration)
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()


if __name__ == "__main__":
    # Test graph creation
    graph = build_graph()
    print("✅ LangGraph created successfully")

