"""
Keep the Change (KTC) Flask API Server

Main API server for the KTC application that integrates with SIMP system.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import requests

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3

# Import KTC agent
try:
    from simp.organs.ktc.agent.ktc_agent import KTCAgent, create_ktc_agent
    from simp.organs.ktc.mesh_agent import KTCMeshAgent, get_ktc_mesh_agent
except ModuleNotFoundError:
    import sys

    # Allow direct execution without relying on the ambiguous top-level `agent` name.
    sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))
    from simp.organs.ktc.agent.ktc_agent import KTCAgent, create_ktc_agent
    from simp.organs.ktc.mesh_agent import KTCMeshAgent, get_ktc_mesh_agent


# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ktc_api")

# Initialize KTC agent
ktc_agent = create_ktc_agent()
ktc_mesh_agent: Optional[KTCMeshAgent] = None

# Configuration
CONFIG = {
    "api_port": int(os.getenv("KTC_API_PORT", 8765)),
    "database_path": os.getenv("KTC_DATABASE_PATH", "data/ktc.db"),
    "simp_broker_url": os.getenv("SIMP_BROKER_URL", "http://localhost:5555"),
    "simp_api_key": os.getenv("SIMP_API_KEY", "test_key"),
    "upload_folder": "uploads/receipts",
    "max_file_size": 16 * 1024 * 1024,  # 16MB
}

# Ensure upload directory exists
Path(CONFIG["upload_folder"]).mkdir(parents=True, exist_ok=True)


def configure_runtime(
    mesh_agent: Optional[KTCMeshAgent] = None,
    simp_broker_url: Optional[str] = None,
) -> None:
    """Inject runtime dependencies from the startup wrapper."""
    global ktc_mesh_agent
    if mesh_agent is not None:
        ktc_mesh_agent = mesh_agent
    if simp_broker_url:
        CONFIG["simp_broker_url"] = simp_broker_url


def _get_mesh_agent() -> KTCMeshAgent:
    global ktc_mesh_agent
    if ktc_mesh_agent is None:
        ktc_mesh_agent = get_ktc_mesh_agent(
            broker_url=CONFIG["simp_broker_url"],
            autostart=False,
        )
    return ktc_mesh_agent


@app.route("/")
def index():
    """API root endpoint"""
    return jsonify({
        "service": "Keep the Change (KTC) API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "process_receipt": "/api/receipts/process (POST)",
            "compare_prices": "/api/prices/compare (POST)",
            "invest_savings": "/api/investments/create (POST)",
            "user_stats": "/api/users/<user_id>/stats (GET)",
            "agent_health": "/api/agent/health (GET)"
        },
        "simp_integration": {
            "broker_url": CONFIG["simp_broker_url"],
            "agent_id": ktc_agent.agent_id,
            "capabilities": ktc_agent.capabilities
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    mesh_status = None
    try:
        mesh_status = _get_mesh_agent().get_status()
    except Exception as exc:
        logger.debug(f"Mesh agent status unavailable during health check: {exc}")

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "ktc_api",
        "version": "1.0.0",
        "investment_routing": {
            "live_execution_enabled": (
                mesh_status.get("live_execution_enabled") if mesh_status else False
            ),
            "quantumarb_inbox": mesh_status.get("quantumarb_inbox") if mesh_status else None,
            "investments_queued": mesh_status.get("investments_queued", 0) if mesh_status else 0,
        },
    })


@app.route("/api/agent/health", methods=["GET"])
def agent_health():
    """Get KTC agent health status"""
    try:
        health_data = ktc_agent.health()
        try:
            health_data["mesh_runtime"] = _get_mesh_agent().get_status()
        except Exception as exc:
            health_data["mesh_runtime_error"] = str(exc)
        return jsonify(health_data)
    except Exception as e:
        logger.error(f"Error getting agent health: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/api/receipts/process", methods=["POST"])
def process_receipt():
    """
    Process a receipt image
    
    Expected JSON payload:
    {
        "user_id": "user_123",
        "store_name": "Whole Foods",
        "receipt_image": "base64_encoded_image"  # Optional for now
    }
    
    Or multipart form with image file
    """
    try:
        # Get request data
        if request.is_json:
            data = request.get_json()
            receipt_image = data.get("receipt_image")
        else:
            data = request.form.to_dict()
            # Handle file upload
            if 'receipt_image' in request.files:
                file = request.files['receipt_image']
                # Save file temporarily
                filename = f"receipt_{int(datetime.utcnow().timestamp())}_{file.filename}"
                filepath = Path(CONFIG["upload_folder"]) / filename
                file.save(filepath)
                receipt_image = str(filepath)
            else:
                receipt_image = None
        
        user_id = data.get("user_id")
        store_name = data.get("store_name", "Unknown Store")
        
        if not user_id:
            return jsonify({
                "status": "error",
                "error": "user_id is required"
            }), 400
        
        # Create intent for KTC agent
        intent_data = {
            "intent_type": "process_receipt",
            "parameters": {
                "user_id": user_id,
                "store_name": store_name,
                "receipt_id": f"rec_{int(datetime.utcnow().timestamp())}",
                "receipt_image": receipt_image
            }
        }
        
        # Process through KTC agent
        result = ktc_agent.handle_intent(intent_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to process receipt: {str(e)}"
        }), 500


@app.route("/api/prices/compare", methods=["POST"])
def compare_prices():
    """
    Compare prices for items
    
    Expected JSON payload:
    {
        "user_id": "user_123",
        "items": [
            {"name": "Organic Milk", "brand": "Organic Valley", "price": 5.99},
            {"name": "Whole Wheat Bread", "brand": "Nature's Own", "price": 3.49}
        ],
        "location": {
            "zipcode": "90210",
            "radius_miles": 10
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON payload required"
            }), 400
        
        items = data.get("items", [])
        user_id = data.get("user_id")
        location = data.get("location", {})
        
        if not items:
            return jsonify({
                "status": "error", 
                "error": "No items provided"
            }), 400
        
        # Create intent for KTC agent
        intent_data = {
            "intent_type": "compare_prices",
            "parameters": {
                "user_id": user_id,
                "items": items,
                "location": location
            }
        }
        
        # Process through KTC agent
        result = ktc_agent.handle_intent(intent_data)
        
        # Calculate savings
        if result.get("status") == "success":
            savings_intent = {
                "intent_type": "calculate_savings",
                "parameters": {
                    "comparisons": result.get("comparisons", [])
                }
            }
            savings_result = ktc_agent.handle_intent(savings_intent)
            result["savings_summary"] = savings_result
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error comparing prices: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to compare prices: {str(e)}"
        }), 500


@app.route("/api/investments/create", methods=["POST"])
def create_investment():
    """
    Invest savings into crypto
    
    Expected JSON payload:
    {
        "user_id": "user_123",
        "amount": 15.75,
        "receipt_id": "rec_123456",
        "auto_approve": true
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON payload required"
            }), 400
        
        user_id = data.get("user_id")
        amount = float(data.get("amount", 0))
        receipt_id = data.get("receipt_id")
        auto_approve = bool(data.get("auto_approve", True))
        asset = data.get("asset", "SOL")

        if not user_id:
            return jsonify({
                "status": "error",
                "error": "user_id is required"
            }), 400
        
        if amount <= 0:
            return jsonify({
                "status": "error",
                "error": "amount must be greater than 0"
            }), 400

        mesh_agent = _get_mesh_agent()
        routing = mesh_agent.queue_investment_request(
            user_id=user_id,
            amount_usd=amount,
            receipt_id=receipt_id,
            auto_approve=auto_approve,
            source="ktc_api",
            asset=asset,
            metadata={"request_ip": request.remote_addr},
        )

        response = {
            "status": "accepted",
            "message": (
                "Investment request queued for QuantumArb review"
                if routing["review_required"]
                else "Investment request queued for QuantumArb execution"
            ),
            "routing": routing,
        }
        return jsonify(response), 202
        
    except Exception as e:
        logger.error(f"Error creating investment: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to create investment: {str(e)}"
        }), 500


@app.route("/api/users/<user_id>/stats", methods=["GET"])
def get_user_stats(user_id: str):
    """Get user statistics"""
    try:
        # Create intent for KTC agent
        intent_data = {
            "intent_type": "get_user_stats",
            "parameters": {
                "user_id": user_id
            }
        }
        
        # Process through KTC agent
        result = ktc_agent.handle_intent(intent_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to get user stats: {str(e)}"
        }), 500


@app.route("/api/simp/route", methods=["POST"])
def route_to_simp():
    """
    Route an intent through SIMP broker
    
    This endpoint allows the KTC frontend to route intents through SIMP
    without going through the KTC agent first.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON payload required"
            }), 400
        
        # Extract intent data
        intent_type = data.get("intent_type")
        target_agent = data.get("target_agent", "auto")
        parameters = data.get("parameters", {})
        
        if not intent_type:
            return jsonify({
                "status": "error",
                "error": "intent_type is required"
            }), 400
        
        # Prepare SIMP intent
        simp_intent = {
            "intent_type": intent_type,
            "source_agent": "ktc_frontend",
            "target_agent": target_agent,
            "parameters": parameters,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        logger.info(f"Routing to SIMP: {intent_type} -> {target_agent}")
        
        # In production, this would make HTTP request to SIMP broker
        # For now, mock response
        mock_response = {
            "status": "success",
            "intent_id": f"intent_{int(datetime.utcnow().timestamp())}",
            "message": f"Intent '{intent_type}' routed to SIMP broker",
            "simp_intent": simp_intent,
            "note": "In production, this would make actual HTTP request to SIMP broker"
        }
        
        return jsonify(mock_response)
        
    except Exception as e:
        logger.error(f"Error routing to SIMP: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to route to SIMP: {str(e)}"
        }), 500


@app.route("/send", methods=["POST"])
@app.route("/mesh/send", methods=["POST"])
def proxy_mesh_send():
    """Proxy mesh packet sends through the broker so port 8765 can act as a mesh HTTP endpoint."""
    try:
        packet = request.get_json(silent=True) or {}
        if not packet:
            return jsonify({
                "status": "error",
                "error": "JSON payload required"
            }), 400

        broker_response = requests.post(
            f"{CONFIG['simp_broker_url'].rstrip('/')}/mesh/send",
            json=packet,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        content_type = broker_response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            body = broker_response.json()
            return jsonify(body), broker_response.status_code

        return (
            jsonify({
                "status": "error",
                "error": "Broker returned non-JSON response",
                "body": broker_response.text[:500],
            }),
            502,
        )
    except requests.RequestException as e:
        logger.error(f"Error proxying mesh send to SIMP broker: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to proxy mesh send: {str(e)}"
        }), 502
    except Exception as e:
        logger.error(f"Unexpected mesh proxy error: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Unexpected proxy error: {str(e)}"
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "status": "error",
        "error": "Endpoint not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({
        "status": "error",
        "error": "Method not allowed"
    }), 405


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "status": "error",
        "error": "Internal server error"
    }), 500


def start_server(host: str = "127.0.0.1", port: int = None, debug: bool = False):
    """Start the Flask server"""
    if port is None:
        port = CONFIG["api_port"]
    
    logger.info(f"Starting KTC API server on {host}:{port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"SIMP Broker URL: {CONFIG['simp_broker_url']}")
    logger.info(f"KTC Agent ID: {ktc_agent.agent_id}")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    # Start the server
    start_server(host="127.0.0.1", port=8765, debug=True)
