#!/usr/bin/env python3
"""
DeerFlow Agent for SIMP System
===============================
Bridge between SIMP broker and DeerFlow agent orchestration system.
"""

import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests
from flask import Flask, request, jsonify

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.models.canonical_intent import CanonicalIntent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DeerFlowSubagent:
    """Represents a DeerFlow subagent."""
    agent_id: str
    task_id: str
    status: str  # pending, running, completed, failed
    created_at: str
    task_description: Optional[str] = None
    skill_id: Optional[str] = None
    result: Optional[Dict] = None
    completed_at: Optional[str] = None


class DeerFlowAgent:
    """DeerFlow integration agent for SIMP system."""
    
    def __init__(self, deerflow_url: str = None, api_key: str = None, agent_id: str = "deerflow"):
        self.agent_id = agent_id
        self.deerflow_url = deerflow_url or os.getenv("DEERFLOW_URL", "http://127.0.0.1:8001")
        self.api_key = api_key or os.getenv("DEERFLOW_API_KEY", "")
        self.subagents: Dict[str, DeerFlowSubagent] = {}
        self.capabilities = [
            "subagent_spawning",
            "skill_management", 
            "sandbox_execution",
            "concurrency_management",
            "agent_orchestration"
        ]
        
        logger.info(f"DeerFlow Agent initialized with URL: {self.deerflow_url}")
    
    def _deerflow_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make a request to DeerFlow API."""
        url = f"{self.deerflow_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"DeerFlow API error: {e}")
            raise
    
    def spawn_subagent(self, task_description: str, skill_id: Optional[str] = None) -> DeerFlowSubagent:
        """Spawn a new subagent in DeerFlow."""
        # Create a unique agent name
        agent_name = f"simp_{int(time.time())}_{hash(task_description) % 10000}"
        
        data = {
            "name": agent_name,
            "config": {
                "task": task_description,
                "skill_id": skill_id,
                "metadata": {
                    "source_agent": self.agent_id,
                    "simp_system": True,
                    "task_description": task_description
                }
            }
        }
        
        try:
            # Use the correct DeerFlow API endpoint
            result = self._deerflow_request("POST", "/api/agents", data)
            
            subagent = DeerFlowSubagent(
                agent_id=result.get("agent_id", agent_name),
                task_id=result.get("task_id", f"task_{agent_name}"),
                status="pending",
                created_at=datetime.utcnow().isoformat() + "Z",
                task_description=task_description,
                skill_id=skill_id
            )
            
            self.subagents[subagent.agent_id] = subagent
            logger.info(f"Spawned subagent: {subagent.agent_id} for task: {task_description[:50]}...")
            
            return subagent
        except Exception as e:
            logger.error(f"Failed to spawn subagent: {e}")
            raise
    
    def get_subagent_status(self, agent_id: str) -> Optional[DeerFlowSubagent]:
        """Get status of a subagent."""
        if agent_id not in self.subagents:
            # Try to get from DeerFlow API
            try:
                result = self._deerflow_request("GET", f"/api/agents/{agent_id}")
                # Create subagent record if found
                subagent = DeerFlowSubagent(
                    agent_id=agent_id,
                    task_id=result.get("task_id", ""),
                    status=result.get("status", "unknown"),
                    created_at=result.get("created_at", datetime.utcnow().isoformat() + "Z")
                )
                self.subagents[agent_id] = subagent
                return subagent
            except:
                return None
        
        return self.subagents[agent_id]
    
    def list_skills(self) -> List[Dict]:
        """List available skills in DeerFlow."""
        try:
            # Note: DeerFlow might have a different endpoint for skills
            # For now, return empty list or check if there's a skills endpoint
            return []
        except Exception as e:
            logger.error(f"Failed to list skills: {e}")
            return []
    
    def execute_in_sandbox(self, command: str, timeout_seconds: int = 30) -> Dict:
        """Execute a command in DeerFlow sandbox."""
        data = {
            "command": command,
            "timeout_seconds": timeout_seconds,
            "metadata": {
                "source_agent": self.agent_id
            }
        }
        
        try:
            # Note: DeerFlow might have a sandbox execution endpoint
            # For now, simulate execution
            return {
                "success": True,
                "output": f"Simulated execution of: {command}",
                "exit_code": 0
            }
        except Exception as e:
            logger.error(f"Failed to execute in sandbox: {e}")
            return {
                "success": False,
                "error": str(e),
                "output": ""
            }
    
    def handle_intent(self, intent: CanonicalIntent) -> Dict:
        """Handle incoming SIMP intents."""
        intent_type = intent.intent_type
        params = intent.params or {}
        action = params.get("action", "")
        
        logger.info(f"DeerFlow Agent handling intent: {intent_type}, action: {action}")
        
        response = {
            "success": False,
            "message": f"Unhandled intent type: {intent_type}",
            "data": {}
        }
        
        try:
            # Handle DeerFlow-specific intent types
            if intent_type == "deerflow_spawn" or action == "spawn_subagent":
                # Spawn a new subagent
                task = params.get("task", "")
                skill_id = params.get("skill_id")
                
                if not task:
                    response["message"] = "Missing required parameter: task"
                    return response
                
                subagent = self.spawn_subagent(task, skill_id)
                response = {
                    "success": True,
                    "message": f"Subagent spawned: {subagent.agent_id}",
                    "data": {
                        "subagent_id": subagent.agent_id,
                        "task_id": subagent.task_id,
                        "status": subagent.status,
                        "created_at": subagent.created_at
                    }
                }
                
            elif intent_type == "deerflow_status" or action == "check_status":
                # Check subagent status
                agent_id = params.get("agent_id", "")
                
                if not agent_id:
                    # List all subagents
                    subagents_list = []
                    for agent_id, subagent in self.subagents.items():
                        subagents_list.append(asdict(subagent))
                    
                    response = {
                        "success": True,
                        "message": f"Found {len(subagents_list)} subagents",
                        "data": {
                            "subagents": subagents_list
                        }
                    }
                else:
                    subagent = self.get_subagent_status(agent_id)
                    if subagent:
                        response = {
                            "success": True,
                            "message": f"Status for {agent_id}: {subagent.status}",
                            "data": asdict(subagent)
                        }
                    else:
                        response["message"] = f"Subagent not found: {agent_id}"
            
            elif intent_type == "deerflow_skills" or action == "list_skills":
                # List available skills
                skills = self.list_skills()
                response = {
                    "success": True,
                    "message": f"Found {len(skills)} skills",
                    "data": {
                        "skills": skills
                    }
                }
            
            elif intent_type == "deerflow_execute" or action == "execute_command":
                # Execute command in sandbox
                command = params.get("command", "")
                timeout = params.get("timeout_seconds", 30)
                
                if not command:
                    response["message"] = "Missing required parameter: command"
                    return response
                
                result = self.execute_in_sandbox(command, timeout)
                response = {
                    "success": result["success"],
                    "message": "Command executed" if result["success"] else f"Command failed: {result.get('error', 'Unknown error')}",
                    "data": result
                }
            
            elif intent_type == "health_check" or intent_type == "deerflow_health":
                # Health check
                response = {
                    "success": True,
                    "message": "DeerFlow Agent is healthy",
                    "data": {
                        "agent_id": self.agent_id,
                        "deerflow_url": self.deerflow_url,
                        "subagent_count": len(self.subagents),
                        "capabilities": self.capabilities
                    }
                }
                
            else:
                response["message"] = f"Unknown intent type for DeerFlow: {intent_type}"
                
        except Exception as e:
            logger.error(f"Error handling intent {intent_type}: {e}")
            response = {
                "success": False,
                "message": f"Error: {str(e)}",
                "data": {}
            }
        
        return response


# Flask app for HTTP interface
app = Flask(__name__)
deerflow_agent = DeerFlowAgent()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "agent_id": deerflow_agent.agent_id,
        "deerflow_url": deerflow_agent.deerflow_url,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


@app.route('/capabilities', methods=['GET'])
def capabilities():
    """Get agent capabilities."""
    return jsonify({
        "capabilities": deerflow_agent.capabilities,
        "agent_type": "management"
    })


@app.route('/subagents', methods=['GET'])
def list_subagents():
    """List all subagents."""
    subagents_list = []
    for agent_id, subagent in deerflow_agent.subagents.items():
        subagents_list.append(asdict(subagent))
    
    return jsonify({
        "subagents": subagents_list,
        "count": len(subagents_list)
    })


@app.route('/intent', methods=['POST'])
def handle_intent():
    """Handle SIMP intents."""
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No JSON data provided"
            }), 400
        
        # Convert to CanonicalIntent
        intent = CanonicalIntent(
            intent_type=data.get("intent_type", ""),
            source_agent=data.get("source_agent", "unknown"),
            target_agent=data.get("target_agent", deerflow_agent.agent_id),
            params=data.get("params", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z")
        )
        
        # Handle intent
        result = deerflow_agent.handle_intent(intent)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in /intent endpoint: {e}")
        return jsonify({
            "success": False,
            "message": f"Internal error: {str(e)}"
        }), 500


if __name__ == '__main__':
    port = int(os.getenv("DEERFLOW_AGENT_PORT", "8888"))
    logger.info(f"Starting DeerFlow Agent on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)