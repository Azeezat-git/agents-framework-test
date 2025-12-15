# Local Testing Guide

Before deploying to Kubernetes, test your agents locally. **Start with Python-only tests (no Docker required)**.

## Python-Only Test (Recommended - No Docker)

Fastest way to catch import and dependency issues:

```bash
# Test LangGraph agent
./test_local_python.sh langgraph

# Test Crew agent
./test_local_python.sh crew
```

This tests:
- ✅ All Python imports (kagent, anthropic, google-genai, etc.)
- ✅ Agent card file exists
- ✅ KAgentConfig initialization
- ✅ Main module imports

## Docker Test (Optional)

If you want to test the full Docker image:

```bash
# Test LangGraph agent
./test_docker_local.sh langgraph

# Test Crew agent
./test_docker_local.sh crew
```

## Comprehensive Test

This tests all the issues we've encountered:

```bash
# Test LangGraph agent with full validation
./test_agent_comprehensive.sh langgraph

# Test Crew agent with full validation
./test_agent_comprehensive.sh crew
```

## What the Tests Check

1. ✅ **Docker build** - Image builds successfully
2. ✅ **Imports** - All required modules import correctly
   - `kagent.langgraph` / `kagent.crewai`
   - `KAgentConfig`
   - `anthropic`, `google-genai` (for LangGraph)
   - `MCPServerHTTP` / `MCPServerAdapter` (for Crew)
3. ✅ **Agent card** - `agent-card.json` is found and loaded
4. ✅ **Container startup** - Container runs without crashing
5. ✅ **KAgent integration** - Uses KAgent (not standalone mode)
6. ✅ **No errors** - No import errors, exceptions, or crashes
7. ✅ **Health endpoint** - HTTP endpoint responds (if available)

## Expected Output

### Success:
```
✅ Build successful
✅ Module imports
✅ kagent.langgraph imports
✅ agent-card.json found: tech-lead-langgraph
✅ Container is running
✅ KAgent integration detected
✅ No critical errors in logs
✅ Agent card loaded
🎉 All tests passed! Image is ready for deployment.
```

### Failure Indicators:
- ❌ `ModuleNotFoundError` - Missing dependencies
- ❌ `standalone mode` - KAgent not available
- ❌ `agent-card.json not found` - File not included in image
- ❌ Container crashes - Check logs for errors

## Manual Testing

If you want to test interactively:

```bash
# Build image
cd tech_lead_langgraph  # or tech_lead_crew
docker build -t test-agent:local .

# Run container
docker run -it --rm \
  -p 8080:8080 \
  -e KAGENT_URL=http://localhost:8083 \
  -e KAGENT_NAME=test \
  -e KAGENT_NAMESPACE=test \
  -e JIRA_MCP_URL=http://localhost:3001/mcp \
  -e BITBUCKET_MCP_URL=http://localhost:3000/mcp \
  test-agent:local

# In another terminal, check logs
docker logs <container-id>

# Test health endpoint
curl http://localhost:8080/health
```

## Troubleshooting

### Container exits immediately
- Check logs: `docker logs <container-name>`
- Verify all environment variables are set
- Check for import errors

### KAgent not available
- Verify `anthropic` and `google-genai` are in dependencies (LangGraph)
- Check that `kagent-langgraph` / `kagent-crewai` installed correctly

### Agent card not found
- Verify `agent-card.json` is copied in Dockerfile
- Check file exists in source: `src/tech_lead_*/agent-card.json`

## Before Deploying

1. ✅ Run comprehensive test: `./test_agent_comprehensive.sh <agent-type>`
2. ✅ All tests pass
3. ✅ Commit and push code
4. ✅ Build and push Docker image
5. ✅ Update manifest with new image tag
6. ✅ Deploy to cluster

