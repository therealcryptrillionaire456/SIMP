"""
Basic tests for KashClaw Media Grid agents.
"""
import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from simp.organs.media.agents.trend_harvester_agent import create_trend_harvester_agent
from simp.organs.media.agents.script_agent import create_script_agent
from simp.organs.media.agents.asset_agent import create_asset_agent
from simp.organs.media.agents.edit_packaging_agent import create_edit_packaging_agent
from simp.organs.media.agents.publisher_agent import create_publisher_agent
from simp.organs.media.agents.analytics_agent import create_analytics_agent
from simp.organs.media.models import GenerationTool


class TestMediaAgents(unittest.TestCase):
    """Test cases for media grid agents."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp(prefix="media_test_")
        self.data_dir = Path(self.test_dir) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Test data
        self.test_brief = {
            "brief_id": "brief_test_123",
            "title": "Test AI Tool Review",
            "description": "Testing the media grid system",
            "content_angle": "review",
            "target_platforms": ["tiktok", "youtube_shorts"],
            "primary_offer": {
                "name": "Test Tool",
                "description": "A test tool for demonstration",
                "affiliate_link": "https://example.com/test"
            }
        }
        
        self.test_script = {
            "script_id": "script_test_123",
            "brief_id": "brief_test_123",
            "title": "Test Script",
            "hooks": ["Test hook 1", "Test hook 2"],
            "scripts": [{
                "script_id": "script_1",
                "content": [{"section": "intro", "content": "Test content"}],
                "duration_estimate": 45
            }],
            "cta_variants": ["Test CTA 1", "Test CTA 2"],
            "platform_metadata": {
                "tiktok": {"caption": "Test caption", "hashtags": ["#test"]}
            }
        }
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_trend_harvester_agent_creation(self):
        """Test Trend Harvester Agent creation."""
        agent = create_trend_harvester_agent(
            agent_id="test_trend",
            data_dir=str(self.data_dir),
            research_interval_minutes=1
        )
        
        self.assertEqual(agent.agent_id, "test_trend")
        self.assertEqual(agent.agent_name, "Trend Harvester Agent")
        self.assertTrue(hasattr(agent, 'research_trends_and_generate_briefs'))
        
        # Check that data directory was created
        self.assertTrue(self.data_dir.exists())
    
    def test_script_agent_creation(self):
        """Test Script Agent creation."""
        agent = create_script_agent(
            agent_id="test_script",
            data_dir=str(self.data_dir),
            generation_tool=GenerationTool.CLAUDE
        )
        
        self.assertEqual(agent.agent_id, "test_script")
        self.assertEqual(agent.agent_name, "Script Agent")
        self.assertEqual(agent.generation_tool, GenerationTool.CLAUDE)
    
    def test_asset_agent_creation(self):
        """Test Asset Agent creation."""
        agent = create_asset_agent(
            agent_id="test_asset",
            data_dir=str(self.data_dir),
            default_tool=GenerationTool.HIGGSFIELD,
            budget_per_job=5.0
        )
        
        self.assertEqual(agent.agent_id, "test_asset")
        self.assertEqual(agent.agent_name, "Asset Agent")
        self.assertEqual(agent.default_tool, GenerationTool.HIGGSFIELD)
        self.assertEqual(agent.budget_per_job, 5.0)
    
    def test_edit_packaging_agent_creation(self):
        """Test Edit/Packaging Agent creation."""
        agent = create_edit_packaging_agent(
            agent_id="test_edit",
            data_dir=str(self.data_dir)
        )
        
        self.assertEqual(agent.agent_id, "test_edit")
        self.assertEqual(agent.agent_name, "Edit/Packaging Agent")
    
    def test_publisher_agent_creation(self):
        """Test Publisher Agent creation."""
        agent = create_publisher_agent(
            agent_id="test_publisher",
            data_dir=str(self.data_dir),
            max_retries=2,
            retry_delay=30
        )
        
        self.assertEqual(agent.agent_id, "test_publisher")
        self.assertEqual(agent.agent_name, "Publisher Agent")
        self.assertEqual(agent.max_retries, 2)
        self.assertEqual(agent.retry_delay, 30)
    
    def test_analytics_agent_creation(self):
        """Test Analytics Agent creation."""
        agent = create_analytics_agent(
            agent_id="test_analytics",
            data_dir=str(self.data_dir),
            analysis_interval_minutes=30
        )
        
        self.assertEqual(agent.agent_id, "test_analytics")
        self.assertEqual(agent.agent_name, "Analytics Agent")
        self.assertEqual(agent.analysis_interval_minutes, 30)
    
    def test_agent_ledger_operations(self):
        """Test agent ledger read/write operations."""
        agent = create_trend_harvester_agent(
            agent_id="test_ledger",
            data_dir=str(self.data_dir)
        )
        
        # Test appending to ledger
        test_record = {
            "test_id": "123",
            "message": "Test record",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        record_id = agent._append_to_ledger("test_ledger", test_record)
        self.assertIsNotNone(record_id)
        
        # Test reading from ledger
        records = agent._read_ledger("test_ledger", limit=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["test_id"], "123")
        
        # Test finding in ledger
        found = agent._find_in_ledger("test_ledger", "test_id", "123")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["message"], "Test record")
    
    def test_agent_health_check(self):
        """Test agent health check functionality."""
        agent = create_trend_harvester_agent(
            agent_id="test_health",
            data_dir=str(self.data_dir)
        )
        
        health = agent.health_check()
        
        self.assertEqual(health["agent_id"], "test_health")
        self.assertEqual(health["agent_name"], "Trend Harvester Agent")
        self.assertEqual(health["status"], "stopped")  # Not started yet
        self.assertIn("data_dir", health)
        self.assertIn("ledgers", health)
    
    def test_agent_statistics(self):
        """Test agent statistics collection."""
        agent = create_trend_harvester_agent(
            agent_id="test_stats",
            data_dir=str(self.data_dir)
        )
        
        # Log some operations
        agent._log_operation("test_op", "success", {"test": "data"})
        agent._log_operation("test_op", "failure", {"error": "test error"})
        
        stats = agent.get_stats()
        
        self.assertEqual(stats["agent_id"], "test_stats")
        self.assertEqual(stats["operations_total"], 2)
        self.assertEqual(stats["operations_success"], 1)
        self.assertEqual(stats["operations_failure"], 1)
    
    async def _test_async_agent_start_stop(self):
        """Test async agent start/stop (helper for async test)."""
        agent = create_trend_harvester_agent(
            agent_id="test_async",
            data_dir=str(self.data_dir),
            research_interval_minutes=1
        )
        
        # Start agent
        success = await agent.start()
        self.assertTrue(success)
        self.assertTrue(agent.is_running)
        
        # Check health after start
        health = agent.health_check()
        self.assertEqual(health["status"], "running")
        
        # Stop agent
        success = await agent.stop()
        self.assertTrue(success)
        self.assertFalse(agent.is_running)
        
        # Check health after stop
        health = agent.health_check()
        self.assertEqual(health["status"], "stopped")
    
    def test_async_agent_lifecycle(self):
        """Test agent async lifecycle."""
        # Run async test
        asyncio.run(self._test_async_agent_start_stop())
    
    def test_content_opportunity_score_calculation(self):
        """Test content opportunity score calculation."""
        agent = create_trend_harvester_agent(
            agent_id="test_cos",
            data_dir=str(self.data_dir)
        )
        
        # Test COS calculation
        cos = agent._calculate_content_opportunity_score(
            demand=80.0,
            monetization=70.0,
            content_fit=60.0,
            distribution_fit=90.0,
            competition=40.0,
            compliance_risk=20.0,
            production_cost=30.0
        )
        
        self.assertIsNotNone(cos)
        self.assertIsInstance(cos.final_score, float)
        self.assertIn(cos.recommendation, ["proceed", "review", "reject"])
        self.assertGreaterEqual(cos.confidence, 0)
        self.assertLessEqual(cos.confidence, 100)
    
    def test_mock_data_loading(self):
        """Test that agents load mock data correctly."""
        trend_agent = create_trend_harvester_agent(
            agent_id="test_mock",
            data_dir=str(self.data_dir)
        )
        
        # Check mock trends
        self.assertIsInstance(trend_agent.mock_trends, list)
        self.assertGreater(len(trend_agent.mock_trends), 0)
        
        # Check mock offers
        self.assertIsInstance(trend_agent.mock_offers, list)
        self.assertGreater(len(trend_agent.mock_offers), 0)
        
        # Check that trends have required fields
        for trend in trend_agent.mock_trends:
            self.assertIn("topic", trend)
            self.assertIn("platforms", trend)
            self.assertIn("trend_score", trend)
    
    def test_agent_intent_handling(self):
        """Test agent intent handling (mock)."""
        script_agent = create_script_agent(
            agent_id="test_intent",
            data_dir=str(self.data_dir)
        )
        
        # Test intent handling
        intent_data = {
            "brief_id": "test_brief_123",
            "title": "Test Intent",
            "content_angle": "review"
        }
        
        # This would normally be async, but we're testing the sync wrapper
        # For now, just verify the method exists
        self.assertTrue(hasattr(script_agent, 'handle_intent'))
    
    def test_agent_configuration_persistence(self):
        """Test agent configuration and persistence."""
        # Create multiple agents with different configs
        agents = [
            create_trend_harvester_agent(
                agent_id=f"agent_{i}",
                data_dir=str(self.data_dir),
                research_interval_minutes=i+1
            )
            for i in range(3)
        ]
        
        # Verify each has unique config
        for i, agent in enumerate(agents):
            self.assertEqual(agent.agent_id, f"agent_{i}")
            # Research interval is not exposed, but we can check agent_id
        
        # Verify data files were created
        data_files = list(self.data_dir.glob("*.jsonl"))
        self.assertGreater(len(data_files), 0)


if __name__ == "__main__":
    unittest.main()