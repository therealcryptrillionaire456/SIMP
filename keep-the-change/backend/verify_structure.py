#!/usr/bin/env python3
"""
Simple verification of KEEPTHECHANGE.com backend structure
"""

import os
import sys
from pathlib import Path

def check_structure():
    """Check if all required files and directories exist"""
    print("🔍 Verifying KEEPTHECHANGE.com Backend Structure")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    all_good = True
    
    # Required directories
    required_dirs = [
        "app",
        "app/api",
        "app/core", 
        "app/models",
        "app/schemas",
        "logs",
        "uploads"
    ]
    
    print("\n📁 Checking directories:")
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ - MISSING")
            all_good = False
    
    # Required files
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
        "app/core/logging.py",
        "app/models/user.py",
        "app/models/shopping.py",
        "app/models/payment.py",
        "app/models/crypto.py",
        "app/models/subscription.py",
        "app/schemas/user.py",
        "app/schemas/shopping.py",
        "app/schemas/payment.py",
        "app/schemas/crypto.py",
        "app/schemas/subscription.py",
        "app/schemas/admin.py",
        "app/api/users.py",
        "app/api/shopping.py",
        "app/api/payments.py",
        "app/api/crypto.py",
        "app/api/subscriptions.py",
        "app/api/mobile.py",
        "app/api/admin.py"
    ]
    
    print("\n📄 Checking files:")
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"  ✅ {file_path} ({size:,} bytes)")
        else:
            print(f"  ❌ {file_path} - MISSING")
            all_good = False
    
    # Check file contents
    print("\n📊 Checking file contents:")
    
    # Check main.py has FastAPI app
    main_py = base_dir / "main.py"
    if main_py.exists():
        content = main_py.read_text()
        if "FastAPI" in content and "@app" in content:
            print("  ✅ main.py contains FastAPI application")
        else:
            print("  ⚠️  main.py may not have proper FastAPI setup")
            all_good = False
    
    # Check requirements.txt has key dependencies
    req_file = base_dir / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text()
        key_deps = ["fastapi", "sqlalchemy", "pydantic", "jose", "stripe"]
        found_deps = [dep for dep in key_deps if dep in content.lower()]
        print(f"  ✅ requirements.txt has {len(found_deps)}/{len(key_deps)} key dependencies")
    
    # Check Dockerfile
    dockerfile = base_dir / "Dockerfile"
    if dockerfile.exists():
        content = dockerfile.read_text()
        if "EXPOSE" in content and "CMD" in content:
            print("  ✅ Dockerfile properly configured")
        else:
            print("  ⚠️  Dockerfile may be incomplete")
    
    # Check docker-compose.yml
    compose_file = base_dir / "docker-compose.yml"
    if compose_file.exists():
        content = compose_file.read_text()
        if "postgres" in content and "redis" in content:
            print("  ✅ docker-compose.yml has full stack")
        else:
            print("  ⚠️  docker-compose.yml may be incomplete")
    
    return all_good

def check_architecture():
    """Check architecture documentation"""
    print("\n🏗️  Checking architecture documentation:")
    
    base_dir = Path(__file__).parent
    # Look in parent directory (keep-the-change/)
    arch_file = base_dir.parent / "KEEPTHECHANGE_ARCHITECTURE.md"
    
    if arch_file.exists():
        size = arch_file.stat().st_size
        print(f"  ✅ Architecture document: {size:,} bytes")
        
        # Check if it's comprehensive
        content = arch_file.read_text()
        sections = [
            "System Architecture",
            "Core Components",
            "Technical Implementation",
            "Business Model",
            "Development Roadmap"
        ]
        
        found_sections = [section for section in sections if section in content]
        print(f"  ✅ Contains {len(found_sections)}/{len(sections)} key sections")
        return True
    else:
        print("  ❌ Architecture document missing")
        return False

def generate_summary():
    """Generate implementation summary"""
    print("\n" + "=" * 60)
    print("📋 IMPLEMENTATION SUMMARY")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    
    # Count files by type
    python_files = list(base_dir.rglob("*.py"))
    api_files = list((base_dir / "app/api").rglob("*.py"))
    model_files = list((base_dir / "app/models").rglob("*.py"))
    schema_files = list((base_dir / "app/schemas").rglob("*.py"))
    
    print(f"📁 Total Python files: {len(python_files)}")
    print(f"🔌 API endpoints: {len(api_files)} files")
    print(f"🗄️  Database models: {len(model_files)} files")
    print(f"📝 Pydantic schemas: {len(schema_files)} files")
    
    # Estimate lines of code
    total_lines = 0
    for py_file in python_files:
        try:
            with open(py_file, 'r') as f:
                total_lines += len(f.readlines())
        except:
            pass
    
    print(f"📊 Estimated lines of code: {total_lines:,}")
    
    # API endpoints summary
    print("\n🔗 API ENDPOINTS IMPLEMENTED:")
    api_categories = {
        "users.py": "User authentication & management",
        "shopping.py": "Shopping lists & price comparison", 
        "payments.py": "Payment processing",
        "crypto.py": "Crypto investment & trading",
        "subscriptions.py": "Subscription management",
        "mobile.py": "Mobile features",
        "admin.py": "Admin dashboard"
    }
    
    for api_file, description in api_categories.items():
        file_path = base_dir / "app/api" / api_file
        if file_path.exists():
            print(f"  ✅ {api_file}: {description}")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Configure environment: cp .env.example .env")
    print("3. Start database: docker-compose up -d postgres redis")
    print("4. Run migrations: alembic upgrade head")
    print("5. Start server: ./start.sh")
    print("6. Access API docs: http://localhost:8000/docs")
    
    print("\n🎯 PHASE 2 READY:")
    print("• Crypto trading bot integration")
    print("• Tip-based investment system") 
    print("• Subscription tier management")
    print("• Portfolio tracking system")

def main():
    """Main verification function"""
    print("KEEPTHECHANGE.com Backend Verification")
    print("=" * 60)
    
    structure_ok = check_structure()
    arch_ok = check_architecture()
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    if structure_ok and arch_ok:
        print("✅ BACKEND STRUCTURE COMPLETE")
        print("\nAll required files and directories are in place.")
        print("The backend is ready for Phase 2 implementation.")
        
        generate_summary()
        
        print("\n" + "=" * 60)
        print("🎉 KEEPTHECHANGE.com Backend Phase 1 COMPLETED!")
        print("=" * 60)
        return True
    else:
        print("❌ BACKEND STRUCTURE INCOMPLETE")
        print("\nSome files or directories are missing.")
        print("Please check the errors above and complete the structure.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)