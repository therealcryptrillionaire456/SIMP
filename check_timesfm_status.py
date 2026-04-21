#!/usr/bin/env python3
"""Check TimesFM status in the broker."""

import os
import sys

# Set environment variables
os.environ['SIMP_TIMESFM_ENABLED'] = 'true'
os.environ['SIMP_TIMESFM_SHADOW_MODE'] = 'true'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import TimesFM service
from simp.integrations.timesfm_service import get_timesfm_service
import asyncio

async def check_timesfm():
    """Check TimesFM service status."""
    print("=== Checking TimesFM Service Status ===")
    
    # Get TimesFM service
    service = await get_timesfm_service()
    
    print(f"Service initialized: {service is not None}")
    print(f"Enabled: {service._enabled}")
    print(f"Shadow mode: {service._shadow_mode}")
    print(f"Model loaded: {service._model is not None}")
    print(f"Checkpoint: {service._checkpoint}")
    print(f"Context length: {service._context_len}")
    print(f"Default horizon: {service._default_horizon}")
    
    # Check cache
    print(f"\nCache size: {service.cache.size}")
    
    # Check audit log
    print(f"Audit log entries: {len(service.audit._log)}")
    
    # Try to get health report
    health = service.health_report()
    print(f"\nHealth Report:")
    print(f"  Total requests: {health.get('total_requests', 0)}")
    print(f"  Cache hits: {health.get('cache_hits', 0)}")
    print(f"  Errors: {health.get('errors', 0)}")
    print(f"  Shadow mode samples: {health.get('shadow_mode_samples', 0)}")
    
    # Test a simple forecast
    print(f"\n=== Testing Forecast Request ===")
    from simp.integrations.timesfm_service import ForecastRequest
    
    request = ForecastRequest(
        series_id="test_check",
        values=[1.0, 2.0, 1.5, 2.5, 1.8, 2.2, 1.9, 2.1],
        requesting_agent="check_script",
        horizon=3,
    )
    
    try:
        response = await service.forecast(request)
        print(f"Forecast request completed")
        print(f"  Available: {response.available}")
        print(f"  Shadow mode: {response.shadow_mode}")
        print(f"  Cached: {response.cached}")
        print(f"  Latency: {response.latency_ms:.2f} ms")
        
        if response.available and not response.shadow_mode:
            print(f"  Point forecast: {response.point_forecast}")
            print(f"  Lower bound: {response.lower_bound}")
            print(f"  Upper bound: {response.upper_bound}")
        elif response.shadow_mode:
            print("  ✓ Forecast computed in shadow mode (not returned)")
        else:
            print(f"  Forecast not available: {response.error}")
            
    except Exception as e:
        print(f"Forecast error: {e}")
    
    print(f"\n=== TimesFM Status Check Complete ===")
    print(f"\nSummary:")
    print(f"  TimesFM is {'ENABLED' if service._enabled else 'DISABLED'}")
    print(f"  Running in {'SHADOW MODE' if service._shadow_mode else 'LIVE MODE'}")
    print(f"  Model is {'LOADED' if service._model is not None else 'NOT LOADED (lazy)'}")
    print(f"  Service is {'OPERATIONAL' if service._enabled else 'DISABLED'}")

if __name__ == "__main__":
    asyncio.run(check_timesfm())