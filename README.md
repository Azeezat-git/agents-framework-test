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
├── tech_lead_langgraph/     # LangGraph-based Tech Lead agent
│   ├── src/
│   ├── pyproject.toml
│   └── test_local.py
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
   
   # Optional: Enable CrewAI Cloud tracing (creates ephemeral URL for quick viewing)
   export CREWAI_TRACING_ENABLED=true
   export CREWAI_LOG_LEVEL=INFO  # Use DEBUG for detailed LLM prompts/responses
   
   # Optional: Send telemetry to your company's OTEL endpoint
   # (CrewAI automatically uses opentelemetry-instrumentation-crewai when CREWAI_TRACING_ENABLED=true)
   export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.company.collector:4318
   export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer YOUR_TOKEN"  # If auth required
   export OTEL_SERVICE_NAME=tech-lead-crew
   export OTEL_TRACES_EXPORTER=otlp
   export OTEL_LOGS_EXPORTER=otlp
   export OTEL_METRICS_EXPORTER=otlp
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
- **`CREWAI_TRACING_ENABLED`**: Enable tracing (default: `false`)
  - When enabled, automatically activates `opentelemetry-instrumentation-crewai`
  - Creates CrewAI Cloud ephemeral URL for quick viewing
  - Also sends to your OTEL endpoint if `OTEL_EXPORTER_OTLP_ENDPOINT` is set
- **`CREWAI_LOG_LEVEL`**: Logging level (`INFO`, `DEBUG`, etc.)
- **`OTEL_EXPORTER_OTLP_ENDPOINT`**: Your company's OTEL collector endpoint (e.g., `https://collector.company.com:4318`)
- **`OTEL_EXPORTER_OTLP_HEADERS`**: Authentication headers if required (e.g., `"Authorization=Bearer TOKEN"`)
- **`OTEL_SERVICE_NAME`**: Service name for filtering in your observability platform
- **`OTEL_TRACES_EXPORTER`**: Set to `otlp` to export traces
- **`OTEL_LOGS_EXPORTER`**: Set to `otlp` to export logs
- **`OTEL_METRICS_EXPORTER`**: Set to `otlp` to export metrics

### Output

After execution, you'll get:

1. **Console Output**: The implementation plan and issue summary
2. **CrewAI Cloud Trace URL** (if `CREWAI_TRACING_ENABLED=true`): Ephemeral URL for quick viewing in CrewAI AMP dashboard
3. **OTEL Telemetry** (if `OTEL_EXPORTER_OTLP_ENDPOINT` is set): Traces, logs, and metrics sent to your company's OTEL endpoint
4. **Logs File** (if `output_log_file=True` in crew config): `logs.txt` with execution logs
5. **Metrics** (accessible via `crew.usage_metrics` in code): Usage metrics for LLM calls, tokens, etc.

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

### Telemetry and Observability

**CrewAI Telemetry:**
- **Focus**: Traces, Logs, and Metrics
- **Automatic**: When `CREWAI_TRACING_ENABLED=true`, CrewAI automatically uses the installed `opentelemetry-instrumentation-crewai` package
- **No Code Changes**: Just set environment variables - no imports or SDK calls needed

**Two Possible Destinations:**

1. **CrewAI Cloud (Ephemeral URL)**
   - Quick debugging and visualization
   - URL appears automatically when `CREWAI_TRACING_ENABLED=true`
   - Authenticate with: `crewai login`

2. **Your Company's OTEL Endpoint** (Recommended for Production)
   - Full control over telemetry destination
   - Traces, logs, and metrics sent to your infrastructure
   - Set `OTEL_EXPORTER_OTLP_ENDPOINT` and related variables
   - View in your company's observability platform (Jaeger, Grafana, Datadog, etc.)

**Note**: You can have both enabled simultaneously. The CrewAI Cloud URL is a convenience feature, while your OTEL configuration builds the production observability pipeline.

**Verification**: After running, check your company's observability platform for traces from service `tech-lead-crew`.

## Tech Lead LangGraph

A LangGraph-based agent that analyzes Jira issues and Bitbucket repositories to generate implementation plans. Uses a deterministic state machine approach for faster execution.

### Setup

1. **Navigate to the directory:**
   ```bash
   cd tech_lead_langgraph
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3.13 -m venv venv_langgraph
   source venv_langgraph/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .
   ```

### Port-Forwarding Setup

Same port-forwarding setup as CrewAI (see [Port-Forwarding Setup](#port-forwarding-setup) above):

- Jira MCP: `localhost:3001`
- Bitbucket MCP: `localhost:3000`
- Agent Gateway: `localhost:8080`

### Running Locally

1. **Set environment variables:**
   ```bash
   export PYTHON_DOTENV_IGNORE=1
   export FASTMCP_DOTENV=0
   export JIRA_MCP_URL=http://localhost:3001/mcp
   export BITBUCKET_MCP_URL=http://localhost:3000/mcp
   export GATEWAY_BASE_URL=http://localhost:8080/llm/bedrock/default
   export GATEWAY_API_KEY="irsa-placeholder-key"
   
   # Optional: Enable LangSmith tracing
   export LANGCHAIN_TRACING_V2=true
   export LANGCHAIN_PROJECT=tech-lead-langgraph
   export LANGCHAIN_API_KEY=your-api-key  # Optional, for cloud tracing
   
   # Optional: Send telemetry to your company's OTEL endpoint
   export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.company.collector:4318
   export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer YOUR_TOKEN"  # If auth required
   export OTEL_SERVICE_NAME=tech-lead-langgraph
   export OTEL_TRACES_EXPORTER=otlp
   export OTEL_LOGS_EXPORTER=otlp
   export OTEL_METRICS_EXPORTER=otlp
   ```

2. **Run the test script:**
   ```bash
   python test_local.py
   ```

   The script will:
   - Fetch the Jira issue using MCP tools
   - Extract repository information
   - List repositories and files
   - Generate the implementation specification

### Environment Variables Explained

- **`JIRA_MCP_URL`**: URL for the Jira MCP server (default: `http://localhost:3001/mcp`)
- **`BITBUCKET_MCP_URL`**: URL for the Bitbucket MCP server (default: `http://localhost:3000/mcp`)
- **`GATEWAY_BASE_URL`**: Agent Gateway endpoint for LLM access (default: `http://localhost:8080/llm/bedrock/default`)
- **`GATEWAY_API_KEY`**: API key for Agent Gateway (use `"irsa-placeholder-key"` for IRSA-authenticated gateways)
- **`LANGCHAIN_TRACING_V2`**: Enable LangSmith tracing (default: `false`)
  - When enabled, automatically activates LangChain/LangGraph instrumentation
  - Creates LangSmith trace URLs for viewing
  - Also sends to your OTEL endpoint if `OTEL_EXPORTER_OTLP_ENDPOINT` is set
- **`LANGCHAIN_PROJECT`**: Project name for LangSmith (default: `tech-lead-langgraph`)
- **`LANGCHAIN_API_KEY`**: LangSmith API key (optional, for cloud tracing)
- **`OTEL_EXPORTER_OTLP_ENDPOINT`**: Your company's OTEL collector endpoint (e.g., `https://collector.company.com:4318`)
- **`OTEL_EXPORTER_OTLP_HEADERS`**: Authentication headers if required (e.g., `"Authorization=Bearer TOKEN"`)
- **`OTEL_SERVICE_NAME`**: Service name for filtering in your observability platform
- **`OTEL_TRACES_EXPORTER`**: Set to `otlp` to export traces
- **`OTEL_LOGS_EXPORTER`**: Set to `otlp` to export logs
- **`OTEL_METRICS_EXPORTER`**: Set to `otlp` to export metrics

### Output

After execution, you'll get:

1. **Console Output**: The implementation plan and issue summary
2. **LangSmith Trace URL** (if `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` is set): URL for viewing in LangSmith dashboard
3. **OTEL Telemetry** (if `OTEL_EXPORTER_OTLP_ENDPOINT` is set): Traces, logs, and metrics sent to your company's OTEL endpoint
4. **State Summary**: Information about what was fetched (Jira issue, repositories, files)

### Key Differences from CrewAI

- **Faster Execution**: LangGraph uses a deterministic state machine, resulting in fewer LLM calls (~1-2 vs 5+)
- **Explicit Control Flow**: Graph-based execution with explicit nodes and edges
- **State-Driven**: State determines the next step, not agent reasoning
- **Same Functionality**: Both agents produce the same output format

### Troubleshooting

1. **Connection refused errors**: Ensure port-forwarding is active and ports are correct
2. **401 Unauthorized**: Check that `GATEWAY_API_KEY` is set (even if using IRSA)
3. **MCP connection failures**: Verify MCP server URLs and that services are running in the cluster
4. **No trace URL**: Ensure `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` is set for cloud tracing

### Telemetry and Observability

**LangGraph Telemetry:**
- **Focus**: Traces, Logs, and Metrics
- **Automatic**: When `LANGCHAIN_TRACING_V2=true`, LangGraph automatically uses the installed `opentelemetry-instrumentation-langchain` package
- **No Code Changes**: Just set environment variables - no imports or SDK calls needed

**Two Possible Destinations:**

1. **LangSmith** (if API key provided)
   - Cloud-based tracing and visualization
   - URL appears automatically when `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` is set
   - View at: https://smith.langchain.com

2. **Your Company's OTEL Endpoint** (Recommended for Production)
   - Full control over telemetry destination
   - Traces, logs, and metrics sent to your infrastructure
   - Set `OTEL_EXPORTER_OTLP_ENDPOINT` and related variables
   - View in your company's observability platform (Jaeger, Grafana, Datadog, etc.)

**Note**: You can have both enabled simultaneously. LangSmith provides cloud-based debugging, while your OTEL configuration builds the production observability pipeline.

**Verification**: After running, check your company's observability platform for traces from service `tech-lead-langgraph`.

## Framework Comparison

| Feature | CrewAI | LangGraph |
|---------|--------|-----------|
| **Execution Model** | Agent reasoning loop | Deterministic state machine |
| **LLM Calls** | 5+ (agent decides flow) | 1-2 (explicit flow) |
| **Speed** | Slower (~180-230s) | Faster (~30-60s) |
| **Flexibility** | High (agents adapt) | Medium (explicit flow) |
| **Use Case** | Complex multi-agent tasks | Deterministic workflows |
| **API Style** | Agent/Task-based | Graph API (StateGraph) |

Both frameworks use the same:
- Bedrock model (via agent gateway)
- MCP servers (Jira, Bitbucket)
- OTEL endpoint (for observability)
- Output format (implementation specifications)



