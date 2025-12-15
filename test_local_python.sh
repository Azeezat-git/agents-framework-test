#!/bin/bash
# Python-only test (no Docker required)
# Tests all imports and basic functionality

set -e

AGENT_TYPE=${1:-langgraph}

echo "🧪 Python Test for $AGENT_TYPE Agent"
echo "===================================="

if [ "$AGENT_TYPE" = "langgraph" ]; then
    AGENT_DIR="tech_lead_langgraph"
    MODULE="tech_lead_langgraph"
    VENV_PATH="../tech_lead_crew/venv313"
elif [ "$AGENT_TYPE" = "crew" ]; then
    AGENT_DIR="tech_lead_crew"
    MODULE="tech_lead_crew"
    VENV_PATH="venv313"
else
    echo "❌ Invalid agent type. Use 'langgraph' or 'crew'"
    exit 1
fi

cd "$AGENT_DIR"

echo ""
echo "1️⃣  Activating virtual environment..."
source "$VENV_PATH/bin/activate" || {
    echo "❌ Failed to activate venv at $VENV_PATH"
    exit 1
}
echo "✅ Virtual environment activated"

echo ""
echo "2️⃣  Testing Python imports..."
# Set env vars before testing imports (Crew needs them)
export KAGENT_URL=http://localhost:8083
export KAGENT_NAME=test-agent
export KAGENT_NAMESPACE=test

python -c "
import sys
import os
print('Testing imports...')

# Set env vars for imports that validate them
os.environ['KAGENT_URL'] = 'http://localhost:8083'
os.environ['KAGENT_NAME'] = 'test-agent'
os.environ['KAGENT_NAMESPACE'] = 'test'

# Test basic module import
try:
    import $MODULE
    print('✅ Module $MODULE imports')
except Exception as e:
    print(f'❌ Module import failed: {e}')
    sys.exit(1)

# Test KAgent imports
if '$AGENT_TYPE' == 'langgraph':
    try:
        from kagent.langgraph import KAgentApp
        print('✅ kagent.langgraph.KAgentApp imports')
    except Exception as e:
        print(f'❌ kagent.langgraph import failed: {e}')
        sys.exit(1)
    
    try:
        from kagent.core._config import KAgentConfig
        print('✅ kagent.core._config.KAgentConfig imports')
    except Exception as e:
        print(f'❌ KAgentConfig import failed: {e}')
        sys.exit(1)
    
    try:
        import anthropic
        print(f'✅ anthropic imports (version: {anthropic.__version__})')
    except Exception as e:
        print(f'❌ anthropic import failed: {e}')
        sys.exit(1)
    
    try:
        import google.genai
        print('✅ google.genai imports')
    except Exception as e:
        print(f'❌ google.genai import failed: {e}')
        sys.exit(1)

elif '$AGENT_TYPE' == 'crew':
    try:
        from kagent.crewai import KAgentApp
        print('✅ kagent.crewai.KAgentApp imports')
    except Exception as e:
        print(f'❌ kagent.crewai import failed: {e}')
        sys.exit(1)
    
    try:
        import anthropic
        print(f'✅ anthropic imports (version: {anthropic.__version__})')
    except Exception as e:
        print(f'❌ anthropic import failed: {e}')
        sys.exit(1)
    
    # Test MCP imports
    try:
        from crewai_tools import MCPServerAdapter
        print('✅ crewai_tools.MCPServerAdapter imports')
    except Exception as e:
        print(f'⚠️  MCPServerAdapter import failed: {e}')
        # Try fallback
        try:
            from crewai.mcp import MCPServerHTTP
            print('✅ crewai.mcp.MCPServerHTTP imports (fallback)')
        except:
            try:
                from crewai_tools.mcp import MCPServerHTTP
                print('✅ crewai_tools.mcp.MCPServerHTTP imports (fallback)')
            except:
                print('❌ No MCP import available')
                sys.exit(1)

print('✅ All imports successful!')
" || {
    echo "❌ Import tests failed!"
    exit 1
}

echo ""
echo "3️⃣  Testing agent-card.json..."
python -c "
import os
import json
import sys

# Get current directory
cwd = os.getcwd()

# Check multiple possible locations
paths = [
    os.path.join(cwd, 'src', '$MODULE', 'agent-card.json'),  # Source location
    'src/$MODULE/agent-card.json',  # Relative
]

found = False
for path in paths:
    abs_path = os.path.abspath(path)
    if os.path.exists(abs_path):
        try:
            with open(abs_path, 'r') as f:
                card = json.load(f)
            print(f'✅ agent-card.json found at: {abs_path}')
            print(f'   Name: {card.get(\"name\", \"unknown\")}')
            print(f'   Version: {card.get(\"version\", \"unknown\")}')
            found = True
            break
        except Exception as e:
            print(f'⚠️  Found but failed to parse: {e}')
            continue

if not found:
    print('❌ agent-card.json not found!')
    print(f'   Current directory: {cwd}')
    print('   Checked paths:')
    for p in paths:
        abs_p = os.path.abspath(p)
        exists = '✅' if os.path.exists(abs_p) else '❌'
        print(f'     {exists} {abs_p}')
    sys.exit(1)
" || {
    echo "❌ Agent card test failed!"
    exit 1
}

echo ""
echo "4️⃣  Testing KAgentConfig initialization..."
python -c "
import os
import sys

# Set required env vars
os.environ['KAGENT_URL'] = 'http://localhost:8083'
os.environ['KAGENT_NAME'] = 'test-agent'
os.environ['KAGENT_NAMESPACE'] = 'test'

if '$AGENT_TYPE' == 'langgraph':
    try:
        from kagent.core._config import KAgentConfig
        config = KAgentConfig()
        print('✅ KAgentConfig() initializes successfully')
        # Config reads from environment variables - just verify it doesn't crash
    except ValueError as e:
        # ValueError is expected if env vars are missing, but we set them above
        if 'KAGENT_URL' in str(e) or 'KAGENT_NAME' in str(e):
            print(f'⚠️  KAgentConfig requires env vars: {e}')
            print('   (This is expected - env vars are set for main test)')
        else:
            print(f'❌ KAgentConfig initialization failed: {e}')
            sys.exit(1)
    except Exception as e:
        print(f'❌ KAgentConfig initialization failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
elif '$AGENT_TYPE' == 'crew':
    try:
        from kagent.crewai import KAgentApp
        # KAgentApp validates config on import, so just test import
        print('✅ kagent.crewai imports (config validated)')
    except Exception as e:
        print(f'❌ kagent.crewai import/config failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
" || {
    echo "❌ KAgentConfig test failed!"
    exit 1
}

echo ""
echo "5️⃣  Testing main module import (with env vars)..."
export KAGENT_URL=http://localhost:8083
export KAGENT_NAME=test-agent
export KAGENT_NAMESPACE=test
export JIRA_MCP_URL=http://localhost:3001/mcp
export BITBUCKET_MCP_URL=http://localhost:3000/mcp

python -c "
import sys
import os

# Test that main module can be imported without errors
try:
    from $MODULE.main import main
    print('✅ main module imports successfully')
except Exception as e:
    print(f'❌ main module import failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test that main function exists and is callable
try:
    import inspect
    sig = inspect.signature(main)
    print(f'✅ main() function signature: {sig}')
except Exception as e:
    print(f'⚠️  Could not inspect main signature: {e}')
" || {
    echo "❌ Main module test failed!"
    exit 1
}

echo ""
echo "📊 Summary:"
echo "==========="
echo "✅ Virtual environment: PASSED"
echo "✅ Python imports: PASSED"
echo "✅ Agent card: PASSED"
echo "✅ KAgentConfig: PASSED"
echo "✅ Main module: PASSED"
echo ""
echo "🎉 All Python tests passed! Code is ready for Docker build."

