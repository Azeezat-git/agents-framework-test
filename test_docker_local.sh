#!/bin/bash
# Local Docker test script for agents
# This simulates the Kubernetes environment locally

set -e

AGENT_TYPE=${1:-langgraph}  # langgraph or crew
IMAGE_TAG=${2:-local-test}

echo "🧪 Testing $AGENT_TYPE agent locally..."

if [ "$AGENT_TYPE" = "langgraph" ]; then
    AGENT_DIR="tech_lead_langgraph"
    IMAGE_NAME="tech-lead-langgraph-agent"
    CONTAINER_NAME="test-langgraph-agent"
elif [ "$AGENT_TYPE" = "crew" ]; then
    AGENT_DIR="tech_lead_crew"
    IMAGE_NAME="tech-lead-crew-agent"
    CONTAINER_NAME="test-crew-agent"
else
    echo "❌ Invalid agent type. Use 'langgraph' or 'crew'"
    exit 1
fi

cd "$AGENT_DIR"

echo "📦 Building Docker image..."
docker build -t $IMAGE_NAME:$IMAGE_TAG .

echo "🚀 Starting container with test environment..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

# Set environment variables similar to Kubernetes
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

echo "⏳ Waiting for container to start..."
sleep 5

echo "📋 Checking container logs..."
docker logs $CONTAINER_NAME --tail=50

echo "🔍 Checking if container is running..."
if docker ps | grep -q $CONTAINER_NAME; then
    echo "✅ Container is running!"
    
    echo "🌐 Testing health endpoint..."
    sleep 2
    curl -s http://localhost:8080/health || echo "⚠️  Health endpoint not available"
    
    echo ""
    echo "📊 Container status:"
    docker ps | grep $CONTAINER_NAME
    
    echo ""
    echo "📝 Recent logs:"
    docker logs $CONTAINER_NAME --tail=20
    
    echo ""
    echo "🧹 To clean up, run:"
    echo "   docker rm -f $CONTAINER_NAME"
else
    echo "❌ Container failed to start. Check logs:"
    docker logs $CONTAINER_NAME --tail=50
    exit 1
fi

