# KTC App Migration: Emergent.sh → Local SIMP System

## 📋 **Current State Assessment**

### **What You Have:**
1. **KTC App** - Being developed on emergent.sh platform
2. **SIMP System** - Local development environment with:
   - Sovereign Self Compiler v2
   - QuantumArb integration
   - Broker system (port 5555)
   - Complete KTC documentation suite
3. **KTC_MASTER_DOCS** - Complete specifications and architecture

### **Migration Goals:**
1. Bring KTC app codebase from emergent.sh to local
2. Integrate with existing SIMP ecosystem
3. Set up local development environment
4. Connect to SIMP broker and agents
5. Deploy to staging/production

## 🔍 **Step 1: Audit Emergent.sh Environment**

### **Checklist:**
```bash
# 1. Identify what's on emergent.sh
# Access emergent.sh and run:
- ls -la /app/  # Main application directory
- cat package.json  # Frontend dependencies
- cat requirements.txt  # Backend dependencies
- ls -la config/  # Configuration files
- ps aux | grep -E "(node|python|nginx)"  # Running processes
- netstat -tulpn  # Open ports and services
```

### **Key Information to Gather:**
1. **Code Structure** - How is the app organized?
2. **Dependencies** - What packages/libraries are used?
3. **Database** - What database and schema?
4. **Services** - What microservices are running?
5. **Configuration** - Environment variables and configs
6. **Build Process** - How is it built/deployed?

## 📥 **Step 2: Export Code & Assets**

### **Option A: Git Repository Export**
```bash
# If emergent.sh uses Git:
git clone <emergent-repo-url> ktc-app
cd ktc-app
git remote remove origin
git remote add origin <your-new-repo-url>
```

### **Option B: Direct File Export**
```bash
# Create archive on emergent.sh:
tar -czf ktc-app-backup.tar.gz \
  --exclude=node_modules \
  --exclude=.git \
  --exclude=__pycache__ \
  /app/

# Download to local:
scp user@emergent.sh:/path/to/ktc-app-backup.tar.gz .
tar -xzf ktc-app-backup.tar.gz
```

### **Option C: Docker Container Export**
```bash
# If using Docker on emergent.sh:
docker commit <container-id> ktc-app-image
docker save ktc-app-image > ktc-app-image.tar

# Import locally:
docker load < ktc-app-image.tar
```

## 🏗️ **Step 3: Local Environment Setup**

### **3.1 Create Local Project Structure**
```bash
# Create KTC directory in SIMP system
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/
mkdir -p ktc-app/
cd ktc-app/

# Create standard structure
mkdir -p \
  frontend/ \
  backend/ \
  mobile/ \
  infrastructure/ \
  docs/ \
  scripts/
```

### **3.2 Set Up Monorepo (Based on KTC_MASTER_DOCS)**
```bash
# Copy monorepo structure from documentation
cp -r ../keep-the-change/documents/KTC_MASTER_DOCS/08-monorepo-structure.md .
cp -r ../self_compiler_v2/config/self_compiler_config.json config/

# Create package.json for monorepo
cat > package.json << 'EOF'
{
  "name": "keepthechange-monorepo",
  "private": true,
  "workspaces": [
    "apps/*",
    "packages/*",
    "services/*/client"
  ],
  "scripts": {
    "dev": "turbo run dev",
    "build": "turbo run build",
    "test": "turbo run test",
    "lint": "turbo run lint",
    "format": "prettier --write \"**/*.{ts,tsx,js,jsx,json,md}\"",
    "docker:build": "turbo run docker:build",
    "deploy:local": "turbo run deploy:local"
  },
  "devDependencies": {
    "turbo": "^1.10.0",
    "typescript": "^5.0.0",
    "eslint": "^8.0.0",
    "prettier": "^3.0.0"
  }
}
EOF
```

### **3.3 Install Dependencies**
```bash
# Install TurboRepo for monorepo management
npm install -g turbo

# Install project dependencies
npm install

# Set up Python virtual environment
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🔗 **Step 4: SIMP System Integration**

### **4.1 Connect to SIMP Broker**
```python
# Create SIMP integration module
cat > backend/simp_integration.py << 'EOF'
"""
SIMP System Integration for KTC App.
"""
import os
import json
import requests
from typing import Dict, List, Optional, Any

class SIMPIntegration:
    def __init__(self, broker_url: str = None, api_key: str = None):
        self.broker_url = broker_url or os.getenv("SIMP_BROKER_URL", "http://127.0.0.1:5555")
        self.api_key = api_key or os.getenv("SIMP_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        })
    
    def send_intent(self, intent_type: str, source_agent: str, 
                   target_agent: str, payload: Dict) -> Dict:
        """Send intent to SIMP broker."""
        intent = {
            "intent_type": intent_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "payload": payload
        }
        
        response = self.session.post(
            f"{self.broker_url}/intents/route",
            json=intent
        )
        response.raise_for_status()
        return response.json()
    
    def register_ktc_agent(self) -> Dict:
        """Register KTC agent with SIMP broker."""
        agent_card = {
            "agent_id": "ktc_agent",
            "name": "KTC Agent",
            "description": "KeepTheChange receipt processing and savings agent",
            "capabilities": [
                "process_receipt",
                "price_comparison",
                "savings_recommendation",
                "crypto_investment_advice"
            ],
            "endpoint": os.getenv("KTC_AGENT_ENDPOINT", "http://localhost:8001"),
            "status": "active"
        }
        
        response = self.session.post(
            f"{self.broker_url}/agents/register",
            json=agent_card
        )
        return response.json()
    
    def get_quantumarb_recommendation(self, amount: float, risk_profile: str) -> Dict:
        """Get investment recommendation from QuantumArb."""
        return self.send_intent(
            intent_type="analyze_investment",
            source_agent="ktc_agent",
            target_agent="quantumarb",
            payload={
                "amount": amount,
                "risk_profile": risk_profile,
                "currency": "USD"
            }
        )
EOF
```

### **4.2 Create KTC Agent Service**
```python
# Create KTC agent service
cat > services/ktc-agent/main.py << 'EOF'
"""
KTC Agent Service - SIMP-compatible agent for receipt processing.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import Dict, Any
import base64
import json

app = FastAPI(title="KTC Agent", version="1.0.0")

class ReceiptRequest(BaseModel):
    receipt_image_base64: str
    user_id: str
    context: Dict[str, Any] = {}

class InvestmentRequest(BaseModel):
    amount: float
    risk_profile: str
    currency: str = "USD"

@app.post("/process-receipt")
async def process_receipt(request: ReceiptRequest):
    """Process receipt image and extract transaction data."""
    try:
        # Decode image
        image_data = base64.b64decode(request.receipt_image_base64)
        
        # TODO: Implement OCR processing
        # For now, return mock data
        return {
            "processed": True,
            "transaction_data": {
                "merchant": "Example Merchant",
                "total_amount": 29.99,
                "items": [
                    {"name": "Item 1", "price": 19.99},
                    {"name": "Item 2", "price": 10.00}
                ],
                "savings_opportunities": []
            },
            "roundup_recommendation": {
                "amount": 0.01,
                "rationale": "Standard roundup to nearest dollar"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/investment-recommendation")
async def investment_recommendation(request: InvestmentRequest):
    """Get investment recommendation."""
    return {
        "recommendation": {
            "cryptocurrency": "BTC",
            "amount": request.amount,
            "expected_return": 0.08,
            "risk_level": "medium"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ktc-agent"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
EOF
```

### **4.3 Update SIMP Broker Configuration**
```bash
# Update SIMP broker to recognize KTC agent
cat >> /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/config/config.py << 'EOF'

# KTC Agent Configuration
KTC_AGENT_CONFIG = {
    "agent_id": "ktc_agent",
    "endpoint": "http://localhost:8001",
    "capabilities": [
        "process_receipt",
        "price_comparison", 
        "savings_recommendation",
        "crypto_investment_advice"
    ],
    "requires_approval": False,
    "rate_limit": 100  # requests per minute
}

# Add to registered agents
REGISTERED_AGENTS.append("ktc_agent")
EOF
```

## 🧪 **Step 5: Migration Testing**

### **5.1 Create Migration Test Suite**
```python
# Create migration tests
cat > tests/test_migration.py << 'EOF'
"""
Migration tests for KTC app from emergent.sh to local SIMP.
"""
import pytest
import requests
import json
import os
from pathlib import Path

def test_simp_broker_connection():
    """Test connection to SIMP broker."""
    response = requests.get("http://127.0.0.1:5555/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_ktc_agent_registration():
    """Test KTC agent registration with SIMP broker."""
    agent_card = {
        "agent_id": "ktc_agent_test",
        "name": "KTC Test Agent",
        "capabilities": ["test_capability"],
        "endpoint": "http://localhost:8001"
    }
    
    response = requests.post(
        "http://127.0.0.1:5555/agents/register",
        json=agent_card
    )
    assert response.status_code in [200, 201]

def test_code_structure():
    """Test that migrated code structure is correct."""
    required_dirs = [
        "frontend",
        "backend", 
        "services",
        "config",
        "tests"
    ]
    
    for dir_name in required_dirs:
        assert Path(dir_name).exists(), f"Missing directory: {dir_name}"

def test_dependencies():
    """Test that required dependencies are available."""
    # Check Python dependencies
    import fastapi
    import pydantic
    import uvicorn
    
    # Check Node.js dependencies if package.json exists
    if Path("package.json").exists():
        import json
        with open("package.json") as f:
            package = json.load(f)
            assert "dependencies" in package or "devDependencies" in package

def test_environment_variables():
    """Test that required environment variables are set."""
    required_vars = [
        "SIMP_BROKER_URL",
        "SIMP_API_KEY",
        "DATABASE_URL"
    ]
    
    for var in required_vars:
        assert os.getenv(var) is not None, f"Missing environment variable: {var}"
EOF
```

### **5.2 Run Migration Tests**
```bash
# Run tests
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/ktc-app/
pytest tests/test_migration.py -v

# Test SIMP integration
python -c "
from backend.simp_integration import SIMPIntegration
simp = SIMPIntegration()
print('SIMP Integration test:', simp.broker_url)
"

# Test KTC agent
cd services/ktc-agent/
python main.py &
AGENT_PID=$!
sleep 2
curl http://localhost:8001/health
kill $AGENT_PID
```

## 🚀 **Step 6: Deployment & Integration**

### **6.1 Docker Compose Setup**
```yaml
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # SIMP Broker
  simp-broker:
    image: simp-broker:latest
    ports:
      - "5555:5555"
    environment:
      - SIMP_API_KEY=${SIMP_API_KEY}
    volumes:
      - ./data:/app/data
  
  # KTC Frontend
  ktc-frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_SIMP_BROKER_URL=http://simp-broker:5555
    depends_on:
      - simp-broker
  
  # KTC Backend API
  ktc-api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@ktc-db:5432/keepthechange
      - SIMP_BROKER_URL=http://simp-broker:5555
    depends_on:
      - ktc-db
      - simp-broker
  
  # KTC Agent
  ktc-agent:
    build: ./services/ktc-agent
    ports:
      - "8001:8001"
    environment:
      - SIMP_BROKER_URL=http://simp-broker:5555
    depends_on:
      - simp-broker
  
  # Database
  ktc-db:
    image: postgres:15
    environment:
      - POSTGRES_DB=keepthechange
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
EOF
```

### **6.2 Local Development Scripts**
```bash
# Create development scripts
cat > scripts/dev.sh << 'EOF'
#!/bin/bash
# KTC App Development Script

set -e

echo "🚀 Starting KTC App Development Environment"

# Check dependencies
command -v docker >/dev/null 2>&1 || { echo "Docker required"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose required"; exit 1; }

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Check SIMP broker
curl -f http://localhost:5555/health || echo "SIMP broker not ready"

# Start frontend development
echo "Starting frontend development server..."
cd frontend && npm run dev &

# Start backend development  
echo "Starting backend development server..."
cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &

echo "✅ KTC App running at:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   SIMP Broker: http://localhost:5555"
echo "   KTC Agent: http://localhost:8001"

# Keep script running
wait
EOF

chmod +x scripts/dev.sh
```

## 📊 **Step 7: Verification & Monitoring**

### **7.1 Create Monitoring Dashboard**
```python
# Create monitoring script
cat > scripts/monitor.py << 'EOF'
"""
Monitoring script for KTC app migration.
"""
import requests
import time
import json
from datetime import datetime

SERVICES = {
    "simp-broker": "http://localhost:5555/health",
    "ktc-frontend": "http://localhost:3000/api/health",
    "ktc-api": "http://localhost:8000/health",
    "ktc-agent": "http://localhost:8001/health",
    "database": "http://localhost:5432"  # PostgreSQL
}

def check_service(name, url):
    """Check if a service is healthy."""
    try:
        if name == "database":
            # Special check for PostgreSQL
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="keepthechange",
                user="postgres",
                password="password"
            )
            conn.close()
            return True, "Connected"
        else:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return True, data.get("status", "healthy")
            else:
                return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    """Main monitoring loop."""
    print("🔍 KTC App Migration Monitor")
    print("=" * 60)
    
    while True:
        print(f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        all_healthy = True
        
        for name, url in SERVICES.items():
            healthy, message = check_service(name, url)
            status = "✅" if healthy else "❌"
            all_healthy = all_healthy and healthy
            
            print(f"{status} {name:15} {message}")
        
        print("-" * 60)
        
        if all_healthy:
            print("🎉 All services healthy!")
        else:
            print("⚠️  Some services are down")
        
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    main()
EOF
```

### **7.2 Migration Verification Checklist**
```markdown
# Migration Verification Checklist

## ✅ Code Migration
- [ ] All source code exported from emergent.sh
- [ ] Dependencies documented and installed
- [ ] Configuration files migrated
- [ ] Database schema exported
- [ ] Assets (images, fonts, etc.) transferred

## ✅ Local Environment
- [ ] Development environment set up
- [ ] Dependencies installed (npm, pip)
- [ ] Database running locally
- [ ] SIMP broker accessible
- [ ] Environment variables configured

## ✅ SIMP Integration
- [ ] KTC agent registered with SIMP broker
- [ ] QuantumArb integration working
- [ ] Intent routing functional
- [ ] Agent communication tested

## ✅ Application Functionality
- [ ] Frontend loads without errors
- [ ] Backend API endpoints working
- [ ] Database connections established
- [ ] User authentication functional
- [ ] Receipt processing working

## ✅ Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] SIMP integration tests passing
- [ ] End-to-end tests working

## ✅ Deployment
- [ ] Docker containers building
- [ ] Docker Compose working
- [ ] Services starting correctly
- [ ] Health checks passing
- [ ] Monitoring in place
```

## 🎯 **Quick Start Commands**

```bash
# 1. Export from emergent.sh (run on emergent.sh)
tar -czf ktc-app.tar.gz --exclude=node_modules --exclude=.git /app/

# 2. Download to local
scp user@emergent.sh:ktc-app.tar.gz .

# 3. Extract and set up
tar -xzf ktc-app.tar.gz
cd ktc-app/

# 4. Set up environment
cp .env.example .env
# Edit .env with your settings

# 5. Start development
./scripts/dev.sh

# 6. Monitor migration
python scripts/monitor.py

# 7. Run tests
pytest tests/ -v

# 8. Register with SIMP broker
curl -X POST http://localhost:5555/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"ktc_agent","name":"KTC Agent"}'
```

## 🆘 **Troubleshooting Common Issues**

### **Issue: SIMP Broker Connection Failed**
```bash
# Check if SIMP broker is running
curl http://localhost:5555/health

# Start SIMP broker if not running
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/
python -m simp.server.broker &
```

### **Issue: Database Connection Failed**
```bash
# Check PostgreSQL
docker ps | grep postgres
# If not running:
docker-compose up -d ktc-db
```

### **Issue: Missing Dependencies**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### **Issue: Port Conflicts**
```bash
# Check what's using ports
lsof -i :3000  # Frontend
lsof -i :8000  # Backend API
lsof -i :8001  # KTC Agent
lsof -i :5555  # SIMP Broker

# Kill conflicting processes
kill -9 <PID>
```

## 📞 **Support & Next Steps**

### **Immediate Actions:**
1. **Export code** from emergent.sh using the commands above
2. **Set up local environment** with the provided scripts
3. **Test SIMP integration** with the test suite
4. **Deploy locally** using Docker Compose

### **Next Phase:**
1. **CI/CD Pipeline** - Set up automated testing and deployment
2. **Production Deployment** - Deploy to staging/production servers
3. **Monitoring & Alerting** - Set up comprehensive monitoring
4. **Scaling** - Prepare for user growth

### **Get Help:**
- Check `KTC_MASTER_DOCS/` for detailed specifications
- Use the Sovereign Self Compiler v2 for automated improvements
- Consult SIMP system documentation for integration details
- Run `./scripts/dev.sh --help` for development commands

## 🎉 **Migration Complete!**

Once all steps are completed, you'll have:
1. ✅ KTC app running locally
2. ✅ Integrated with SIMP ecosystem
3. ✅ Connected to QuantumArb for crypto investments
4. ✅ Full development environment
5. ✅ Monitoring and testing in place

**Time Estimate:** 2-4 hours for complete migration
**Complexity:** Medium (automated scripts handle most tasks)
**Risk:** Low (phased approach with testing at each step)