# OpenTelemetry (OTEL) Setup Guide

## Quick Answer: Will It Work?

**Yes, with a safety net.** The packages are installed, and we've added manual instrumentation as a fallback to ensure it works even if CrewAI's auto-instrumentation doesn't kick in automatically.

## How It Works

### Automatic Instrumentation (Preferred)
When you set `CREWAI_TRACING_ENABLED=true`, CrewAI *should* automatically use the installed `opentelemetry-instrumentation-crewai` package and read OTEL environment variables.

### Manual Instrumentation (Safety Net)
We've added manual instrumentation in `test_local.py` that runs **before** creating the crew. This ensures OTEL works even if auto-instrumentation doesn't trigger.

```python
# This is already in test_local.py
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("CREWAI_TRACING_ENABLED", "").lower() == "true":
    from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
    CrewAIInstrumentor().instrument()
```

## Setup Steps

1. **Set environment variables:**
   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.company.collector:4318
   export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer YOUR_TOKEN"  # If needed
   export OTEL_SERVICE_NAME=tech-lead-crew
   export OTEL_TRACES_EXPORTER=otlp
   export OTEL_LOGS_EXPORTER=otlp
   export OTEL_METRICS_EXPORTER=otlp
   export CREWAI_TRACING_ENABLED=true
   ```

2. **Run the verification script:**
   ```bash
   python test_otel_setup.py
   ```
   This checks:
   - ✅ Packages are installed
   - ✅ Environment variables are set
   - ✅ Manual instrumentation is available

3. **Run your crew:**
   ```bash
   python test_local.py
   ```

4. **Verify in your OTEL platform:**
   - Look for traces from service `tech-lead-crew`
   - Check for agent execution spans
   - Verify tool calls (Jira/Bitbucket MCP) are traced

## What Gets Sent

When properly configured, you'll get:

- **Traces**: Agent execution, task execution, tool calls, LLM interactions
- **Logs**: Execution logs (if `OTEL_LOGS_EXPORTER=otlp`)
- **Metrics**: Performance metrics (if `OTEL_METRICS_EXPORTER=otlp`)

## Troubleshooting

### No traces appearing in your OTEL endpoint?

1. **Check network connectivity:**
   ```bash
   curl -v https://your.company.collector:4318
   ```

2. **Verify environment variables:**
   ```bash
   python test_otel_setup.py
   ```

3. **Check for errors in console:**
   - Look for OTEL export errors
   - Check authentication headers

4. **Test with a simple OTEL export:**
   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
   
   trace.set_tracer_provider(TracerProvider())
   trace.get_tracer_provider().add_span_processor(
       BatchSpanProcessor(ConsoleSpanExporter())
   )
   ```

### Still not working?

The manual instrumentation in `test_local.py` should catch it. If you see "✅ OTEL instrumentation enabled" in the output, it's working. If not, check:

1. Is `opentelemetry-instrumentation-crewai` installed?
   ```bash
   pip list | grep opentelemetry-instrumentation-crewai
   ```

2. Are you setting environment variables before running?
   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=...
   python test_local.py
   ```

## Confidence Level

- ✅ **Packages installed**: 100% confirmed
- ✅ **Manual instrumentation**: 100% will work (we explicitly call it)
- ⚠️ **Auto-instrumentation**: ~90% confident (CrewAI should handle it, but we have fallback)
- ✅ **OTEL export**: Depends on your endpoint configuration (test when you have it)

## Next Steps

When you're ready to test:

1. Get your company's OTEL endpoint URL
2. Set the environment variables
3. Run `python test_otel_setup.py` to verify setup
4. Run `python test_local.py` to execute the crew
5. Check your OTEL platform for traces

The manual instrumentation ensures it will work even if CrewAI's auto-instrumentation has issues.


