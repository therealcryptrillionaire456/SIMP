#!/usr/bin/env python3
"""
Mother Goose Dashboard - Coordinates flock of geese working on mesh protocol layers.
Monitors progress, reprompts stuck geese, and ensures no redundant work.
"""

import json
import time
import threading
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mother_goose")

class GooseStatus(Enum):
    """Status of a goose worker."""
    IDLE = "idle"
    WORKING = "working"
    STUCK = "stuck"
    COMPLETED = "completed"
    FAILED = "failed"

class LayerStatus(Enum):
    """Status of a mesh protocol layer."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"

@dataclass
class GooseTask:
    """Task assigned to a goose."""
    goose_id: str
    layer: int
    description: str
    assigned_at: str
    status: GooseStatus
    progress: float  # 0.0 to 1.0
    last_update: str
    notes: List[str]
    files_to_touch: List[str]
    dependencies: List[str]  # Other goose IDs this depends on
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GooseTask':
        return cls(**data)

@dataclass
class LayerProgress:
    """Progress tracking for a mesh protocol layer."""
    layer_number: int
    layer_name: str
    status: LayerStatus
    geese_assigned: List[str]
    completed_tasks: int
    total_tasks: int
    verification_passed: bool
    notes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayerProgress':
        return cls(**data)

class MotherGooseDashboard:
    """Mother Goose coordination system."""
    
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = Path(log_dir) if log_dir else Path("data/mother_goose")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self.geese: Dict[str, GooseTask] = {}
        self.layers: Dict[int, LayerProgress] = {}
        self.coordination_log: List[Dict[str, Any]] = []
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Initialize layers based on the mesh protocol stack
        self._init_layers()
        
        # Start monitoring thread
        self._monitor_thread = None
        self._running = False
        
        logger.info("Mother Goose Dashboard initialized")
    
    def _init_layers(self) -> None:
        """Initialize the mesh protocol layers."""
        layer_definitions = [
            (1, "Physical Transport", "UDP multicast, BLE, Nostr WebSocket"),
            (2, "Mesh Bus", "Gossip, offline store, payment channels, receipts"),
            (3, "Intent Routing Protocol", "Capability gossip, intent matching, mesh routing"),
            (4, "Reputation & Trust Graph", "Payment history + receipt chain as trust signal"),
            (5, "Distributed A2A Consensus", "Quorum voting on trades, distributed aggregation"),
            (6, "Commitment Market", "Intent staking, automated settlement on execution")
        ]
        
        for num, name, description in layer_definitions:
            self.layers[num] = LayerProgress(
                layer_number=num,
                layer_name=name,
                status=LayerStatus.NOT_STARTED,
                geese_assigned=[],
                completed_tasks=0,
                total_tasks=0,
                verification_passed=False,
                notes=[description]
            )
    
    def register_goose(self, goose_id: str, layer: int, description: str, 
                      files_to_touch: List[str], dependencies: List[str] = None) -> bool:
        """Register a new goose worker."""
        with self._lock:
            if goose_id in self.geese:
                logger.warning(f"Goose {goose_id} already registered")
                return False
            
            task = GooseTask(
                goose_id=goose_id,
                layer=layer,
                description=description,
                assigned_at=datetime.utcnow().isoformat(),
                status=GooseStatus.IDLE,
                progress=0.0,
                last_update=datetime.utcnow().isoformat(),
                notes=[],
                files_to_touch=files_to_touch,
                dependencies=dependencies or []
            )
            
            self.geese[goose_id] = task
            
            # Update layer tracking
            if layer in self.layers:
                self.layers[layer].geese_assigned.append(goose_id)
                self.layers[layer].total_tasks += 1
                if self.layers[layer].status == LayerStatus.NOT_STARTED:
                    self.layers[layer].status = LayerStatus.IN_PROGRESS
            
            self._log_coordination("goose_registered", {
                "goose_id": goose_id,
                "layer": layer,
                "description": description
            })
            
            logger.info(f"Registered goose {goose_id} for layer {layer}: {description}")
            return True
    
    def update_goose_progress(self, goose_id: str, progress: float, 
                             status: GooseStatus, note: str = "") -> bool:
        """Update progress for a goose."""
        with self._lock:
            if goose_id not in self.geese:
                logger.error(f"Goose {goose_id} not found")
                return False
            
            goose = self.geese[goose_id]
            goose.progress = max(0.0, min(1.0, progress))
            goose.status = status
            goose.last_update = datetime.utcnow().isoformat()
            if note:
                goose.notes.append(f"{datetime.utcnow().isoformat()}: {note}")
            
            # Check if goose is stuck (no progress for too long)
            if status == GooseStatus.WORKING and progress < 0.1:
                # Check last update time
                last_update = datetime.fromisoformat(goose.last_update)
                time_diff = (datetime.utcnow() - last_update).total_seconds()
                if time_diff > 300:  # 5 minutes without progress
                    goose.status = GooseStatus.STUCK
                    self._log_coordination("goose_stuck", {
                        "goose_id": goose_id,
                        "layer": goose.layer,
                        "time_stuck_seconds": time_diff
                    })
                    logger.warning(f"Goose {goose_id} appears stuck on layer {goose.layer}")
            
            # Update layer progress if goose completed
            if status == GooseStatus.COMPLETED:
                layer = self.layers[goose.layer]
                layer.completed_tasks += 1
                
                # Check if layer is complete
                if layer.completed_tasks >= layer.total_tasks:
                    layer.status = LayerStatus.COMPLETED
                    self._log_coordination("layer_completed", {
                        "layer": goose.layer,
                        "layer_name": layer.layer_name
                    })
                    logger.info(f"Layer {goose.layer} ({layer.layer_name}) completed!")
            
            self._log_coordination("goose_progress_updated", {
                "goose_id": goose_id,
                "progress": progress,
                "status": status.value,
                "note": note
            })
            
            return True
    
    def get_stuck_geese(self) -> List[Dict[str, Any]]:
        """Get list of stuck geese that need reprompting."""
        with self._lock:
            stuck = []
            for goose_id, goose in self.geese.items():
                if goose.status == GooseStatus.STUCK:
                    stuck.append({
                        "goose_id": goose_id,
                        "layer": goose.layer,
                        "description": goose.description,
                        "progress": goose.progress,
                        "last_update": goose.last_update,
                        "notes": goose.notes[-3:] if goose.notes else []
                    })
            return stuck
    
    def get_layer_progress(self, layer: Optional[int] = None) -> Dict[str, Any]:
        """Get progress for a specific layer or all layers."""
        with self._lock:
            if layer is not None:
                if layer not in self.layers:
                    return {"error": f"Layer {layer} not found"}
                return self.layers[layer].to_dict()
            
            return {
                "layers": {num: layer.to_dict() for num, layer in self.layers.items()},
                "overall_progress": self._calculate_overall_progress()
            }
    
    def get_goose_status(self, goose_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status for a specific goose or all geese."""
        with self._lock:
            if goose_id is not None:
                if goose_id not in self.geese:
                    return {"error": f"Goose {goose_id} not found"}
                return self.geese[goose_id].to_dict()
            
            return {
                "geese": {gid: goose.to_dict() for gid, goose in self.geese.items()},
                "total_geese": len(self.geese),
                "active_geese": sum(1 for g in self.geese.values() 
                                  if g.status in [GooseStatus.WORKING, GooseStatus.STUCK])
            }
    
    def reprompt_goose(self, goose_id: str, new_instructions: str) -> bool:
        """Reprompt a stuck goose with new instructions."""
        with self._lock:
            if goose_id not in self.geese:
                logger.error(f"Goose {goose_id} not found")
                return False
            
            goose = self.geese[goose_id]
            if goose.status != GooseStatus.STUCK:
                logger.warning(f"Goose {goose_id} is not stuck (status: {goose.status})")
                return False
            
            # Update goose status and add reprompt note
            goose.status = GooseStatus.WORKING
            goose.notes.append(f"{datetime.utcnow().isoformat()}: REPROMPTED - {new_instructions}")
            goose.last_update = datetime.utcnow().isoformat()
            
            self._log_coordination("goose_reprompted", {
                "goose_id": goose_id,
                "layer": goose.layer,
                "new_instructions": new_instructions
            })
            
            logger.info(f"Reprompted goose {goose_id} on layer {goose.layer}")
            return True
    
    def verify_layer(self, layer: int, test_results: Dict[str, Any]) -> bool:
        """Verify that a layer implementation is correct."""
        with self._lock:
            if layer not in self.layers:
                logger.error(f"Layer {layer} not found")
                return False
            
            layer_progress = self.layers[layer]
            if layer_progress.status != LayerStatus.COMPLETED:
                logger.error(f"Layer {layer} not completed (status: {layer_progress.status})")
                return False
            
            # Check test results
            passed = test_results.get("passed", False)
            if passed:
                layer_progress.status = LayerStatus.VERIFIED
                layer_progress.verification_passed = True
                layer_progress.notes.append(f"{datetime.utcnow().isoformat()}: Verified - {test_results.get('summary', '')}")
                
                self._log_coordination("layer_verified", {
                    "layer": layer,
                    "layer_name": layer_progress.layer_name,
                    "test_results": test_results
                })
                
                logger.info(f"Layer {layer} ({layer_progress.layer_name}) verified!")
                return True
            else:
                layer_progress.notes.append(f"{datetime.utcnow().isoformat()}: Verification failed - {test_results.get('error', '')}")
                logger.error(f"Layer {layer} verification failed")
                return False
    
    def _calculate_overall_progress(self) -> float:
        """Calculate overall progress across all layers."""
        if not self.layers:
            return 0.0
        
        total_weight = len(self.layers)
        completed_weight = 0
        
        for layer_num, layer in self.layers.items():
            if layer.status == LayerStatus.VERIFIED:
                completed_weight += 1
            elif layer.status == LayerStatus.COMPLETED:
                completed_weight += 0.8  # Completed but not verified
            elif layer.status == LayerStatus.IN_PROGRESS:
                # Estimate based on goose progress in this layer
                layer_geese = [g for g in self.geese.values() if g.layer == layer_num]
                if layer_geese:
                    avg_progress = sum(g.progress for g in layer_geese) / len(layer_geese)
                    completed_weight += avg_progress * 0.6  # In progress weight
        
        return completed_weight / total_weight
    
    def _log_coordination(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log coordination events."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data
        }
        self.coordination_log.append(log_entry)
        
        # Write to file
        log_file = self.log_dir / "coordination_log.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                # Check for stuck geese
                stuck_geese = self.get_stuck_geese()
                if stuck_geese:
                    logger.warning(f"Found {len(stuck_geese)} stuck geese")
                    for goose in stuck_geese:
                        logger.warning(f"  - {goose['goose_id']}: {goose['description']} (progress: {goose['progress']})")
                
                # Log overall progress
                progress = self._calculate_overall_progress()
                logger.info(f"Overall progress: {progress:.1%}")
                
                # Save snapshot
                self.save_snapshot()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(30)  # Check every 30 seconds
    
    def start_monitoring(self) -> None:
        """Start the background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="MotherGooseMonitor"
        )
        self._monitor_thread.start()
        logger.info("Mother Goose monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            logger.info("Mother Goose monitoring stopped")
    
    def save_snapshot(self) -> None:
        """Save current state to disk."""
        with self._lock:
            snapshot = {
                "timestamp": datetime.utcnow().isoformat(),
                "geese": {gid: goose.to_dict() for gid, goose in self.geese.items()},
                "layers": {num: layer.to_dict() for num, layer in self.layers.items()},
                "overall_progress": self._calculate_overall_progress()
            }
            
            snapshot_file = self.log_dir / "snapshot.json"
            with open(snapshot_file, "w") as f:
                json.dump(snapshot, f, indent=2)
    
    def load_snapshot(self) -> bool:
        """Load state from disk."""
        snapshot_file = self.log_dir / "snapshot.json"
        if not snapshot_file.exists():
            return False
        
        try:
            with open(snapshot_file, "r") as f:
                snapshot = json.load(f)
            
            with self._lock:
                # Load geese
                self.geese.clear()
                for gid, data in snapshot.get("geese", {}).items():
                    self.geese[gid] = GooseTask.from_dict(data)
                
                # Load layers
                self.layers.clear()
                for num, data in snapshot.get("layers", {}).items():
                    self.layers[int(num)] = LayerProgress.from_dict(data)
            
            logger.info(f"Loaded snapshot from {snapshot_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return False
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for dashboard display."""
        with self._lock:
            # Convert geese to serializable format
            serializable_geese = {}
            for gid, goose in self.geese.items():
                serializable_geese[gid] = {
                    "goose_id": goose.goose_id,
                    "layer": goose.layer,
                    "description": goose.description,
                    "assigned_at": goose.assigned_at,
                    "status": goose.status.value,  # Convert Enum to string
                    "progress": goose.progress,
                    "last_update": goose.last_update,
                    "notes": goose.notes,
                    "files_to_touch": goose.files_to_touch,
                    "dependencies": goose.dependencies
                }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_progress": self._calculate_overall_progress(),
                "layers": [
                    {
                        "number": num,
                        "name": layer.layer_name,
                        "status": layer.status.value,  # Convert Enum to string
                        "progress": layer.completed_tasks / max(layer.total_tasks, 1),
                        "geese_assigned": len(layer.geese_assigned),
                        "verification_passed": layer.verification_passed
                    }
                    for num, layer in sorted(self.layers.items())
                ],
                "geese_by_status": {
                    "working": [serializable_geese[gid] for gid, g in self.geese.items() if g.status == GooseStatus.WORKING],
                    "stuck": [serializable_geese[gid] for gid, g in self.geese.items() if g.status == GooseStatus.STUCK],
                    "completed": [serializable_geese[gid] for gid, g in self.geese.items() if g.status == GooseStatus.COMPLETED],
                    "idle": [serializable_geese[gid] for gid, g in self.geese.items() if g.status == GooseStatus.IDLE]
                },
                "stuck_geese": self.get_stuck_geese()
            }


# Singleton instance
_mother_goose_instance: Optional[MotherGooseDashboard] = None

def get_mother_goose(log_dir: Optional[str] = None) -> MotherGooseDashboard:
    """Get or create the Mother Goose Dashboard singleton."""
    global _mother_goose_instance
    if _mother_goose_instance is None:
        _mother_goose_instance = MotherGooseDashboard(log_dir)
    return _mother_goose_instance


if __name__ == "__main__":
    # Example usage
    mother_goose = get_mother_goose()
    
    # Register some example geese
    mother_goose.register_goose(
        goose_id="goose_udp",
        layer=1,
        description="Implement UDP multicast transport",
        files_to_touch=["simp/mesh/transport/udp_multicast.py"],
        dependencies=[]
    )
    
    mother_goose.register_goose(
        goose_id="goose_intent_router",
        layer=3,
        description="Create IntentMeshRouter for mesh routing",
        files_to_touch=["simp/mesh/intent_router.py"],
        dependencies=["goose_udp"]
    )
    
    # Start monitoring
    mother_goose.start_monitoring()
    
    print("Mother Goose Dashboard running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mother_goose.stop_monitoring()
        print("\nMother Goose Dashboard stopped.")