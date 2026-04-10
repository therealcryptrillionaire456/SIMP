#!/usr/bin/env python3
"""
Test script for the Scrapling Query Tool.
"""

import sys
import json
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, '.')

from tools.scrapling_query_app.server import app

client = TestClient(app)

def test_health():
    """Test health check endpoint."""
    print("Testing health check...")
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Scrapling Query Tool"
    print("✓ Health check passed")

def test_root():
    """Test root endpoint returns HTML."""
    print("\nTesting root endpoint...")
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Scrapling Query Tool" in response.text
    print("✓ Root endpoint returns HTML")

def test_sync_query():
    """Test synchronous query endpoint."""
    print("\nTesting synchronous query...")
    query_data = {
        "query": "test query",
        "max_results": 2,
        "fetcher_type": "dynamic",
        "use_cache": True
    }
    
    response = client.post("/api/query", json=query_data)
    assert response.status_code == 200
    data = response.json()
    
    assert data["query"] == "test query"
    assert data["status"] == "completed"
    assert len(data["search_results"]) <= 2
    assert len(data["extracted_content"]) <= 2
    
    print(f"✓ Sync query returned {len(data['extracted_content'])} results")

def test_async_query():
    """Test asynchronous query endpoint."""
    print("\nTesting asynchronous query...")
    query_data = {
        "query": "async test",
        "max_results": 1,
        "fetcher_type": "static",
        "use_cache": True
    }
    
    # Start async query
    response = client.post("/api/query/async", json=query_data)
    assert response.status_code == 200
    data = response.json()
    request_id = data["request_id"]
    assert data["status"] == "queued"
    
    print(f"✓ Async query started with ID: {request_id}")
    
    # Check status (might still be processing)
    response = client.get(f"/api/query/{request_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == request_id
    assert data["query"] == "async test"
    
    print(f"✓ Async query status: {data['status']}")

def test_all_requests():
    """Test getting all requests."""
    print("\nTesting all requests endpoint...")
    response = client.get("/api/requests")
    assert response.status_code == 200
    data = response.json()
    # Should return a list (might be empty)
    assert isinstance(data, list)
    print(f"✓ Got {len(data)} active requests")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Scrapling Query Tool")
    print("=" * 60)
    
    try:
        test_health()
        test_root()
        test_sync_query()
        test_async_query()
        test_all_requests()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()