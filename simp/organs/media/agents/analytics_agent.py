"""
Analytics Agent for KashClaw Media Grid.

Responsible for:
- Tracking performance metrics across platforms
- Monitoring engagement, clicks, conversions, revenue
- Calculating ROI and performance scores
- Generating optimization recommendations
- Providing A/B testing analysis
"""
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    PerformanceMetrics, PublishedPost, ContentPlatform
)


class AnalyticsAgent(BaseMediaAgent):
    """Agent that tracks and analyzes content performance."""
    
    def __init__(
        self,
        agent_id: str = "analytics_agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        analysis_interval_minutes: int = 60
    ):
        """Initialize the Analytics Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Analytics Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.analysis_interval_minutes = analysis_interval_minutes
        self.last_analysis_time = None
        self.pending_posts = asyncio.Queue()
        self.active_tracking: Dict[str, Dict[str, Any]] = {}
        
        # Performance benchmarks
        self.benchmarks = self._load_performance_benchmarks()
        
        # Optimization rules
        self.optimization_rules = self._load_optimization_rules()
        
        self.logger.info(f"Analytics Agent initialized with {analysis_interval_minutes}min analysis interval")
    
    def _load_performance_benchmarks(self) -> Dict[str, Dict[str, float]]:
        """Load performance benchmarks for different platforms."""
        return {
            "tiktok": {
                "avg_view_rate": 0.03,  # 3% of followers see post
                "avg_engagement_rate": 0.05,  # 5% engagement rate
                "avg_ctr": 0.02,  # 2% click-through rate
                "avg_conversion_rate": 0.001,  # 0.1% conversion rate
                "avg_cpm": 10.0,  # $10 CPM
                "avg_epc": 0.50  # $0.50 earnings per click
            },
            "youtube_shorts": {
                "avg_view_rate": 0.10,
                "avg_engagement_rate": 0.03,
                "avg_ctr": 0.015,
                "avg_conversion_rate": 0.0008,
                "avg_cpm": 15.0,
                "avg_epc": 0.75
            },
            "instagram_reels": {
                "avg_view_rate": 0.05,
                "avg_engagement_rate": 0.04,
                "avg_ctr": 0.01,
                "avg_conversion_rate": 0.0005,
                "avg_cpm": 12.0,
                "avg_epc": 0.60
            },
            "x": {
                "avg_view_rate": 0.02,
                "avg_engagement_rate": 0.01,
                "avg_ctr": 0.005,
                "avg_conversion_rate": 0.0003,
                "avg_cpm": 8.0,
                "avg_epc": 0.40
            }
        }
    
    def _load_optimization_rules(self) -> List[Dict[str, Any]]:
        """Load optimization rules for content improvement."""
        return [
            {
                "condition": "engagement_rate < benchmark * 0.5",
                "action": "improve_hook",
                "priority": "high",
                "message": "Engagement rate is below 50% of benchmark. Improve hook in first 3 seconds."
            },
            {
                "condition": "ctr < benchmark * 0.3",
                "action": "improve_cta",
                "priority": "high",
                "message": "Click-through rate is very low. Test different call-to-action variants."
            },
            {
                "condition": "conversion_rate > benchmark * 2",
                "action": "scale_content",
                "priority": "medium",
                "message": "High conversion rate detected. Consider creating similar content or scaling budget."
            },
            {
                "condition": "watch_time < duration * 0.3",
                "action": "shorten_content",
                "priority": "medium",
                "message": "Low watch time. Consider shortening content or improving pacing."
            },
            {
                "condition": "roi < 0",
                "action": "review_strategy",
                "priority": "critical",
                "message": "Negative ROI detected. Review content strategy and costs."
            },
            {
                "condition": "views > benchmark * 3",
                "action": "analyze_virality",
                "priority": "low",
                "message": "High view count. Analyze what made this content perform well."
            }
        ]
    
    async def _process_loop(self):
        """Main processing loop for analytics."""
        while self.is_running:
            try:
                # Check for pending posts to track
                if not self.pending_posts.empty():
                    post_data = await self.pending_posts.get()
                    
                    self.logger.info(f"Starting tracking for post: {post_data.get('post_id', 'unknown')}")
                    
                    # Start tracking post performance
                    await self.start_tracking_post(post_data)
                    
                    self.pending_posts.task_done()
                
                # Update tracking for active posts
                await self._update_active_tracking()
                
                # Check if it's time for periodic analysis
                should_analyze = self._should_do_analysis()
                
                if should_analyze:
                    self.logger.info("Starting periodic performance analysis")
                    
                    # Run comprehensive analysis
                    analysis_results = await self.run_performance_analysis()
                    
                    # Generate optimization recommendations
                    recommendations = await self.generate_optimization_recommendations(analysis_results)
                    
                    # Update last analysis time
                    self.last_analysis_time = datetime.utcnow()
                    
                    self.logger.info(f"Analysis complete: {len(recommendations)} recommendations generated")
                
                # Wait before next check
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in analytics loop: {e}")
                await asyncio.sleep(60)
    
    async def _update_active_tracking(self):
        """Update tracking for active posts."""
        posts_to_remove = []
        
        for post_id, tracking_info in self.active_tracking.items():
            try:
                # Check if tracking period is over (e.g., 7 days)
                start_time = datetime.fromisoformat(tracking_info.get("started_at", ""))
                days_tracked = (datetime.utcnow() - start_time).days
                
                if days_tracked >= 7:  # Track for 7 days
                    posts_to_remove.append(post_id)
                    self.logger.info(f"Stopped tracking post {post_id} after {days_tracked} days")
                else:
                    # Update metrics (simulated)
                    await self._update_post_metrics(post_id, tracking_info)
            
            except Exception as e:
                self.logger.error(f"Error updating tracking for post {post_id}: {e}")
                posts_to_remove.append(post_id)
        
        # Remove completed tracking
        for post_id in posts_to_remove:
            if post_id in self.active_tracking:
                del self.active_tracking[post_id]
    
    async def _update_post_metrics(self, post_id: str, tracking_info: Dict[str, Any]):
        """Update metrics for a tracked post (simulated)."""
        try:
            # Simulate metric updates
            # In real implementation, this would query platform APIs
            
            # Get current metrics
            metrics_list = self._find_in_ledger("performance_metrics", "post_id", post_id, limit=1)
            current_metrics = metrics_list[0] if metrics_list else {}
            
            # Generate updated metrics
            platform = tracking_info.get("platform", "unknown")
            benchmark = self.benchmarks.get(platform, {})
            
            # Simulate growth
            views_growth = random.randint(10, 100)
            likes_growth = random.randint(1, 10)
            shares_growth = random.randint(0, 5)
            comments_growth = random.randint(0, 3)
            
            # Simulate clicks and conversions (with some randomness)
            click_probability = benchmark.get("avg_ctr", 0.01)
            conversion_probability = benchmark.get("avg_conversion_rate", 0.001)
            
            clicks_growth = int(views_growth * click_probability * random.uniform(0.5, 1.5))
            conversions_growth = int(clicks_growth * conversion_probability * random.uniform(0.5, 1.5))
            
            # Calculate revenue
            epc = benchmark.get("avg_epc", 0.50)
            revenue_growth = conversions_growth * epc * random.uniform(0.8, 1.2)
            
            # Create updated metrics
            updated_metrics = PerformanceMetrics(
                metrics_id=f"metrics_{post_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                post_id=post_id,
                views=current_metrics.get("views", 0) + views_growth,
                likes=current_metrics.get("likes", 0) + likes_growth,
                shares=current_metrics.get("shares", 0) + shares_growth,
                comments=current_metrics.get("comments", 0) + comments_growth,
                clicks=current_metrics.get("clicks", 0) + clicks_growth,
                conversions=current_metrics.get("conversions", 0) + conversions_growth,
                revenue=current_metrics.get("revenue", 0) + revenue_growth
            )
            
            # Calculate derived metrics
            total_views = updated_metrics.views
            total_clicks = updated_metrics.clicks
            total_conversions = updated_metrics.conversions
            
            if total_views > 0:
                updated_metrics.click_through_rate = (total_clicks / total_views) * 100
                updated_metrics.watch_time_seconds = total_views * random.uniform(10, 30)  # Simulated
                updated_metrics.completion_rate = random.uniform(0.3, 0.8) * 100
            
            if total_clicks > 0:
                updated_metrics.conversion_rate = (total_conversions / total_clicks) * 100
                updated_metrics.revenue_per_click = updated_metrics.revenue / total_clicks if total_clicks > 0 else 0
            
            if total_conversions > 0:
                updated_metrics.cost_per_conversion = random.uniform(5, 20)  # Simulated
            
            # Calculate ROI
            # Simulate costs
            content_production_cost = random.uniform(5, 15)
            promotion_cost = random.uniform(0, 10)
            updated_metrics.content_production_cost = content_production_cost
            updated_metrics.promotion_cost = promotion_cost
            updated_metrics.total_cost = content_production_cost + promotion_cost
            
            if updated_metrics.total_cost > 0:
                updated_metrics.return_on_investment = ((updated_metrics.revenue - updated_metrics.total_cost) / updated_metrics.total_cost) * 100
            
            if total_views > 0:
                updated_metrics.revenue_per_view = updated_metrics.revenue / total_views
            
            # Save updated metrics
            self._save_performance_metrics(updated_metrics)
            
            self.logger.debug(f"Updated metrics for post {post_id}: {views_growth} new views, ${revenue_growth:.2f} revenue")
            
        except Exception as e:
            self.logger.error(f"Error updating metrics for post {post_id}: {e}")
    
    def _should_do_analysis(self) -> bool:
        """Determine if it's time to do analysis based on interval."""
        if self.last_analysis_time is None:
            return True
        
        time_since_last = datetime.utcnow() - self.last_analysis_time
        return time_since_last.total_seconds() >= (self.analysis_interval_minutes * 60)
    
    async def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intent for performance tracking.
        
        Args:
            intent_data: Intent payload with post information
            
        Returns:
            Response with tracking status
        """
        operation_id = self._log_operation(
            operation="performance_tracking_intent",
            status="pending",
            details={"post_id": intent_data.get("post_id", "unknown")}
        )
        
        try:
            # Add to processing queue
            await self.pending_posts.put(intent_data)
            
            self._log_operation(
                operation="performance_tracking_intent",
                status="success",
                details={
                    "post_id": intent_data.get("post_id", "unknown"),
                    "queue_position": self.pending_posts.qsize()
                }
            )
            
            return {
                "status": "queued",
                "operation_id": operation_id,
                "queue_position": self.pending_posts.qsize(),
                "estimated_wait": self.pending_posts.qsize() * 10  # 10 seconds per post
            }
            
        except Exception as e:
            self._log_operation(
                operation="performance_tracking_intent",
                status="failure",
                details={"error": str(e)}
            )
            
            return {
                "status": "error",
                "operation_id": operation_id,
                "error": str(e)
            }
    
    async def start_tracking_post(self, post_data: Dict[str, Any]) -> bool:
        """
        Start tracking performance for a published post.
        
        Args:
            post_data: Post data from Publisher Agent
            
        Returns:
            True if tracking started successfully
        """
        operation_id = self._log_operation(
            operation="start_tracking",
            status="pending",
            details={"post_id": post_data.get("post_id", "unknown")}
        )
        
        start_time = time.time()
        
        try:
            post_id = post_data.get("post_id", "")
            platform = post_data.get("platform", "")
            
            # Add to active tracking
            self.active_tracking[post_id] = {
                "post_id": post_id,
                "platform": platform,
                "started_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat(),
                "initial_metrics": post_data.get("initial_metrics", {})
            }
            
            # Create initial performance metrics
            initial_metrics = PerformanceMetrics(
                metrics_id=f"metrics_{post_id}_initial",
                post_id=post_id,
                views=post_data.get("initial_metrics", {}).get("views", 0),
                likes=post_data.get("initial_metrics", {}).get("likes", 0),
                shares=post_data.get("initial_metrics", {}).get("shares", 0),
                comments=post_data.get("initial_metrics", {}).get("comments", 0)
            )
            
            # Save initial metrics
            self._save_performance_metrics(initial_metrics)
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="start_tracking",
                status="success",
                details={
                    "post_id": post_id,
                    "platform": platform,
                    "tracking_duration_days": 7
                },
                duration_seconds=duration
            )
            
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="start_tracking",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to start tracking for post {post_data.get('post_id', 'unknown')}: {e}")
            return False
    
    async def run_performance_analysis(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Run comprehensive performance analysis.
        
        Args:
            days_back: How many days back to analyze
            
        Returns:
            Analysis results
        """
        operation_id = self._log_operation(
            operation="performance_analysis",
            status="pending",
            details={"days_back": days_back}
        )
        
        start_time = time.time()
        
        try:
            # Get performance metrics from the specified period
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            
            # Read all metrics and filter by date
            all_metrics = self._read_ledger("performance_metrics", limit=1000)
            recent_metrics = [
                m for m in all_metrics 
                if m.get("collected_at", "") >= cutoff_date
            ]
            
            if not recent_metrics:
                self.logger.warning(f"No metrics found for analysis period (last {days_back} days)")
                return {"status": "no_data", "message": "No metrics available for analysis"}
            
            # Get associated posts
            all_posts = self._read_ledger("published_posts", limit=1000)
            
            # Calculate overall statistics
            total_posts = len(set(m.get("post_id") for m in recent_metrics))
            total_views = sum(m.get("views", 0) for m in recent_metrics)
            total_revenue = sum(m.get("revenue", 0) for m in recent_metrics)
            total_cost = sum(m.get("total_cost", 0) for m in recent_metrics)
            
            # Calculate averages
            avg_views = total_views / len(recent_metrics) if recent_metrics else 0
            avg_revenue = total_revenue / len(recent_metrics) if recent_metrics else 0
            avg_cost = total_cost / len(recent_metrics) if recent_metrics else 0
            
            # Calculate ROI
            overall_roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
            
            # Platform performance
            platform_performance = {}
            for platform in self.benchmarks.keys():
                platform_metrics = [m for m in recent_metrics 
                                  if self._get_post_platform(m.get("post_id", ""), all_posts) == platform]
                
                if platform_metrics:
                    platform_views = sum(m.get("views", 0) for m in platform_metrics)
                    platform_revenue = sum(m.get("revenue", 0) for m in platform_metrics)
                    platform_cost = sum(m.get("total_cost", 0) for m in platform_metrics)
                    
                    platform_roi = ((platform_revenue - platform_cost) / platform_cost * 100) if platform_cost > 0 else 0
                    
                    platform_performance[platform] = {
                        "posts": len(platform_metrics),
                        "total_views": platform_views,
                        "total_revenue": platform_revenue,
                        "total_cost": platform_cost,
                        "roi": platform_roi,
                        "avg_views_per_post": platform_views / len(platform_metrics) if platform_metrics else 0,
                        "avg_revenue_per_post": platform_revenue / len(platform_metrics) if platform_metrics else 0
                    }
            
            # Top performing posts
            posts_with_revenue = []
            for metrics in recent_metrics:
                post_id = metrics.get("post_id", "")
                revenue = metrics.get("revenue", 0)
                cost = metrics.get("total_cost", 0)
                roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
                
                posts_with_revenue.append({
                    "post_id": post_id,
                    "revenue": revenue,
                    "cost": cost,
                    "roi": roi,
                    "views": metrics.get("views", 0)
                })
            
            # Sort by ROI (descending)
            posts_with_revenue.sort(key=lambda x: x.get("roi", 0), reverse=True)
            top_performers = posts_with_revenue[:10]
            
            # Identify underperforming posts
            underperformers = [p for p in posts_with_revenue if p.get("roi", 0) < 0][:10]
            
            # Calculate content decay (how performance changes over time)
            content_decay = self._calculate_content_decay(recent_metrics, all_posts)
            
            duration = time.time() - start_time
            
            analysis_results = {
                "period": f"last_{days_back}_days",
                "overall_statistics": {
                    "total_posts_analyzed": total_posts,
                    "total_metrics_points": len(recent_metrics),
                    "total_views": total_views,
                    "total_revenue": total_revenue,
                    "total_cost": total_cost,
                    "overall_roi": overall_roi,
                    "average_views": avg_views,
                    "average_revenue": avg_revenue,
                    "average_cost": avg_cost
                },
                "platform_performance": platform_performance,
                "top_performers": top_performers,
                "underperformers": underperformers,
                "content_decay_analysis": content_decay,
                "benchmark_comparison": self._compare_to_benchmarks(platform_performance)
            }
            
            self._log_operation(
                operation="performance_analysis",
                status="success",
                details={
                    "posts_analyzed": total_posts,
                    "metrics_analyzed": len(recent_metrics),
                    "top_performers_found": len(top_performers),
                    "underperformers_found": len(underperformers)
                },
                duration_seconds=duration
            )
            
            return analysis_results
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="performance_analysis",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to run performance analysis: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_post_platform(self, post_id: str, all_posts: List[Dict[str, Any]]) -> str:
        """Get platform for a post ID."""
        for post in all_posts:
            if post.get("post_id") == post_id:
                return post.get("platform", "unknown")
        return "unknown"
    
    def _calculate_content_decay(
        self,
        metrics: List[Dict[str, Any]],
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate how content performance decays over time."""
        # Group metrics by age
        age_groups = {
            "0-1_hours": [],
            "1-24_hours": [],
            "1-7_days": [],
            "7+_days": []
        }
        
        now = datetime.utcnow()
        
        for metric in metrics:
            collected_at = metric.get("collected_at", "")
            if not collected_at:
                continue
            
            try:
                collected_time = datetime.fromisoformat(collected_at)
                age_hours = (now - collected_time).total_seconds() / 3600
                
                if age_hours <= 1:
                    age_groups["0-1_hours"].append(metric)
                elif age_hours <= 24:
                    age_groups["1-24_hours"].append(metric)
                elif age_hours <= 168:  # 7 days
                    age_groups["1-7_days"].append(metric)
                else:
                    age_groups["7+_days"].append(metric)
            except:
                continue
        
        # Calculate average metrics per age group
        decay_analysis = {}
        for group_name, group_metrics in age_groups.items():
            if group_metrics:
                avg_views = sum(m.get("views", 0) for m in group_metrics) / len(group_metrics)
                avg_engagement = sum(
                    (m.get("likes", 0) + m.get("shares", 0) + m.get("comments", 0)) 
                    for m in group_metrics
                ) / len(group_metrics)
                
                decay_analysis[group_name] = {
                    "metrics_count": len(group_metrics),
                    "average_views": avg_views,
                    "average_engagement": avg_engagement
                }
        
        return decay_analysis
    
    def _compare_to_benchmarks(self, platform_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Compare actual performance to benchmarks."""
        comparison = {}
        
        for platform, performance in platform_performance.items():
            benchmark = self.benchmarks.get(platform, {})
            
            if benchmark and performance.get("posts", 0) > 0:
                actual_avg_views = performance.get("avg_views_per_post", 0)
                benchmark_views = benchmark.get("avg_view_rate", 0.03) * 10000  # Convert to absolute
                
                actual_roi = performance.get("roi", 0)
                # No direct ROI benchmark, but we can compare to positive/negative
                
                comparison[platform] = {
                    "views_vs_benchmark": actual_avg_views / benchmark_views if benchmark_views > 0 else 0,
                    "roi_status": "positive" if actual_roi > 0 else "negative",
                    "performance_rating": self._calculate_performance_rating(actual_avg_views, benchmark_views, actual_roi)
                }
        
        return comparison
    
    def _calculate_performance_rating(
        self,
        actual_views: float,
        benchmark_views: float,
        roi: float
    ) -> str:
        """Calculate performance rating."""
        if benchmark_views == 0:
            return "unknown"
        
        view_ratio = actual_views / benchmark_views
        
        if roi > 100:
            return "excellent"
        elif roi > 0:
            if view_ratio > 1.5:
                return "very_good"
            elif view_ratio > 1.0:
                return "good"
            else:
                return "acceptable"
        else:
            if view_ratio > 1.0:
                return "needs_optimization"
            else:
                return "poor"
    
    async def generate_optimization_recommendations(
        self,
        analysis_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate optimization recommendations based on analysis.
        
        Args:
            analysis_results: Results from performance analysis
            
        Returns:
            List of optimization recommendations
        """
        recommendations = []
        
        try:
            # Check underperformers
            underperformers = analysis_results.get("underperformers", [])
            for post in underperformers[:5]:  # Top 5 underperformers
                post_id = post.get("post_id", "")
                roi = post.get("roi", 0)
                
                if roi < 0:
                    recommendation = {
                        "post_id": post_id,
                        "issue": "negative_roi",
                        "priority": "critical",
                        "action": "review_strategy",
                        "message": f"Post {post_id} has negative ROI ({roi:.1f}%). Review content strategy and costs.",
                        "suggested_actions": [
                            "Analyze cost breakdown",
                            "Review target audience",
                            "Test different content angles",
                            "Consider pausing similar content"
                        ]
                    }
                    recommendations.append(recommendation)
            
            # Check platform performance
            platform_performance = analysis_results.get("platform_performance", {})
            for platform, performance in platform_performance.items():
                roi = performance.get("roi", 0)
                
                if roi < 0:
                    recommendation = {
                        "platform": platform,
                        "issue": "platform_negative_roi",
                        "priority": "high",
                        "action": "platform_review",
                        "message": f"Platform {platform} has negative overall ROI ({roi:.1f}%). Consider reallocating budget.",
                        "suggested_actions": [
                            f"Reduce investment in {platform}",
                            "Test different content formats",
                            "Review platform-specific strategy",
                            "Compare with other platforms"
                        ]
                    }
                    recommendations.append(recommendation)
            
            # Apply optimization rules
            benchmark_comparison = analysis_results.get("benchmark_comparison", {})
            for platform, comparison in benchmark_comparison.items():
                views_ratio = comparison.get("views_vs_benchmark", 0)
                
                # Check each optimization rule
                for rule in self.optimization_rules:
                    condition = rule.get("condition", "")
                    
                    # Simple condition evaluation (in real implementation, use a proper evaluator)
                    if "engagement_rate" in condition and views_ratio < 0.5:
                        recommendation = {
                            "platform": platform,
                            "issue": "low_engagement",
                            "priority": rule.get("priority", "medium"),
                            "action": rule.get("action", ""),
                            "message": rule.get("message", "").replace("benchmark", f"{views_ratio:.2f}x benchmark"),
                            "suggested_actions": [
                                "Improve hook in first 3 seconds",
                                "Test different content openings",
                                "Analyze competitor engagement strategies"
                            ]
                        }
                        recommendations.append(recommendation)
                        break
            
            # Content decay recommendations
            content_decay = analysis_results.get("content_decay_analysis", {})
            if "7+_days" in content_decay:
                decay_metrics = content_decay["7+_days"]
                if decay_metrics.get("metrics_count", 0) > 10:
                    avg_views_old = decay_metrics.get("average_views", 0)
                    
                    if "0-1_hours" in content_decay:
                        avg_views_new = content_decay["0-1_hours"].get("average_views", 0)
                        
                        if avg_views_new > 0 and avg_views_old / avg_views_new < 0.1:
                            recommendation = {
                                "issue": "rapid_content_decay",
                                "priority": "medium",
                                "action": "improve_longevity",
                                "message": "Content loses 90% of views after 7 days. Focus on evergreen content.",
                                "suggested_actions": [
                                    "Create more evergreen content",
                                    "Improve content depth and value",
                                    "Consider content updates/refreshes",
                                    "Test different content formats"
                                ]
                            }
                            recommendations.append(recommendation)
            
            # Limit to top 10 recommendations
            recommendations = recommendations[:10]
            
            # Save recommendations
            for rec in recommendations:
                rec["generated_at"] = datetime.utcnow().isoformat()
                rec["agent_id"] = self.agent_id
                self._append_to_ledger("optimization_recommendations", rec)
            
            self.logger.info(f"Generated {len(recommendations)} optimization recommendations")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to generate optimization recommendations: {e}")
            return []
    
    def _save_performance_metrics(self, metrics: PerformanceMetrics):
        """Save performance metrics to ledger."""
        from dataclasses import asdict
        
        record = asdict(metrics)
        self._append_to_ledger("performance_metrics", record)
    
    def get_recent_metrics(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent performance metrics."""
        return self._read_ledger("performance_metrics", limit=limit)
    
    def get_recent_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent optimization recommendations."""
        return self._read_ledger("optimization_recommendations", limit=limit)
    
    def get_analytics_statistics(self) -> Dict[str, Any]:
        """Get analytics statistics."""
        metrics = self._read_ledger("performance_metrics", limit=100)
        recommendations = self._read_ledger("optimization_recommendations", limit=100)
        operations = self._read_ledger("operations", limit=100)
        
        if not metrics:
            return {"status": "no_data", "message": "No metrics tracked yet"}
        
        # Calculate statistics
        tracking_operations = [op for op in operations if op.get("operation") == "start_tracking"]
        
        success_count = sum(1 for op in tracking_operations if op.get("status") == "success")
        failure_count = sum(1 for op in tracking_operations if op.get("status") == "failure")
        
        # Active tracking
        active_posts = len(self.active_tracking)
        
        # Revenue statistics
        total_revenue = sum(m.get("revenue", 0) for m in metrics)
        total_cost = sum(m.get("total_cost", 0) for m in metrics)
        total_roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        
        # Recommendation statistics
        recommendation_priorities = {}
        for rec in recommendations:
            priority = rec.get("priority", "unknown")
            recommendation_priorities[priority] = recommendation_priorities.get(priority, 0) + 1
        
        return {
            "status": "success",
            "statistics": {
                "total_metrics_points": len(metrics),
                "tracking_success_rate": f"{(success_count / len(tracking_operations) * 100):.1f}%" if tracking_operations else "0%",
                "active_posts_tracked": active_posts,
                "total_revenue_tracked": f"${total_revenue:.2f}",
                "total_cost_tracked": f"${total_cost:.2f}",
                "overall_roi": f"{total_roi:.1f}%",
                "recommendations_generated": len(recommendations),
                "recommendation_priority_distribution": recommendation_priorities,
                "pending_queue": self.pending_posts.qsize()
            },
            "recent_metrics": metrics[:5],
            "recent_recommendations": recommendations[:5]
        }


# Factory function for creating the agent
def create_analytics_agent(
    agent_id: str = "analytics_agent",
    data_dir: Optional[str] = None,
    analysis_interval_minutes: int = 60
) -> AnalyticsAgent:
    """Create and return an Analytics Agent instance."""
    return AnalyticsAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        analysis_interval_minutes=analysis_interval_minutes
    )