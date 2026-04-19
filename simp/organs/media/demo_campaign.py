"""
Demo campaign for KashClaw Media Grid.

Demonstrates the complete content creation pipeline with a sample campaign.
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from simp.organs.media.orchestration import MediaGridOrchestrator
from simp.organs.media.config import get_config, MediaEnvironment


class DemoCampaign:
    """Demo campaign showcasing the media grid capabilities."""
    
    def __init__(self, data_dir: str = "data/media_demo"):
        """Initialize demo campaign."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Use development config
        self.config = get_config(MediaEnvironment.DEVELOPMENT)
        self.config.data_dir = str(self.data_dir)
        self.config.max_content_per_day = 3
        self.config.daily_budget = 25.0
        
        # Demo campaign configuration
        self.campaign_config = {
            "name": "AI Tools Showcase Campaign",
            "description": "Demo campaign showcasing AI tool reviews and tutorials",
            "duration_days": 7,
            "target_niches": ["ai_tools", "productivity", "creator_tools"],
            "target_platforms": ["tiktok", "youtube_shorts", "instagram_reels"],
            "content_types": ["review", "tutorial", "comparison"],
            "goals": {
                "content_pieces": 10,
                "target_views": 50000,
                "target_engagement": 5.0,  # percentage
                "target_revenue": 100.0  # USD
            }
        }
        
        # Demo offers
        self.demo_offers = [
            {
                "name": "Higgsfield AI",
                "description": "Cinematic AI video generation platform",
                "category": "ai_tools",
                "commission_rate": 30.0,
                "average_payout": 45.0,
                "affiliate_link": "https://higgsfield.ai/ref/kashclaw_demo",
                "tags": ["ai", "video", "premium", "creators"]
            },
            {
                "name": "Notion AI",
                "description": "AI-powered workspace for notes and projects",
                "category": "productivity",
                "commission_rate": 20.0,
                "average_payout": 30.0,
                "affiliate_link": "https://notion.so/ref/kashclaw_demo",
                "tags": ["productivity", "notes", "organization", "ai"]
            },
            {
                "name": "Carrd",
                "description": "Simple one-page website builder",
                "category": "creator_tools",
                "commission_rate": 35.0,
                "average_payout": 25.0,
                "affiliate_link": "https://carrd.co/ref/kashclaw_demo",
                "tags": ["website", "landing page", "simple", "portfolio"]
            }
        ]
        
        # Demo content ideas
        self.demo_content_ideas = [
            {
                "title": "Create AI Videos in 60 Seconds",
                "angle": "tutorial",
                "platforms": ["tiktok", "youtube_shorts"],
                "offer": "Higgsfield AI",
                "keywords": ["ai video", "text to video", "video generation", "content creation"]
            },
            {
                "title": "Notion AI vs Traditional Note-taking",
                "angle": "comparison",
                "platforms": ["youtube_shorts", "instagram_reels"],
                "offer": "Notion AI",
                "keywords": ["notion", "productivity", "ai notes", "organization"]
            },
            {
                "title": "One-Page Websites for Creators",
                "angle": "review",
                "platforms": ["tiktok", "instagram_reels"],
                "offer": "Carrd",
                "keywords": ["website", "portfolio", "landing page", "creator tools"]
            },
            {
                "title": "AI Tools That Actually Save Time",
                "angle": "tips",
                "platforms": ["tiktok", "youtube_shorts"],
                "offer": "Higgsfield AI",
                "keywords": ["ai tools", "time saving", "efficiency", "workflow"]
            },
            {
                "title": "From Idea to Landing Page in 10 Minutes",
                "angle": "tutorial",
                "platforms": ["instagram_reels", "youtube_shorts"],
                "offer": "Carrd",
                "keywords": ["landing page", "quick website", "online presence", "business"]
            }
        ]
    
    async def run(self):
        """Run the demo campaign."""
        print("=" * 60)
        print("KASHCLAW MEDIA GRID - DEMO CAMPAIGN")
        print("=" * 60)
        print(f"Campaign: {self.campaign_config['name']}")
        print(f"Duration: {self.campaign_config['duration_days']} days")
        print(f"Data Directory: {self.data_dir}")
        print("=" * 60)
        
        # Initialize orchestrator
        print("\n1. Initializing Media Grid Orchestrator...")
        orchestrator = MediaGridOrchestrator(self.config)
        
        success = await orchestrator.initialize()
        if not success:
            print("❌ Failed to initialize Media Grid")
            return
        
        print("✅ Media Grid initialized successfully")
        
        # Start orchestrator
        print("\n2. Starting Media Grid...")
        success = await orchestrator.start()
        if not success:
            print("❌ Failed to start Media Grid")
            return
        
        print("✅ Media Grid started successfully")
        
        # Run demo workflows
        try:
            await self._run_demo_workflows(orchestrator)
        finally:
            # Stop orchestrator
            print("\n5. Stopping Media Grid...")
            await orchestrator.stop()
            print("✅ Media Grid stopped")
    
    async def _run_demo_workflows(self, orchestrator):
        """Run demo workflows."""
        print("\n3. Running Demo Workflows...")
        
        # Workflow 1: Trend Research
        print("\n   Workflow 1: Trend Research")
        print("   " + "-" * 40)
        
        trend_results = await orchestrator.execute_workflow(
            "trend_research",
            limit=3
        )
        
        if trend_results.get("status") == "success":
            result = trend_results.get("result", {})
            print(f"   ✅ Generated {result.get('briefs_generated', 0)} content briefs")
            print(f"   ✅ Found {result.get('high_opportunity_briefs', 0)} high-opportunity briefs")
            
            # Show sample briefs
            briefs = result.get("briefs", [])
            if briefs:
                print("\n   Sample Briefs:")
                for i, brief in enumerate(briefs[:2], 1):
                    print(f"   {i}. {brief.get('title', 'Unknown')}")
                    print(f"      Score: {brief.get('score', 0):.1f}")
                    print(f"      Est. Revenue: ${brief.get('estimated_revenue', 0):.2f}")
        else:
            print(f"   ❌ Trend research failed: {trend_results.get('error', 'Unknown error')}")
        
        # Workflow 2: Performance Analysis
        print("\n   Workflow 2: Performance Analysis")
        print("   " + "-" * 40)
        
        # First, simulate some metrics for the demo
        await self._simulate_demo_metrics(orchestrator)
        
        analysis_results = await orchestrator.execute_workflow(
            "performance_analysis",
            days_back=1
        )
        
        if analysis_results.get("status") == "success":
            result = analysis_results.get("result", {})
            analysis = result.get("analysis", {})
            
            if analysis.get("status") == "success":
                stats = analysis.get("overall_statistics", {})
                print(f"   ✅ Analyzed {stats.get('total_posts_analyzed', 0)} posts")
                print(f"   ✅ Total Revenue: ${stats.get('total_revenue', 0):.2f}")
                print(f"   ✅ Overall ROI: {stats.get('overall_roi', 0):.1f}%")
                
                # Show recommendations
                recommendations = result.get("recommendations", [])
                if recommendations:
                    print(f"\n   Generated {len(recommendations)} recommendations")
                    for i, rec in enumerate(recommendations[:2], 1):
                        print(f"   {i}. {rec.get('message', 'No message')}")
            else:
                print(f"   ⚠️ No data for analysis: {analysis.get('message', 'Unknown')}")
        else:
            print(f"   ⚠️ Performance analysis skipped (no data yet)")
        
        # Workflow 3: Full Pipeline (simulated)
        print("\n   Workflow 3: Content Creation Pipeline (Simulated)")
        print("   " + "-" * 40)
        
        print("   Simulating content creation pipeline...")
        
        # Simulate each step
        steps = [
            ("Research", "Finding trending topics and offers"),
            ("Scripting", "Generating engaging scripts"),
            ("Asset Creation", "Creating video/assets with AI tools"),
            ("Packaging", "Formatting for different platforms"),
            ("Publishing", "Posting to social media"),
            ("Tracking", "Monitoring performance and revenue")
        ]
        
        for step_name, step_desc in steps:
            print(f"   • {step_name}: {step_desc}")
            await asyncio.sleep(0.5)  # Simulate processing time
        
        print("   ✅ Pipeline simulation complete")
        
        # Show campaign summary
        print("\n4. Campaign Summary")
        print("   " + "-" * 40)
        await self._show_campaign_summary(orchestrator)
    
    async def _simulate_demo_metrics(self, orchestrator):
        """Simulate demo metrics for the campaign."""
        try:
            # Get analytics agent
            analytics_agent = orchestrator.agents.get("analytics_agent")
            if not analytics_agent:
                return
            
            # Create demo metrics
            demo_metrics = [
                {
                    "post_id": "post_demo_1",
                    "views": 1250,
                    "likes": 85,
                    "shares": 12,
                    "comments": 7,
                    "clicks": 38,
                    "conversions": 2,
                    "revenue": 90.0,
                    "total_cost": 15.0,
                    "collected_at": datetime.utcnow().isoformat()
                },
                {
                    "post_id": "post_demo_2",
                    "views": 850,
                    "likes": 62,
                    "shares": 8,
                    "comments": 4,
                    "clicks": 25,
                    "conversions": 1,
                    "revenue": 45.0,
                    "total_cost": 12.0,
                    "collected_at": datetime.utcnow().isoformat()
                },
                {
                    "post_id": "post_demo_3",
                    "views": 2100,
                    "likes": 145,
                    "shares": 21,
                    "comments": 15,
                    "clicks": 63,
                    "conversions": 3,
                    "revenue": 135.0,
                    "total_cost": 18.0,
                    "collected_at": datetime.utcnow().isoformat()
                }
            ]
            
            # Save demo metrics
            for metrics in demo_metrics:
                analytics_agent._append_to_ledger("performance_metrics", metrics)
            
            # Create demo published posts
            publisher_agent = orchestrator.agents.get("publisher_agent")
            if publisher_agent:
                demo_posts = [
                    {
                        "post_id": "post_demo_1",
                        "platform": "tiktok",
                        "platform_post_id": "tiktok_123456",
                        "published_at": datetime.utcnow().isoformat(),
                        "initial_views": 1250,
                        "initial_likes": 85
                    },
                    {
                        "post_id": "post_demo_2",
                        "platform": "youtube_shorts",
                        "platform_post_id": "shorts_789012",
                        "published_at": datetime.utcnow().isoformat(),
                        "initial_views": 850,
                        "initial_likes": 62
                    },
                    {
                        "post_id": "post_demo_3",
                        "platform": "instagram_reels",
                        "platform_post_id": "reel_345678",
                        "published_at": datetime.utcnow().isoformat(),
                        "initial_views": 2100,
                        "initial_likes": 145
                    }
                ]
                
                for post in demo_posts:
                    publisher_agent._append_to_ledger("published_posts", post)
            
        except Exception as e:
            print(f"   ⚠️ Error simulating demo metrics: {e}")
    
    async def _show_campaign_summary(self, orchestrator):
        """Show campaign summary."""
        try:
            # Get metrics
            metrics = await orchestrator.collect_metrics()
            
            # Campaign statistics
            total_content = metrics["orchestrator"].get("content_published", 0)
            total_revenue = metrics["orchestrator"].get("revenue_generated", 0)
            total_workflows = metrics["orchestrator"].get("workflows_completed", 0)
            
            # Agent status
            agent_status = []
            for agent_name, agent in orchestrator.agents.items():
                if hasattr(agent, 'is_running') and agent.is_running:
                    agent_status.append(f"{agent_name}: ✅")
                else:
                    agent_status.append(f"{agent_name}: ❌")
            
            print(f"   Campaign Duration: {self.campaign_config['duration_days']} days")
            print(f"   Content Created: {total_content} pieces")
            print(f"   Revenue Generated: ${total_revenue:.2f}")
            print(f"   Workflows Executed: {total_workflows}")
            print(f"   Agents Status: {', '.join(agent_status)}")
            
            # Demo offers
            print("\n   Demo Offers:")
            for offer in self.demo_offers[:3]:
                print(f"   • {offer['name']} ({offer['category']})")
                print(f"     Commission: {offer['commission_rate']}%")
                print(f"     Avg. Payout: ${offer['average_payout']}")
            
            # Next steps
            print("\n   Next Steps for Production:")
            print("   1. Configure real API keys for AI tools")
            print("   2. Set up social media platform authentication")
            print("   3. Integrate with affiliate networks")
            print("   4. Configure compliance and disclosure requirements")
            print("   5. Set up monitoring and alerting")
            
        except Exception as e:
            print(f"   Error generating summary: {e}")
    
    def save_campaign_report(self):
        """Save campaign report to file."""
        report = {
            "campaign": self.campaign_config,
            "demo_offers": self.demo_offers,
            "content_ideas": self.demo_content_ideas,
            "generated_at": datetime.utcnow().isoformat(),
            "data_directory": str(self.data_dir)
        }
        
        report_file = self.data_dir / "campaign_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Campaign report saved to: {report_file}")
        return report_file


async def main():
    """Main function to run the demo campaign."""
    print("Starting KashClaw Media Grid Demo Campaign...")
    
    # Create and run demo campaign
    demo = DemoCampaign()
    
    try:
        await demo.run()
        
        # Save campaign report
        report_file = demo.save_campaign_report()
        
        print("\n" + "=" * 60)
        print("DEMO CAMPAIGN COMPLETE!")
        print("=" * 60)
        print("\nThe KashClaw Media Grid system includes:")
        print("• 6 specialized agents for content creation pipeline")
        print("• AI-powered video/image/audio generation")
        print("• Multi-platform publishing and scheduling")
        print("• Performance analytics and optimization")
        print("• Affiliate monetization tracking")
        print("• Compliance and risk management")
        print(f"\nDemo data saved to: {demo.data_dir}")
        print(f"Campaign report: {report_file}")
        print("\nTo run in production:")
        print("1. Configure API keys in config.py")
        print("2. Set up platform authentication")
        print("3. Enable real affiliate networks")
        print("4. Run: python -m simp.organs.media.orchestration")
        
    except KeyboardInterrupt:
        print("\n\nDemo campaign interrupted by user")
    except Exception as e:
        print(f"\nError running demo campaign: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())