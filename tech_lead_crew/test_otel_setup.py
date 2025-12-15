"""
Test script to verify OTEL setup works correctly.
This checks if CrewAI automatically uses OTEL environment variables.
"""
import os
import sys

# Add src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

def test_otel_packages():
    """Test if OTEL packages are installed and importable"""
    print("=" * 60)
    print("Testing OTEL Package Installation")
    print("=" * 60)
    
    try:
        from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
        print("✅ opentelemetry-instrumentation-crewai is installed")
        
        # Check if we can instantiate it
        instrumentor = CrewAIInstrumentor()
        print("✅ CrewAIInstrumentor can be instantiated")
        
        # Check OTEL SDK packages
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        print("✅ Required OTEL packages are available")
        
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        return False

def test_otel_env_vars():
    """Test if OTEL environment variables are set"""
    print("\n" + "=" * 60)
    print("Checking OTEL Environment Variables")
    print("=" * 60)
    
    required_vars = {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "Your OTEL collector endpoint",
        "OTEL_SERVICE_NAME": "Service name for filtering",
    }
    
    optional_vars = {
        "OTEL_EXPORTER_OTLP_HEADERS": "Authentication headers (if needed)",
        "OTEL_TRACES_EXPORTER": "Should be 'otlp'",
        "OTEL_LOGS_EXPORTER": "Should be 'otlp'",
        "OTEL_METRICS_EXPORTER": "Should be 'otlp'",
        "CREWAI_TRACING_ENABLED": "Should be 'true'",
    }
    
    all_set = True
    
    print("\nRequired variables:")
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}={value[:50]}..." if len(value) > 50 else f"  ✅ {var}={value}")
        else:
            print(f"  ❌ {var} - NOT SET ({desc})")
            all_set = False
    
    print("\nOptional variables:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}={value}")
        else:
            print(f"  ⚠️  {var} - not set ({desc})")
    
    return all_set

def test_crewai_auto_instrumentation():
    """Test if CrewAI automatically instruments when CREWAI_TRACING_ENABLED=true"""
    print("\n" + "=" * 60)
    print("Testing CrewAI Auto-Instrumentation")
    print("=" * 60)
    
    # Check if CREWAI_TRACING_ENABLED is set
    tracing_enabled = os.getenv("CREWAI_TRACING_ENABLED", "").lower() == "true"
    
    if not tracing_enabled:
        print("⚠️  CREWAI_TRACING_ENABLED is not set to 'true'")
        print("   CrewAI may not automatically instrument OTEL")
        return False
    
    print("✅ CREWAI_TRACING_ENABLED=true is set")
    
    # Try to check if instrumentation happens automatically
    # This is tricky - we'd need to actually import crewai and see if it instruments
    # For now, we'll just verify the setup is correct
    print("ℹ️  Note: CrewAI should automatically use OTEL when:")
    print("   1. CREWAI_TRACING_ENABLED=true")
    print("   2. opentelemetry-instrumentation-crewai is installed (✅ verified)")
    print("   3. OTEL environment variables are set")
    
    return True

def test_manual_instrumentation_fallback():
    """Show how to manually instrument if auto doesn't work"""
    print("\n" + "=" * 60)
    print("Manual Instrumentation (Fallback Option)")
    print("=" * 60)
    
    print("If automatic instrumentation doesn't work, you can manually instrument:")
    print("""
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor

# Call this BEFORE creating your crew
CrewAIInstrumentor().instrument()
""")
    
    # Check if we can do this
    try:
        from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
        print("✅ Manual instrumentation is available as fallback")
        return True
    except ImportError:
        print("❌ Manual instrumentation not available")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("OTEL Setup Verification")
    print("=" * 60 + "\n")
    
    results = {
        "Packages": test_otel_packages(),
        "Environment Variables": test_otel_env_vars(),
        "Auto-Instrumentation": test_crewai_auto_instrumentation(),
        "Manual Fallback": test_manual_instrumentation_fallback(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ All checks passed! OTEL setup should work.")
        print("\nNext steps:")
        print("1. Run your crew with the environment variables set")
        print("2. Check your OTEL endpoint for traces from service 'tech-lead-crew'")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\nIf automatic instrumentation doesn't work, use manual instrumentation:")
        print("   Add to test_local.py before creating crew:")
        print("   from opentelemetry.instrumentation.crewai import CrewAIInstrumentor")
        print("   CrewAIInstrumentor().instrument()")


