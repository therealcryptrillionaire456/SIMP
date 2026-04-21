#!/usr/bin/env python3
"""
DeerFlow Agent for SIMP System
===============================
Integrates DeerFlow agent spawning and management capabilities into SIMP.
DeerFlow provides:
- Subagent spawning and management
- Sandboxed command execution
- Skill loading and management
- Loop/concurrency guards

This agent acts as a bridge between SIMP and DeerFlow.
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from flask import Flask, request, jsonify

# Add SIMP to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from simp.agent import SimpAgent
from simp.models.canonical_intent import CanonicalIntent

logger = logging.getLogger(__name__)

@dataclass
class DeerFlowSubagent:
    """Represents a DeerFlow subagent."""
    agent_id: str
    task_id: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

@dataclass
class DeerFlowSkill:
    """Represents a DeerFlow skill."""
    skill_id: str
    name: str
    description: str
    version: str
    enabled: bool

class DeerFlowAgent(SimpAgent):
    """SIMP agent that integrates with DeerFlow for agent spawning and management."""
    
    def __init__(self, agent_id: str = "deerflow"):
        super().__init__(agent_id, organization="SIMP")
        
        # DeerFlow configuration
        self.deerflow_url = os.getenv("DEERFLOW_URL", "http://127.0.0.1:8001")
        self.api_key = os.getenv("DEERFLOW_API_KEY", "")
        
        # Track spawned subagents
        self.subagents: Dict[str, DeerFlowSubagent] = {}
        self.skills: Dict[str, DeerFlowSkill] = {}
        
        # Agent capabilities
        self.capabilities = [
            "subagent_spawning",
            "skill_management", 
            "sandbox_execution",
            "concurrency_management",
            "agent_health_monitoring"
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
        data = {
            "task": task_description,
            "skill_id": skill_id,
            "metadata": {
                "source_agent": self.agent_id,
                "simp_system": True
            }
        }
        
        try:
            result = self._deerflow_request("POST", "/api/v1/subagents/spawn", data)
            
            subagent = DeerFlowSubagent(
                agent_id=result.get("agent_id", f"deerflow_subagent_{len(self.subagents)}"),
                task_id=result.get("task_id", ""),
                status="pending",
                created_at=datetime.utcnow().isoformat() + "Z"
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
            return None
        
        try:
            result = self._deerflow_request("GET", f"/api/v1/subagents/{agent_id}/status")
            
            subagent = self.subagents[agent_id]
            subagent.status = result.get("status", subagent.status)
            subagent.completed_at = result.get("completed_at")
            subagent.result = result.get("result")
            subagent.error = result.get("error")
            
            return subagent
        except Exception as e:
            logger.error(f"Failed to get subagent status: {e}")
            return self.subagents[agent_id]
    
    def list_skills(self) -> List[DeerFlowSkill]:
        """List available DeerFlow skills."""
        try:
            result = self._deerflow_request("GET", "/api/v1/skills")
            
            skills = []
            for skill_data in result.get("skills", []):
                skill = DeerFlowSkill(
                    skill_id=skill_data.get("id"),
                    name=skill_data.get("name"),
                    description=skill_data.get("description"),
                    version=skill_data.get("version"),
                    enabled=skill_data.get("enabled", True)
                )
                skills.append(skill)
                self.skills[skill.skill_id] = skill
            
            return skills
        except Exception as e:
            logger.error(f"Failed to list skills: {e}")
            return []
    
    def execute_sandbox_command(self, command: str, timeout: int = 30) -> Dict:
        """Execute a command in DeerFlow sandbox."""
        data = {
            "command": command,
            "timeout": timeout,
            "sandbox": True
        }
        
        try:
            result = self._deerflow_request("POST", "/api/v1/execute", data)
            return result
        except Exception as e:
            logger.error(f"Failed to execute sandbox command: {e}")
            return {"success": False, "error": str(e), "output": ""}
    
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
                
                subagent = self.spawn_subagent(task, skill_id)
                response = {
                    "success": True,
                    "message": "Subagent spawned successfully",
                    "data": asdict(subagent)
                }
                
            elif intent_type == "deerflow_status" or action == "get_subagent_status":
                # Get subagent status
                agent_id = params.get("agent_id", "")
                
                subagent = self.get_subagent_status(agent_id)
                if subagent:
                    response = {
                        "success": True,
                        "message": "Subagent status retrieved",
                        "data": asdict(subagent)
                    }
                else:
                    response = {
                        "success": False,
                        "message": f"Subagent not found: {agent_id}",
                        "data": {}
                    }
                    
            elif intent_type == "deerflow_skills" or action == "list_skills":
                # List available skills
                skills = self.list_skills()
                response = {
                    "success": True,
                    "message": f"Found {len(skills)} skills",
                    "data": {
                        "skills": [asdict(skill) for skill in skills]
                    }
                }
                
            elif intent_type == "deerflow_execute" or action == "execute_command":
                # Execute sandbox command
                command = params.get("command", "")
                timeout = params.get("timeout", 30)
                
                result = self.execute_sandbox_command(command, timeout)
                response = {
                    "success": result.get("success", False),
                    "message": "Command executed",
                    "data": result
                }
                
            elif intent_type == "deerflow_health" or intent_type == "health_check":
                # Health check
                response = {
                    "success": True,
                    "message": "DeerFlow Agent healthy",
                    "data": {
                        "subagents_count": len(self.subagents),
                        "skills_count": len(self.skills),
                        "deerflow_url": self.deerflow_url,
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

def create_app():
    """Create Flask app for DeerFlow agent."""
    app = Flask(__name__)
    agent = DeerFlowAgent()
    
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "agent_id": agent.agent_id})
    
    @app.route("/intent", methods=["POST"])
    def handle_intent():
        try:
            data = request.json
            intent = CanonicalIntent(**data)
            result = agent.handle_intent(intent)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error in intent handler: {e}")
            return jsonify({
                "success": False,
                "message": f"Error: {str(e)}",
                "data": {}
            }), 500
    
    @app.route("/capabilities", methods=["GET"])
    def get_capabilities():
        return jsonify({
            "agent_id": agent.agent_id,
            "capabilities": agent.capabilities,
            "deerflow_url": agent.deerflow_url
        })
    
    @app.route("/subagents", methods=["GET"])
    def list_subagents():
        subagents = [asdict(sa) for sa in agent.subagents.values()]
        return jsonify({
            "count": len(subagents),
            "subagents": subagents
        })
    
    return app

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and run the agent
    app = create_app()
    
    port = int(os.getenv("DEERFLOW_AGENT_PORT", "8888"))
    logger.info(f"Starting DeerFlow Agent on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)