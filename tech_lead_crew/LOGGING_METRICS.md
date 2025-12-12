# Logging and Metrics Guide

## Overview

Your CrewAI application can export **three types of telemetry** to your OTEL endpoint:

1. **Traces** - Agent execution flows, task timelines, tool calls
2. **Logs** - Application logs, errors, debug information
3. **Metrics** - Performance metrics, token usage, execution counts

## How to View Each Type

### 1. Traces (Already Working ✅)

**What you get:**
- Agent execution spans
- Task execution timelines
- Tool call traces (Jira/Bitbucket MCP)
- LLM interaction traces

**How to view:**
- **CrewAI Cloud**: Ephemeral URL when `CREWAI_TRACING_ENABLED=true`
- **Your OTEL Platform**: Jaeger, Grafana Tempo, Datadog, etc.
  - Filter by service: `tech-lead-crew`
  - Look for spans with names like: `crew.execute`, `agent.run`, `tool.call`

**Configuration:**
```bash
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.collector:4318
export CREWAI_TRACING_ENABLED=true
```

### 2. Logs

**What you get:**
- Python application logs
- CrewAI execution logs
- Error traces
- Debug information

**How to view:**
- **Local**: `logs.txt` file (when `output_log_file=True` in crew config)
- **OTEL Platform**: Your logging backend (Loki, Elasticsearch, etc.)
  - Filter by service: `tech-lead-crew`
  - Search by log level: INFO, WARNING, ERROR

**Configuration:**
```bash
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.collector:4318
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
export CREWAI_LOG_LEVEL=INFO  # or DEBUG for more detail
```

**Note**: You may need to install:
```bash
pip install opentelemetry-instrumentation-logging
```

### 3. Metrics

**What you get:**
- Token usage (input/output)
- Execution duration
- Task completion counts
- Error rates
- LLM call counts

**How to view:**
- **OTEL Platform**: Prometheus, Grafana, Datadog, etc.
  - Query metrics like: `crewai_tokens_used`, `crewai_execution_duration`
  - Create dashboards for monitoring

**Configuration:**
```bash
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.collector:4318
```

**Note**: CrewAI's `usage_metrics` (accessible via `crew.usage_metrics`) is a Pydantic model that doesn't automatically export to OTEL. The OTEL metrics come from the instrumentation itself.

## Complete Setup Example

For all three telemetry types:

```bash
# OTEL Endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.company.collector:4318
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer YOUR_TOKEN"
export OTEL_SERVICE_NAME=tech-lead-crew

# Enable all three signals
export OTEL_TRACES_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp

# CrewAI specific
export CREWAI_TRACING_ENABLED=true
export CREWAI_LOG_LEVEL=INFO

# Python logging auto-instrumentation
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
```

## What You'll See in Your OTEL Platform

### Traces
- **Service**: `tech-lead-crew`
- **Spans**: 
  - `crew.execute` - Overall crew execution
  - `agent.run` - Agent execution
  - `task.execute` - Task execution
  - `tool.call` - MCP tool calls
  - `llm.call` - LLM interactions

### Logs
- **Service**: `tech-lead-crew`
- **Log Levels**: INFO, WARNING, ERROR
- **Fields**: timestamp, level, message, trace_id, span_id

### Metrics
- **Service**: `tech-lead-crew`
- **Metrics**:
  - `crewai.agent.executions` - Number of agent executions
  - `crewai.task.executions` - Number of task executions
  - `crewai.tool.calls` - Number of tool calls
  - `crewai.llm.calls` - Number of LLM calls
  - `crewai.tokens.input` - Input tokens used
  - `crewai.tokens.output` - Output tokens used

## Local Logs (logs.txt)

Even with OTEL, CrewAI still creates `logs.txt` locally when `output_log_file=True`:

```python
Crew(
    ...
    output_log_file=True,  # Creates logs.txt
)
```

This is useful for:
- Local debugging
- Quick log inspection
- Development

## Platform Logs (Kubernetes)

If deployed in Kubernetes, you'll also see:
- **Pod logs**: `kubectl logs <pod-name>`
- **Container logs**: Standard stdout/stderr
- **Platform OTEL**: If your apps repo has OTEL configured, these logs may also go there

## Troubleshooting

### Not seeing logs in OTEL?

1. **Check environment variables:**
   ```bash
   echo $OTEL_LOGS_EXPORTER
   echo $OTEL_EXPORTER_OTLP_ENDPOINT
   ```

2. **Verify package is installed:**
   ```bash
   pip list | grep opentelemetry-instrumentation-logging
   ```

3. **Check application logs:**
   - Look for "✅ OTEL logging export enabled" in startup logs
   - Check for errors in pod logs

### Not seeing metrics in OTEL?

1. **Check environment variables:**
   ```bash
   echo $OTEL_METRICS_EXPORTER
   ```

2. **Verify OTEL collector accepts metrics:**
   - Check collector configuration
   - Verify endpoint supports metrics export

3. **Check application logs:**
   - Look for "✅ OTEL metrics export enabled" in startup logs

## Summary

| Telemetry Type | Local View | OTEL View | Auto-Export? |
|---------------|------------|-----------|--------------|
| **Traces** | CrewAI Cloud URL | OTEL Platform | ✅ Yes (with instrumentation) |
| **Logs** | `logs.txt` | OTEL Platform | ⚠️ Needs `OTEL_LOGS_EXPORTER=otlp` |
| **Metrics** | `crew.usage_metrics` (code) | OTEL Platform | ⚠️ Needs `OTEL_METRICS_EXPORTER=otlp` |

The code in `main.py` automatically sets up all three when environment variables are configured!

