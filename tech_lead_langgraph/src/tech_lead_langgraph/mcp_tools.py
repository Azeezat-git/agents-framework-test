"""
MCP tool wrappers for LangGraph.
Converts MCP tools to LangChain-compatible tools.
"""
import os
import asyncio
from typing import Any, Dict
from langchain_core.tools import BaseTool
from fastmcp.client import Client
import logging

logger = logging.getLogger(__name__)


class MCPLangChainTool(BaseTool):
    """LangChain tool wrapper for MCP tools"""
    
    mcp_url: str
    mcp_tool_name: str
    
    def __init__(self, mcp_url: str, mcp_tool_name: str, name: str, description: str, **kwargs):
        super().__init__(name=name, description=description, mcp_url=mcp_url, mcp_tool_name=mcp_tool_name, **kwargs)
    
    def _run(self, **kwargs: Any) -> str:
        """Synchronous wrapper for async MCP call"""
        return asyncio.run(self._arun(**kwargs))
    
    async def _arun(self, **kwargs: Any) -> str:
        """Async MCP tool call"""
        try:
            # Create new client for each call (fastmcp handles connection pooling)
            async with Client(self.mcp_url) as client:
                result = await client.call_tool(self.mcp_tool_name, kwargs)
                
                # Handle CallToolResult object (from fastmcp)
                # It has a 'content' field with TextContent objects
                if hasattr(result, 'content'):
                    # Extract text from content list
                    content_parts = []
                    for item in result.content:
                        if hasattr(item, 'text'):
                            content_parts.append(item.text)
                        elif isinstance(item, str):
                            content_parts.append(item)
                        else:
                            content_parts.append(str(item))
                    result_text = ''.join(content_parts)
                    
                    # Try to parse as JSON if it looks like JSON
                    import json
                    if result_text.strip().startswith('{') or result_text.strip().startswith('['):
                        try:
                            parsed = json.loads(result_text)
                            return json.dumps(parsed, indent=2)
                        except (json.JSONDecodeError, ValueError):
                            return result_text
                    return result_text
                
                # Handle dict result
                import json
                if isinstance(result, dict):
                    return json.dumps(result, indent=2)
                elif isinstance(result, str):
                    # Try to parse if it's a JSON string, otherwise return as-is
                    try:
                        parsed = json.loads(result)
                        return json.dumps(parsed, indent=2)
                    except (json.JSONDecodeError, ValueError):
                        return result
                else:
                    return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error calling MCP tool {self.mcp_tool_name}: {e}")
            raise


def create_jira_tools() -> list[BaseTool]:
    """Create Jira MCP tools as LangChain tools"""
    jira_mcp_url = os.getenv("JIRA_MCP_URL", "http://localhost:3001/mcp")
    
    return [
        MCPLangChainTool(
            mcp_url=jira_mcp_url,
            mcp_tool_name="jira_get_issue",
            name="jira_get_issue",
            description="Retrieve a Jira issue by key (e.g., 'TECBAC-209')",
        ),
        # Add other Jira tools as needed
    ]


def create_bitbucket_tools() -> list[BaseTool]:
    """Create Bitbucket MCP tools as LangChain tools"""
    bitbucket_mcp_url = os.getenv("BITBUCKET_MCP_URL", "http://localhost:3000/mcp")
    
    return [
        MCPLangChainTool(
            mcp_url=bitbucket_mcp_url,
            mcp_tool_name="listRepositories",
            name="listRepositories",
            description="List repositories in a Bitbucket workspace",
        ),
        MCPLangChainTool(
            mcp_url=bitbucket_mcp_url,
            mcp_tool_name="listRepositoryFiles",
            name="listRepositoryFiles",
            description="List files in a Bitbucket repository",
        ),
        # Add other Bitbucket tools as needed
    ]


def get_all_mcp_tools() -> list[BaseTool]:
    """Get all MCP tools as LangChain tools"""
    return create_jira_tools() + create_bitbucket_tools()

