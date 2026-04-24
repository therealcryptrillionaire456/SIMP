#!/bin/bash
# Manual fix for quantum_mesh_consumer.py

echo "Applying manual fix to quantum_mesh_consumer.py..."

# Create a backup
cp quantum_mesh_consumer.py quantum_mesh_consumer.py.manual_backup

# Use sed to comment out mesh bus code
sed -i '' 's/from simp\.mesh\.bus import get_mesh_bus/# from simp.mesh.bus import get_mesh_bus  # DISABLED/' quantum_mesh_consumer.py

# Comment out the mesh bus registration in _register_with_mesh_bus
sed -i '' '/# Try mesh bus first/,/return False/s/^/# /' quantum_mesh_consumer.py
sed -i '' '/# Try mesh bus first/s/^# //' quantum_mesh_consumer.py  # Uncomment the comment line
sed -i '' 's/# Try mesh bus first/# DISABLED: Mesh bus registration - using HTTP instead/' quantum_mesh_consumer.py

# Comment out mesh bus subscription
sed -i '' '/# Subscribe via mesh bus/,/logger.error.*MeshBus subscription error/s/^/# /' quantum_mesh_consumer.py
sed -i '' '/# Subscribe via mesh bus/s/^# //' quantum_mesh_consumer.py  # Uncomment the comment line
sed -i '' 's/# Subscribe via mesh bus/# DISABLED: Mesh bus subscription - using HTTP instead/' quantum_mesh_consumer.py

# Comment out main mesh bus registration
sed -i '' '/# Register with mesh bus/,/logger.error.*MeshBus pre-subscription to intent_requests failed/s/^/# /' quantum_mesh_consumer.py
sed -i '' '/# Register with mesh bus/s/^# //' quantum_mesh_consumer.py  # Uncomment the comment line
sed -i '' 's/# Register with mesh bus/# DISABLED: Main mesh bus registration - using HTTP instead/' quantum_mesh_consumer.py

echo "✅ Manual fix applied"
echo "Starting QIP with HTTP transport only..."
