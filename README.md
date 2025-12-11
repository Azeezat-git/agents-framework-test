# Agents Framework Test

This repository contains multiple agent implementations for testing and development purposes.

## Repository Structure

```
for-tech-crew/
├── tech_lead_crew/          # CrewAI-based Tech Lead agent
│   ├── src/
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
└── README.md                # This file
```

## Prerequisites

Before running any agent, ensure you have:

1. **Python 3.13+** installed
2. **kubectl** configured and connected to your cluster
3. **Port-forwarding** set up for required services (see below)
4. **SSM Session Manager** access (if running from local machine to EC2)

## Tech Lead Crew

A CrewAI-based agent that analyzes Jira issues and Bitbucket repositories to generate implementation plans.

### Setup

1. **Navigate to the directory:**
   ```bash
   cd tech_lead_crew
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3.13 -m venv venv313
   source venv313/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .
   ```

### Port-Forwarding Setup

Before running the agent, you need to set up port-forwarding for the required services:

#### Option 1: Direct kubectl port-forward (if you have cluster access)

```bash
# Jira MCP Server
kubectl -n core-kagent port-forward svc/jira-mcp 3001:3001 --address 0.0.0.0 &

# Bitbucket MCP Server
kubectl -n core-kagent port-forward svc/bitbucket-mcp 3000:3000 --address 0.0.0.0 &

# Agent Gateway
kubectl port-forward -n core-gloogateway svc/agentgateway-enterprise 8080:8080 --address 0.0.0.0 &
```

#### Option 2: SSM Port-Forwarding (if accessing via EC2)

If you're running from a local machine and need to tunnel through EC2:

```bash
# Jira MCP (port 3001)
aws ssm start-session \
  --target i-0274545f5d70fb4af \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3001"],"localPortNumber":["3001"]}' \
  --profile tlz_server_admin-187509843811 \
  --region eu-west-1 &

# Bitbucket MCP (port 3000)
aws ssm start-session \
  --target i-0274545f5d70fb4af \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3000"],"localPortNumber":["3000"]}' \
  --profile tlz_server_admin-187509843811 \
  --region eu-west-1 &

# Agent Gateway (port 8080)
aws ssm start-session \
  --target i-0274545f5d70fb4af \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}' \
  --profile tlz_server_admin-187509843811 \
  --region eu-west-1 &
```

**Note:** Replace `i-0274545f5d70fb4af` with your actual EC2 instance ID if different.

### Running Locally

1. **Set environment variables:**
   ```bash
   export PYTHON_DOTENV_IGNORE=1
   export FASTMCP_DOTENV=0
   export JIRA_MCP_URL=http://localhost:3001/mcp
   export BITBUCKET_MCP_URL=http://localhost:3000/mcp
   export GATEWAY_BASE_URL=http://localhost:8080/llm/bedrock/default
   export GATEWAY_API_KEY="irsa-placeholder-key"
   
   # Optional: Enable observability
   export CREWAI_TRACING_ENABLED=true
   export CREWAI_LOGGING_ENABLED=true
   export CREWAI_METRICS_ENABLED=true
   ```

2. **Run the test script:**
   ```bash
   python test_local.py
   ```

   Or run with a specific Jira issue:
   ```bash
   python test_local.py
   # Edit test_local.py to change the issue key, or modify the script to accept CLI args
   ```

### Environment Variables Explained

- **`JIRA_MCP_URL`**: URL for the Jira MCP server (default: `http://localhost:3001/mcp`)
- **`BITBUCKET_MCP_URL`**: URL for the Bitbucket MCP server (default: `http://localhost:3000/mcp`)
- **`GATEWAY_BASE_URL`**: Agent Gateway endpoint for LLM access (default: `http://localhost:8080/llm/bedrock/default`)
- **`GATEWAY_API_KEY`**: API key for Agent Gateway (use `"irsa-placeholder-key"` for IRSA-authenticated gateways)
- **`CREWAI_TRACING_ENABLED`**: Enable tracing to CrewAI AMP dashboard (default: `false`)
- **`CREWAI_LOGGING_ENABLED`**: Enable file logging (default: `false`)
- **`CREWAI_METRICS_ENABLED`**: Enable metrics collection (default: `false`)

### Output

After execution, you'll get:

1. **Console Output**: The implementation plan and issue summary
2. **Trace URL** (if tracing enabled): Link to view detailed execution traces in CrewAI AMP dashboard
3. **Logs File** (if logging enabled): `logs.txt` with execution logs
4. **Metrics** (if metrics enabled): Accessible via `crew.usage_metrics` in code

### Example Output

```
✅ Trace batch finalized with session ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

🔗 View here: https://app.crewai.com/crewai_plus/ephemeral_trace_batches/...
🔑 Access Code: TRACE-xxxxxxxx
```

### Troubleshooting

1. **Connection refused errors**: Ensure port-forwarding is active and ports are correct
2. **401 Unauthorized**: Check that `GATEWAY_API_KEY` is set (even if using IRSA)
3. **MCP connection failures**: Verify MCP server URLs and that services are running in the cluster
4. **No trace URL**: Ensure `CREWAI_TRACING_ENABLED=true` and you're logged in with `crewai login`

### Authentication

For CrewAI tracing, authenticate with:
```bash
crewai login
```

This will open a browser to authenticate your local environment with CrewAI AMP.

## Future Agents

Additional agent implementations can be added to this repository:
- `tech-lead-langgraph/` - LangGraph-based implementation
- Other agent frameworks as needed

Each agent directory should have its own README with specific setup instructions.

