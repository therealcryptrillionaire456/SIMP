#!/usr/bin/env python3
"""
ProjectX Integration for Stray Goose Quantum Mode

Integrates with ProjectX for judgment and escalation of quantum tasks.
Provides a safety net for uncertain or high-risk quantum operations.
"""

import json
import sys
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from quantum_mode_schema import (
    QuantumTask, RetrievalResult, VerificationResult,
    ProjectXJudgment, QuantumErrorCode
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ProjectXIntegration:
    """Integration with ProjectX for quantum task judgment."""
    
    endpoint: str
    api_key: Optional[str] = None
    timeout: int = 30  # seconds
    cache_enabled: bool = True
    
    # Cache for judgments
    _judgment_cache: Dict[str, Dict] = field(default_factory=dict)
    _cache_max_size: int = 1000
    
    def request_judgment(self, query: str, task: QuantumTask,
                        retrieval_result: RetrievalResult,
                        verification_result: VerificationResult,
                        trace_id: str) -> Dict:
        """
        Request judgment from ProjectX for a quantum task.
        
        Args:
            query: Original user query
            task: Quantum task
            retrieval_result: Retrieved examples
            verification_result: Verification result
            trace_id: Trace ID for correlation
            
        Returns:
            ProjectX judgment dictionary
        """
        # Generate cache key
        cache_key = self._generate_cache_key(query, task, retrieval_result)
        
        # Check cache
        if self.cache_enabled and cache_key in self._judgment_cache:
            logger.debug(f"Cache hit for ProjectX judgment: {cache_key[:50]}...")
            cached = self._judgment_cache[cache_key]
            cached["cached"] = True
            cached["cached_at"] = datetime.now().isoformat()
            return cached
        
        # Prepare request data
        request_data = self._prepare_request_data(
            query, task, retrieval_result, verification_result, trace_id
        )
        
        try:
            # Send request to ProjectX
            response = self._send_request(request_data)
            
            # Parse response
            judgment = self._parse_response(response, request_data)
            
            # Cache result
            if self.cache_enabled:
                self._judgment_cache[cache_key] = judgment
                self._manage_cache_size()
            
            return judgment
            
        except Exception as e:
            logger.error(f"Error requesting ProjectX judgment: {e}")
            return self._create_fallback_judgment(
                query, task, retrieval_result, verification_result,
                error=str(e)
            )
    
    def _generate_cache_key(self, query: str, task: QuantumTask,
                           retrieval_result: RetrievalResult) -> str:
        """Generate cache key for judgment request."""
        import hashlib
        
        # Create string representation
        data_str = f"{query}_{task.task_id}_{task.task_type}"
        
        # Add example IDs
        example_ids = [ex["id"] for ex in retrieval_result.examples[:3]]
        data_str += "_" + "_".join(example_ids)
        
        # Hash
        return hashlib.sha256(data_str.encode()).hexdigest()[:32]
    
    def _prepare_request_data(self, query: str, task: QuantumTask,
                             retrieval_result: RetrievalResult,
                             verification_result: VerificationResult,
                             trace_id: str) -> Dict:
        """Prepare data for ProjectX request."""
        # Extract key information from examples
        examples_summary = []
        for example in retrieval_result.examples[:5]:  # Limit to 5 examples
            examples_summary.append({
                "id": example.get("id"),
                "framework": example.get("framework"),
                "complexity": example.get("complexity"),
                "verification_status": example.get("verification_status"),
                "safety_checks": example.get("safety_checks", []),
                "tags": example.get("tags", [])
            })
        
        # Prepare verification summary
        verification_summary = {
            "status": verification_result.verification_status,
            "overall_score": verification_result.overall_score,
            "checks_passed": len([c for c in verification_result.checks 
                                if c.get("score", 0) >= 0.5]),
            "checks_total": len(verification_result.checks)
        }
        
        # Build request
        request_data = {
            "request_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "task": {
                "id": task.task_id,
                "type": task.task_type,
                "created_at": task.created_at
            },
            "retrieval_summary": {
                "examples_count": len(retrieval_result.examples),
                "confidence_level": retrieval_result.confidence_level,
                "match_scores": retrieval_result.match_scores[:3],
                "examples": examples_summary
            },
            "verification_summary": verification_summary,
            "context": {
                "system": "stray_goose_quantum_mode",
                "version": "1.0.0",
                "mode": "quantum_escalation"
            }
        }
        
        # Add API key if available
        if self.api_key:
            request_data["api_key"] = self.api_key
        
        return request_data
    
    def _send_request(self, request_data: Dict) -> Dict:
        """Send request to ProjectX endpoint."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "StrayGoose/1.0 QuantumMode"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.post(
                self.endpoint,
                json=request_data,
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"ProjectX request timeout after {self.timeout} seconds")
            raise Exception(f"ProjectX request timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"ProjectX request failed: {e}")
            raise Exception(f"ProjectX request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from ProjectX: {e}")
            raise Exception(f"Invalid ProjectX response")
    
    def _parse_response(self, response: Dict, request_data: Dict) -> Dict:
        """Parse ProjectX response."""
        # Extract judgment
        judgment = response.get("judgment", {})
        
        # Create ProjectXJudgment object
        px_judgment = ProjectXJudgment(
            request_id=request_data["request_id"],
            query=request_data["query"],
            task_type=request_data["task"]["type"],
            approved=judgment.get("approved", False),
            confidence=judgment.get("confidence", 0.5),
            reasoning=judgment.get("reasoning", "No reasoning provided"),
            constraints=judgment.get("constraints", []),
            recommendations=judgment.get("recommendations", []),
            judgment_time=datetime.now().isoformat(),
            projectx_version=response.get("version", "unknown")
        )
        
        # Add additional metadata
        result = px_judgment.to_dict()
        result.update({
            "response_received": True,
            "response_timestamp": datetime.now().isoformat(),
            "raw_response_summary": {
                "has_judgment": "judgment" in response,
                "has_reasoning": "reasoning" in (judgment or {}),
                "response_keys": list(response.keys())
            }
        })
        
        return result
    
    def _create_fallback_judgment(self, query: str, task: QuantumTask,
                                 retrieval_result: RetrievalResult,
                                 verification_result: VerificationResult,
                                 error: str) -> Dict:
        """Create fallback judgment when ProjectX is unavailable."""
        logger.warning(f"Creating fallback judgment due to: {error}")
        
        # Conservative fallback: only approve if verification passed with high score
        approved = (verification_result.verification_status == "passed" and 
                   verification_result.overall_score >= 0.8)
        
        reasoning = f"Fallback judgment: ProjectX unavailable ({error}). "
        reasoning += f"Verification status: {verification_result.verification_status}, "
        reasoning += f"Score: {verification_result.overall_score}. "
        reasoning += "Approved" if approved else "Rejected"
        
        px_judgment = ProjectXJudgment(
            request_id=f"fallback_{datetime.now().timestamp()}",
            query=query,
            task_type=task.task_type,
            approved=approved,
            confidence=0.3,  # Low confidence for fallback
            reasoning=reasoning,
            constraints=["fallback_mode", "no_projectx_consultation"],
            recommendations=["Retry with ProjectX when available"],
            judgment_time=datetime.now().isoformat(),
            projectx_version="fallback_1.0"
        )
        
        result = px_judgment.to_dict()
        result.update({
            "response_received": False,
            "fallback": True,
            "error": error,
            "warning": "Using fallback judgment - conservative approval"
        })
        
        return result
    
    def _manage_cache_size(self):
        """Manage cache size by removing oldest entries."""
        if len(self._judgment_cache) > self._cache_max_size:
            # Remove oldest 10% of entries
            keys_to_remove = list(self._judgment_cache.keys())[:self._cache_max_size // 10]
            for key in keys_to_remove:
                del self._judgment_cache[key]
            logger.debug(f"Cleaned ProjectX cache, removed {len(keys_to_remove)} entries")
    
    def batch_request_judgments(self, requests: List[Dict]) -> List[Dict]:
        """
        Request judgments for multiple tasks in batch.
        
        Args:
            requests: List of request dictionaries
            
        Returns:
            List of judgment dictionaries
        """
        # Prepare batch request
        batch_data = {
            "batch_id": f"batch_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "requests": requests,
            "count": len(requests)
        }
        
        if self.api_key:
            batch_data["api_key"] = self.api_key
        
        try:
            # Send batch request
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "StrayGoose/1.0 QuantumMode"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.endpoint}/batch",
                json=batch_data,
                headers=headers,
                timeout=self.timeout * 2  # Longer timeout for batch
            )
            
            response.raise_for_status()
            batch_response = response.json()
            
            # Parse batch response
            judgments = []
            for i, req in enumerate(requests):
                if i < len(batch_response.get("judgments", [])):
                    judgment_data = batch_response["judgments"][i]
                    judgment = self._parse_response(judgment_data, req)
                else:
                    # Fallback for missing judgments
                    judgment = self._create_fallback_judgment(
                        query=req.get("query", ""),
                        task=type('obj', (object,), {
                            'task_id': req.get("task", {}).get("id", ""),
                            'task_type': req.get("task", {}).get("type", "")
                        })(),
                        retrieval_result=type('obj', (object,), {
                            'examples': req.get("retrieval_summary", {}).get("examples", [])
                        })(),
                        verification_result=type('obj', (object,), {
                            'verification_status': req.get("verification_summary", {}).get("status", "unknown"),
                            'overall_score': req.get("verification_summary", {}).get("overall_score", 0.0)
                        })(),
                        error="Missing judgment in batch response"
                    )
                
                judgments.append(judgment)
            
            return judgments
            
        except Exception as e:
            logger.error(f"Error in batch judgment request: {e}")
            # Fallback to individual requests
            judgments = []
            for req in requests:
                # Extract data from request
                query = req.get("query", "")
                task_data = req.get("task", {})
                task = type('obj', (object,), {
                    'task_id': task_data.get("id", ""),
                    'task_type': task_data.get("type", ""),
                    'created_at': task_data.get("created_at", "")
                })()
                
                retrieval_data = req.get("retrieval_summary", {})
                retrieval_result = type('obj', (object,), {
                    'examples': retrieval_data.get("examples", []),
                    'confidence_level': retrieval_data.get("confidence_level", "medium"),
                    'match_scores': retrieval_data.get("match_scores", [])
                })()
                
                verification_data = req.get("verification_summary", {})
                verification_result = type('obj', (object,), {
                    'verification_status': verification_data.get("status", "unknown"),
                    'overall_score': verification_data.get("overall_score", 0.0)
                })()
                
                trace_id = req.get("request_id", f"fallback_{datetime.now().timestamp()}")
                
                judgment = self.request_judgment(
                    query=query,
                    task=task,
                    retrieval_result=retrieval_result,
                    verification_result=verification_result,
                    trace_id=trace_id
                )
                
                judgments.append(judgment)
            
            return judgments
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._judgment_cache),
            "cache_max_size": self._cache_max_size,
            "cache_enabled": self.cache_enabled,
            "endpoint": self.endpoint
        }
    
    def clear_cache(self):
        """Clear judgment cache."""
        self._judgment_cache.clear()
        logger.info("Cleared ProjectX judgment cache")


class MockProjectXIntegration:
    """Mock ProjectX integration for testing."""
    
    def __init__(self, approval_rate: float = 0.7):
        self.approval_rate = approval_rate
        self.request_count = 0
    
    def request_judgment(self, query: str, task: Any,
                        retrieval_result: Any,
                        verification_result: Any,
                        trace_id: str) -> Dict:
        """Mock judgment request."""
        self.request_count += 1
        
        # Simulate approval based on verification score
        base_score = verification_result.overall_score if hasattr(verification_result, 'overall_score') else 0.5
        approved = base_score >= (1.0 - self.approval_rate)
        
        reasoning = f"Mock judgment: verification score {base_score:.2f}, "
        reasoning += f"threshold {1.0 - self.approval_rate:.2f}. "
        reasoning += "Approved" if approved else "Rejected"
        
        return {
            "request_id": trace_id,
            "query": query,
            "task_type": task.task_type if hasattr(task, 'task_type') else "unknown",
            "approved": approved,
            "confidence": min(0.9, base_score * 0.8),
            "reasoning": reasoning,
            "constraints": ["mock_mode", "testing_only"],
            "recommendations": ["This is a mock judgment for testing"],
            "judgment_time": datetime.now().isoformat(),
            "projectx_version": "mock_1.0",
            "response_received": True,
            "mock": True,
            "request_count": self.request_count
        }


def main():
    """Command-line interface for ProjectX Integration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ProjectX Integration")
    parser.add_argument("--endpoint", required=True, help="ProjectX endpoint URL")
    parser.add_argument("--api-key", help="API key for ProjectX")
    parser.add_argument("--query", help="Query to get judgment for")
    parser.add_argument("--task-type", default="quantum_algorithm", help="Task type")
    parser.add_argument("--cache-stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache")
    
    args = parser.parse_args()
    
    # Initialize integration
    integration = ProjectXIntegration(
        endpoint=args.endpoint,
        api_key=args.api_key
    )
    
    if args.cache_stats:
        # Show cache statistics
        stats = integration.get_cache_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.clear_cache:
        # Clear cache
        integration.clear_cache()
        print("Cache cleared")
    
    elif args.query:
        # Request judgment
        # Create mock objects
        task = type('obj', (object,), {
            'task_id': 'test_task',
            'task_type': args.task_type,
            'created_at': datetime.now().isoformat()
        })()
        
        retrieval_result = type('obj', (object,), {
            'examples': [
                {
                    "id": "example_1",
                    "framework": "qiskit",
                    "complexity": "intermediate",
                    "verification_status": "verified",
                    "safety_checks": ["no_execution"],
                    "tags": ["test"]
                }
            ],
            'confidence_level': "high",
            'match_scores': [0.9]
        })()
        
        verification_result = type('obj', (object,), {
            'verification_status': "passed",
            'overall_score': 0.85
        })()
        
        trace_id = f"cli_{datetime.now().timestamp()}"
        
        judgment = integration.request_judgment(
            query=args.query,
            task=task,
            retrieval_result=retrieval_result,
            verification_result=verification_result,
            trace_id=trace_id
        )
        
        print(json.dumps(judgment, indent=2))
    
    else:
        parser.print_help()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())