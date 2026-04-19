#!/usr/bin/env python3
"""
Test script to verify KEEPTHECHANGE.com backend structure
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    modules_to_test = [
        "app.core.config",
        "app.core.database",
        "app.core.security",
        "app.core.logging",
        "app.models.user",
        "app.models.shopping",
        "app.models.payment",
        "app.models.crypto",
        "app.models.subscription",
        "app.schemas.user",
        "app.schemas.shopping",
        "app.schemas.payment",
        "app.schemas.crypto",
        "app.schemas.subscription",
        "app.schemas.admin",
        "app.api.users",
        "app.api.shopping",
        "app.api.payments",
        "app.api.crypto",
        "app.api.subscriptions",
        "app.api.mobile",
        "app.api.admin"
    ]
    
    failed_imports = []
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"  ✓ {module_name}")
        except ImportError as e:
            print(f"  ✗ {module_name}: {e}")
            failed_imports.append(module_name)
    
    return failed_imports

def test_directory_structure():
    """Verify directory structure exists"""
    print("\nTesting directory structure...")
    
    required_dirs = [
        "app",
        "app/api",
        "app/core",
        "app/models",
        "app/schemas",
        "logs",
        "uploads"
    ]
    
    required_files = [
        "main.py",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "start.sh",
        ".env.example",
        "README.md",
        "app/__init__.py",
        "app/api/__init__.py",
        "app/core/__init__.py",
        "app/models/__init__.py",
        "app/schemas/__init__.py",
        "app/core/config.py",
        "app/core/database.py",
        "app/core/security.py",
        "app/core/logging.py"
    ]
    
    missing_dirs = []
    missing_files = []
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_dirs.append(dir_path)
            print(f"  ✗ Directory missing: {dir_path}")
        else:
            print(f"  ✓ Directory exists: {dir_path}")
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
            print(f"  ✗ File missing: {file_path}")
        else:
            print(f"  ✓ File exists: {file_path}")
    
    return missing_dirs, missing_files

def test_fastapi_app():
    """Test FastAPI app creation"""
    print("\nTesting FastAPI app creation...")
    
    try:
        from main import app
        print("  ✓ FastAPI app created successfully")
        
        # Check routes
        routes = [route.path for route in app.routes]
        print(f"  ✓ Found {len(routes)} routes")
        
        # Check essential routes
        essential_routes = ["/", "/health", "/docs", "/redoc"]
        for route in essential_routes:
            if route in routes:
                print(f"  ✓ Route exists: {route}")
            else:
                print(f"  ✗ Route missing: {route}")
        
        return True
    except Exception as e:
        print(f"  ✗ Failed to create FastAPI app: {e}")
        return False

def test_configuration():
    """Test configuration loading"""
    print("\nTesting configuration...")
    
    try:
        from app.core.config import settings
        
        # Check required settings
        required_settings = [
            "APP_NAME",
            "ENVIRONMENT",
            "DATABASE_URL",
            "SECRET_KEY",
            "HOST",
            "PORT"
        ]
        
        for setting in required_settings:
            if hasattr(settings, setting):
                value = getattr(settings, setting)
                if value:
                    print(f"  ✓ {setting}: {str(value)[:50]}...")
                else:
                    print(f"  ⚠ {setting}: (empty)")
            else:
                print(f"  ✗ {setting}: missing")
        
        return True
    except Exception as e:
        print(f"  ✗ Failed to load configuration: {e}")
        return False

def test_schemas():
    """Test Pydantic schemas"""
    print("\nTesting Pydantic schemas...")
    
    try:
        from app.schemas.user import UserCreate, UserResponse
        from app.schemas.shopping import ShoppingListCreate, ShoppingListResponse
        from app.schemas.crypto import CryptoInvestmentResponse
        from app.schemas.subscription import SubscriptionResponse
        
        # Test schema creation
        user_data = {
            "email": "test@example.com",
            "password": "Test123!",
            "first_name": "Test",
            "last_name": "User"
        }
        
        user_create = UserCreate(**user_data)
        print(f"  ✓ UserCreate schema: {user_create.email}")
        
        shopping_data = {
            "name": "Test Shopping List",
            "description": "Test description"
        }
        
        shopping_create = ShoppingListCreate(**shopping_data)
        print(f"  ✓ ShoppingListCreate schema: {shopping_create.name}")
        
        return True
    except Exception as e:
        print(f"  ✗ Failed to test schemas: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("KEEPTHECHANGE.com Backend Structure Test")
    print("=" * 60)
    
    # Run tests
    failed_imports = test_imports()
    missing_dirs, missing_files = test_directory_structure()
    app_ok = test_fastapi_app()
    config_ok = test_configuration()
    schemas_ok = test_schemas()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = 5
    passed_tests = 0
    
    if not failed_imports:
        print("✓ All imports successful")
        passed_tests += 1
    else:
        print(f"✗ Failed imports: {len(failed_imports)}")
    
    if not missing_dirs and not missing_files:
        print("✓ Directory structure complete")
        passed_tests += 1
    else:
        print(f"✗ Missing: {len(missing_dirs)} dirs, {len(missing_files)} files")
    
    if app_ok:
        print("✓ FastAPI app created successfully")
        passed_tests += 1
    else:
        print("✗ FastAPI app creation failed")
    
    if config_ok:
        print("✓ Configuration loaded successfully")
        passed_tests += 1
    else:
        print("✗ Configuration loading failed")
    
    if schemas_ok:
        print("✓ Pydantic schemas validated")
        passed_tests += 1
    else:
        print("✗ Schema validation failed")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n✅ All tests passed! Backend structure is ready.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and configure settings")
        print("2. Run: ./start.sh (or python main.py)")
        print("3. Access API docs at: http://localhost:8000/docs")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)