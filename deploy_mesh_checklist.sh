#!/bin/bash

# SIMP Mesh Upgrade Deployment Checklist
# Run this script to verify all prerequisites before mesh upgrade deployment

# Don't exit on error for warnings
set +e

echo "================================================"
echo "🚀 SIMP Mesh Upgrade Deployment Checklist"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

check_python_module() {
    if python3 -c "import $1" &> /dev/null; then
        print_success "Python module $1 is installed"
        return 0
    else
        print_error "Python module $1 is not installed"
        return 1
    fi
}

check_file() {
    if [ -f "$1" ]; then
        print_success "File exists: $1"
        return 0
    else
        print_error "File missing: $1"
        return 1
    fi
}

check_directory() {
    if [ -d "$1" ]; then
        print_success "Directory exists: $1"
        return 0
    else
        print_error "Directory missing: $1"
        return 1
    fi
}

check_port() {
    if lsof -i :$1 &> /dev/null; then
        print_warning "Port $1 is in use"
        return 1
    else
        print_success "Port $1 is available"
        return 0
    fi
}

check_broker() {
    if curl -s http://127.0.0.1:5555/health &> /dev/null; then
        print_success "SIMP broker is running"
        return 0
    else
        print_error "SIMP broker is not running"
        return 1
    fi
}

# Start checks
echo "🔍 Starting deployment checklist..."
echo ""

# Section 1: System Requirements
echo "1. System Requirements"
echo "---------------------"

check_command "python3.10"
check_command "pip3"
check_command "curl"
check_command "lsof" || print_warning "lsof not installed (port checking limited)"

# Check Python version
PYTHON_VERSION=$(python3.10 --version 2>&1 | cut -d' ' -f2)
if [[ $PYTHON_VERSION == 3.10* ]]; then
    print_success "Python 3.10.x is installed"
else
    print_error "Python 3.10.x is required (found: $PYTHON_VERSION)"
fi

echo ""

# Section 2: SIMP System
echo "2. SIMP System Status"
echo "---------------------"

check_broker

# Check if we can get broker status
if BROKER_STATUS=$(curl -s http://127.0.0.1:5555/health 2>/dev/null); then
    AGENTS_ONLINE=$(echo $BROKER_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin)['agents_online'])")
    print_success "Broker has $AGENTS_ONLINE agents online"
else
    print_warning "Could not get detailed broker status"
fi

check_directory "simp"
check_directory "simp/mesh"
check_file "simp/mesh/bus.py"
check_file "simp/mesh/enhanced_bus.py"
check_file "simp/mesh/transport/udp_multicast.py"

echo ""

# Section 3: Mesh Components
echo "3. Mesh Components"
echo "------------------"

check_python_module "simp.mesh"
check_python_module "simp.mesh.bus"
check_python_module "simp.mesh.enhanced_bus"

# Test mesh core functionality
if python3.10 -c "
import sys
sys.path.insert(0, '.')
try:
    from simp.mesh.bus import get_mesh_bus
    from simp.mesh.packet import MeshPacket, MessageType
    import time
    
    bus = get_mesh_bus()
    bus.register_agent('check_agent')
    
    packet = MeshPacket(
        msg_type=MessageType.EVENT,
        sender_id='check_sender',
        recipient_id='check_recipient',
        payload={'test': 'check'},
        message_id='check_001'
    )
    
    success = bus.send(packet)
    if success:
        print('MESH_CORE_OK')
    else:
        print('MESH_CORE_FAIL')
        
except Exception as e:
    print(f'MESH_CORE_ERROR: {e}')
" | grep -q "MESH_CORE_OK"; then
    print_success "Mesh core functionality test passed"
else
    print_error "Mesh core functionality test failed"
fi

echo ""

# Section 4: Network Configuration
echo "4. Network Configuration"
echo "------------------------"

# Check mesh ports
print_info "Checking mesh network ports..."
check_port 8888  # Default mesh UDP port
check_port 9999  # Alternative mesh UDP port
check_port 1900  # SSDP port (may be in use)

# Check multicast support
print_info "Checking multicast support..."
if ip route | grep -q "224.0.0.0/4"; then
    print_success "Multicast routing appears to be configured"
else
    print_warning "Multicast routing may not be configured"
fi

echo ""

# Section 5: Dependencies
echo "5. Dependencies"
echo "---------------"

# Check Python dependencies
REQUIRED_MODULES=("dataclasses" "typing" "json" "threading" "time" "uuid" "sqlite3" "hashlib" "hmac")

for module in "${REQUIRED_MODULES[@]}"; do
    check_python_module "$module"
done

# Check for optional modules
OPTIONAL_MODULES=("cryptography" "msgpack" "orjson")
for module in "${OPTIONAL_MODULES[@]}"; do
    if python3 -c "import $module" &> /dev/null; then
        print_success "Optional module $module is installed"
    else
        print_warning "Optional module $module is not installed"
    fi
done

echo ""

# Section 6: Files and Configuration
echo "6. Files and Configuration"
echo "--------------------------"

check_file "MESH_UPGRADE_INTEGRATION_PLAN.md"
check_file "MESH_UPGRADE_FINAL_DOCUMENTATION.md"
check_file "simp_mesh_upgrade_verification_dashboard.html"
check_file "mesh_bridge_demo.py"
check_file "test_mesh_simple.py"

# Check for configuration files
if [ -f "config/mesh_config.yaml" ] || [ -f "config/mesh_config.yaml.example" ]; then
    print_success "Mesh configuration files exist"
else
    print_warning "Mesh configuration files not found (may need to be created)"
fi

echo ""

# Section 7: Testing
echo "7. Testing"
echo "----------"

# Run simple mesh test
print_info "Running mesh integration test..."
if python3.10 test_mesh_simple.py 2>&1 | grep -q "MeshBus Core: ✅ PASS"; then
    print_success "Mesh integration test passed"
else
    print_error "Mesh integration test failed"
    print_warning "Run: python3.10 test_mesh_simple.py for details"
fi

# Check for test files
if [ -f "tests/test_mesh_bus.py" ] || [ -f "tests/test_mesh_packet.py" ]; then
    print_success "Mesh test files exist"
else
    print_warning "Mesh test files not found"
fi

echo ""

# Summary
echo "================================================"
echo "📋 Deployment Checklist Summary"
echo "================================================"
echo ""

print_info "Next steps:"
echo "1. Review any warnings or errors above"
echo "2. Run: python3.10 mesh_bridge_demo.py (to test bridge)"
echo "3. Test UDP multicast: sudo python3.10 test_udp_multicast.py"
echo "4. Review deployment plan: MESH_UPGRADE_INTEGRATION_PLAN.md"
echo "5. Begin Phase 1 deployment (monitoring-only mode)"
echo ""

print_info "For UDP multicast issues:"
echo "- On macOS/Linux: May need to run with sudo"
echo "- Check firewall: sudo ufw allow 8888/udp"
echo "- Verify multicast: ping -c 2 239.255.255.250"
echo ""

echo "================================================"
echo "🚀 Deployment checklist complete!"
echo "================================================"