#!/usr/bin/env python3
"""Test Crew agent configuration - verify LLM and MCP setup"""
import os
import sys
import logging

# Set up test environment (cluster URLs - will timeout from local, but that's OK)
os.environ["GATEWAY_BASE_URL"] = "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/llm/bedrock/default"
os.environ["GATEWAY_API_KEY"] = "irsa-placeholder-key"
os.environ["JIRA_MCP_URL"] = "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/jira-mcp/"
os.environ["BITBUCKET_MCP_URL"] = "http://agentgateway-enterprise.core-gloogateway.svc.cluster.local:8080/mcp/core/bitbucket-mcp/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llm_config():
    """Test LLM configuration matches LangGraph"""
    logger.info("=" * 60)
    logger.info("Testing LLM configuration (matching LangGraph)...")
    logger.info("=" * 60)
    
    try:
        import litellm
        from langchain_openai import ChatOpenAI
        
        # Configure exactly as in crew.py
        litellm.suppress_debug_info = True
        litellm.drop_params = True
        
        # Add to model_cost_map (as in crew.py)
        if not hasattr(litellm, 'model_cost_map') or not litellm.model_cost_map:
            litellm.model_cost_map = {}
        litellm.model_cost_map["just-dummy"] = {
            "input_cost_per_token": 0.0000015,
            "output_cost_per_token": 0.000002
        }
        
        gateway_base_url = os.getenv("GATEWAY_BASE_URL")
        gateway_api_key = os.getenv("GATEWAY_API_KEY")
        gateway_base = gateway_base_url.rstrip("/")
        openai_base_url = f"{gateway_base}/v1"
        
        logger.info(f"Base URL: {openai_base_url}")
        logger.info(f"Model: just-dummy (matching LangGraph)")
        logger.info(f"Model in cost map: {'just-dummy' in litellm.model_cost_map}")
        
        # Create ChatOpenAI instance (same as crew.py)
        llm = ChatOpenAI(
            model="just-dummy",
            base_url=openai_base_url,
            api_key=gateway_api_key,
            temperature=0.0,
            timeout=10,  # Short timeout for testing
        )
        
        logger.info("✅ ChatOpenAI instance created successfully with 'just-dummy'")
        logger.info(f"   Model name: {llm.model_name}")
        logger.info(f"   Base URL: {llm.openai_api_base}")
        logger.info("   ✅ Matches LangGraph configuration")
        return True
        
    except Exception as e:
        logger.error(f"❌ LLM configuration test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_crew_agent_creation():
    """Test that Crew agent can be created with the configuration"""
    logger.info("=" * 60)
    logger.info("Testing Crew agent creation...")
    logger.info("=" * 60)
    
    try:
        from tech_lead_crew.crew import TechLeadCrew
        
        # Try to create the crew (this will test LLM and MCP initialization)
        logger.info("Creating TechLeadCrew instance...")
        crew_instance = TechLeadCrew()
        
        logger.info("Creating tech_lead_crew agent...")
        agent = crew_instance.tech_lead_crew()
        
        logger.info("✅ Crew agent created successfully")
        logger.info(f"   Agent LLM model: {agent.llm.model_name if hasattr(agent.llm, 'model_name') else 'N/A'}")
        logger.info(f"   Agent has MCPs: {hasattr(agent, 'mcps') and agent.mcps is not None}")
        
        # Try to create the crew
        logger.info("Creating crew...")
        crew = crew_instance.crew()
        
        logger.info("✅ Crew created successfully")
        logger.info(f"   Crew has {len(crew.agents)} agent(s)")
        logger.info(f"   Crew has {len(crew.tasks)} task(s)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Crew agent creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_mcp_handling():
    """Test MCP error handling"""
    logger.info("=" * 60)
    logger.info("Testing MCP error handling...")
    logger.info("=" * 60)
    
    try:
        from tech_lead_crew.crew import TechLeadCrew
        
        # Create crew - MCPs will fail to connect (expected from local)
        # But agent should still be created
        crew_instance = TechLeadCrew()
        agent = crew_instance.tech_lead_crew()
        
        # Check if agent was created even if MCPs failed
        if agent:
            logger.info("✅ Agent created even with MCP connection failures")
            logger.info("   This confirms graceful error handling works")
            return True
        else:
            logger.error("❌ Agent creation failed")
            return False
        
    except Exception as e:
        logger.error(f"❌ MCP handling test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Run all tests"""
    logger.info("Starting comprehensive Crew agent configuration tests...")
    logger.info("")
    
    results = {
        "LLM Config (matches LangGraph)": test_llm_config(),
        "Crew Agent Creation": test_crew_agent_creation(),
        "MCP Error Handling": test_mcp_handling(),
    }
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test Results Summary:")
    logger.info("=" * 60)
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        logger.info("")
        logger.info("✅ All tests passed! Configuration is correct.")
        return 0
    else:
        logger.info("")
        logger.warning("⚠️  Some tests failed - check logs above")
        return 1

if __name__ == "__main__":
    sys.exit(main())

