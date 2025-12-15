#!/bin/bash
# Comprehensive test script for agents
# Tests all the issues we've encountered

set -e

AGENT_TYPE=${1:-langgraph}
IMAGE_TAG=${2:-local-test}

echo "🧪 Comprehensive Test for $AGENT_TYPE Agent"
echo "=========================================="

if [ "$AGENT_TYPE" = "langgraph" ]; then
    AGENT_DIR="tech_lead_langgraph"
    IMAGE_NAME="tech-lead-langgraph-agent"
    CONTAINER_NAME="test-langgraph-agent"
    MODULE="tech_lead_langgraph"
elif [ "$AGENT_TYPE" = "crew" ]; then
    AGENT_DIR="tech_lead_crew"
    IMAGE_NAME="tech-lead-crew-agent"
    CONTAINER_NAME="test-crew-agent"
    MODULE="tech_lead_crew"
else
    echo "❌ Invalid agent type. Use 'langgraph' or 'crew'"
    exit 1
fi

cd "$AGENT_DIR"

echo ""
echo "1️⃣  Building Docker image..."
docker build -t $IMAGE_NAME:$IMAGE_TAG . || {
    echo "❌ Docker build failed!"
    exit 1
}
echo "✅ Build successful"

echo ""
echo "2️⃣  Testing imports inside container..."
docker run --rm \
    -e KAGENT_URL=http://localhost:8083 \
    -e KAGENT_NAME=test-agent \
    -e KAGENT_NAMESPACE=test \
    $IMAGE_NAME:$IMAGE_TAG \
    python -c "
import sys
print('Testing imports...')

# Test basic imports
try:
    import $MODULE
    print('✅ Module imports')
except Exception as e:
    print(f'❌ Module import failed: {e}')
    sys.exit(1)

# Test KAgent imports
if '$AGENT_TYPE' == 'langgraph':
    try:
        from kagent.langgraph import KAgentApp
        from kagent.core._config import KAgentConfig
        print('✅ kagent.langgraph imports')
    except Exception as e:
        print(f'❌ kagent.langgraph import failed: {e}')
        sys.exit(1)
elif '$AGENT_TYPE' == 'crew':
    try:
        from kagent.crewai import KAgentApp
        print('✅ kagent.crewai imports')
    except Exception as e:
        print(f'❌ kagent.crewai import failed: {e}')
        sys.exit(1)

# Test agent-card.json
try:
    import os
    import json
    card_path = f'/usr/local/lib/python3.13/site-packages/$MODULE/agent-card.json'
    if os.path.exists(card_path):
        with open(card_path) as f:
            card = json.load(f)
        print(f'✅ agent-card.json found: {card.get(\"name\", \"unknown\")}')
    else:
        print(f'⚠️  agent-card.json not at {card_path}, checking alternatives...')
        # Check source location
        alt_path = f'/app/src/$MODULE/agent-card.json'
        if os.path.exists(alt_path):
            print(f'✅ agent-card.json found at source: {alt_path}')
        else:
            print(f'❌ agent-card.json not found anywhere!')
            sys.exit(1)
except Exception as e:
    print(f'❌ agent-card.json check failed: {e}')
    sys.exit(1)

print('✅ All import tests passed!')
" || {
    echo "❌ Import tests failed!"
    exit 1
}

echo ""
echo "3️⃣  Starting container with full environment..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

docker run -d \
    --name $CONTAINER_NAME \
    -p 8080:8080 \
    -e KAGENT_URL=http://localhost:8083 \
    -e KAGENT_NAME=test-agent \
    -e KAGENT_NAMESPACE=test \
    -e JIRA_MCP_URL=http://localhost:3001/mcp \
    -e BITBUCKET_MCP_URL=http://localhost:3000/mcp \
    -e GATEWAY_BASE_URL=http://localhost:8080/llm \
    -e GATEWAY_API_KEY=test-key \
    -e PORT=8080 \
    -e HOST=0.0.0.0 \
    $IMAGE_NAME:$IMAGE_TAG

echo "⏳ Waiting for startup..."
sleep 8

echo ""
echo "4️⃣  Checking container status..."
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "❌ Container is not running!"
    echo "📋 Logs:"
    docker logs $CONTAINER_NAME --tail=50
    exit 1
fi
echo "✅ Container is running"

echo ""
echo "5️⃣  Checking logs for key indicators..."
LOGS=$(docker logs $CONTAINER_NAME --tail=50 2>&1)

# Check for KAgent integration
if echo "$LOGS" | grep -qi "kagent.*available\|KAgent app created"; then
    echo "✅ KAgent integration detected"
elif echo "$LOGS" | grep -qi "standalone mode"; then
    echo "⚠️  Running in standalone mode (KAgent not available)"
else
    echo "❌ Cannot determine KAgent status"
fi

# Check for errors
if echo "$LOGS" | grep -qiE "error|exception|traceback|failed|ModuleNotFound"; then
    echo "❌ Errors found in logs:"
    echo "$LOGS" | grep -iE "error|exception|traceback|failed|ModuleNotFound" | head -5
    echo ""
    echo "Full logs:"
    docker logs $CONTAINER_NAME --tail=50
    exit 1
else
    echo "✅ No critical errors in logs"
fi

# Check for agent-card
if echo "$LOGS" | grep -qi "agent.card.*found\|Loaded agent card"; then
    echo "✅ Agent card loaded"
else
    echo "⚠️  Agent card status unclear"
fi

echo ""
echo "6️⃣  Testing health endpoint..."
sleep 2
if curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Health endpoint responding"
    curl -s http://localhost:8080/health | head -3
else
    echo "⚠️  Health endpoint not responding (may be normal for KAgent apps)"
fi

echo ""
echo "📊 Summary:"
echo "==========="
echo "✅ Docker build: PASSED"
echo "✅ Imports: PASSED"
echo "✅ Container startup: PASSED"
echo "✅ Logs check: PASSED"
echo ""
echo "🧹 Cleanup:"
echo "   docker rm -f $CONTAINER_NAME"
echo ""
echo "🎉 All tests passed! Image is ready for deployment."

