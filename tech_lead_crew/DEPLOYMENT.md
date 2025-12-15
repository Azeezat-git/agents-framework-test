# Deployment Guide

## Where to Configure OTEL Endpoint

When you're ready to send telemetry to your company's OTEL endpoint, you have **two options**:

### Option 1: KAgent BYO Manifest (Recommended)

Add the OTEL endpoint to your KAgent BYO manifest file. See `kagent-byo-manifest.yaml.example` for a complete template.

**Key section to update:**
```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "https://your.company.otel.collector:4318"  # ⬅️ PUT YOUR ENDPOINT HERE
  - name: OTEL_EXPORTER_OTLP_HEADERS
    value: "Authorization=Bearer YOUR_TOKEN"  # If auth required
```

### Option 2: Kubernetes Secret (For Sensitive Values)

If your OTEL endpoint requires authentication, store it in a Kubernetes Secret:

```bash
# Create secret
kubectl create secret generic otel-credentials \
  --from-literal=endpoint=https://your.company.otel.collector:4318 \
  --from-literal=headers="Authorization=Bearer YOUR_TOKEN" \
  -n your-namespace
```

Then reference it in your manifest:
```yaml
envFrom:
  - secretRef:
      name: otel-credentials
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    valueFrom:
      secretKeyRef:
        name: otel-credentials
        key: endpoint
  - name: OTEL_EXPORTER_OTLP_HEADERS
    valueFrom:
      secretKeyRef:
        name: otel-credentials
        key: headers
```

## Quick Setup Steps

1. **Get your OTEL endpoint URL** from your company's observability team
   - Format: `https://collector.company.com:4318` (gRPC) or `https://collector.company.com:4317` (HTTP)
   - Ask if authentication is required

2. **Update the manifest:**
   ```yaml
   - name: OTEL_EXPORTER_OTLP_ENDPOINT
     value: "https://your-actual-endpoint:4318"  # Replace this
   ```

3. **Apply the manifest:**
   ```bash
   kubectl apply -f kagent-byo-manifest.yaml
   ```

4. **Verify it's working:**
   - Check pod logs: `kubectl logs <pod-name>`
   - Look for: "✅ OTEL instrumentation enabled"
   - Check your OTEL platform for traces from service `tech-lead-crew`

## Environment Variables Reference

### Required for OTEL
- `OTEL_EXPORTER_OTLP_ENDPOINT` - Your OTEL collector endpoint
- `OTEL_SERVICE_NAME` - Service name (default: `tech-lead-crew`)

### Optional for OTEL
- `OTEL_EXPORTER_OTLP_HEADERS` - Authentication headers if needed
- `OTEL_TRACES_EXPORTER` - Set to `otlp` (default: `otlp` if endpoint set)
- `OTEL_LOGS_EXPORTER` - Set to `otlp` to export logs
- `OTEL_METRICS_EXPORTER` - Set to `otlp` to export metrics
- `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` - Set to `true` for auto log export

### CrewAI Specific
- `CREWAI_TRACING_ENABLED` - Set to `true` to enable tracing
- `CREWAI_LOG_LEVEL` - Logging level (`INFO`, `DEBUG`, etc.)

## Testing Locally First

Before deploying, test locally with your endpoint:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your.company.collector:4318
export OTEL_SERVICE_NAME=tech-lead-crew
export OTEL_TRACES_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export CREWAI_TRACING_ENABLED=true

python test_local.py
```

Then check your OTEL platform to verify traces are arriving.

## Troubleshooting

### Not seeing traces in OTEL?

1. **Check pod logs:**
   ```bash
   kubectl logs <pod-name> | grep OTEL
   ```

2. **Verify environment variables:**
   ```bash
   kubectl exec <pod-name> -- env | grep OTEL
   ```

3. **Check network connectivity:**
   ```bash
   kubectl exec <pod-name> -- curl -v https://your.otel.endpoint:4318
   ```

4. **Verify authentication:**
   - Check if headers are correct
   - Verify token hasn't expired

### Still not working?

The code in `main.py` automatically sets up OTEL when environment variables are detected. If it's not working:
- Check that environment variables are actually set in the pod
- Verify the OTEL endpoint is reachable from the cluster
- Check for errors in pod logs


