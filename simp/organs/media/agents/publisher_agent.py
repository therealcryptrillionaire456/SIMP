"""
Publisher Agent for KashClaw Media Grid.

Responsible for:
- Posting content to social platforms (TikTok, YouTube, Instagram, X, etc.)
- Handling platform authentication and API integration
- Managing posting schedules and rate limits
- Tracking published posts with unique IDs
- Implementing retry logic for failed posts
"""
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    PublishedPost, ContentPlatform, ContentPackage
)


class PublisherAgent(BaseMediaAgent):
    """Agent that publishes content to social platforms."""
    
    def __init__(
        self,
        agent_id: str = "publisher_agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        max_retries: int = 3,
        retry_delay: int = 60  # seconds
    ):
        """Initialize the Publisher Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Publisher Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pending_packages = asyncio.Queue()
        self.active_publishing: Dict[str, Dict[str, Any]] = {}
        self.platform_clients = self._initialize_platform_clients()
        self.rate_limit_trackers = self._initialize_rate_limit_trackers()
        
        self.logger.info(f"Publisher Agent initialized with {max_retries} max retries")
    
    def _initialize_platform_clients(self) -> Dict[str, Dict[str, Any]]:
        """Initialize mock platform clients."""
        return {
            "tiktok": {
                "name": "TikTok API",
                "base_url": "https://api.tiktok.com/v1",
                "auth_method": "oauth2",
                "rate_limit": 100,  # requests per hour
                "supported_operations": ["publish", "delete", "analytics"],
                "mock_enabled": True
            },
            "youtube_shorts": {
                "name": "YouTube API",
                "base_url": "https://www.googleapis.com/youtube/v3",
                "auth_method": "oauth2",
                "rate_limit": 10000,  # requests per day
                "supported_operations": ["publish", "update", "analytics"],
                "mock_enabled": True
            },
            "instagram_reels": {
                "name": "Instagram Graph API",
                "base_url": "https://graph.instagram.com",
                "auth_method": "oauth2",
                "rate_limit": 200,  # requests per hour
                "supported_operations": ["publish", "delete"],
                "mock_enabled": True
            },
            "x": {
                "name": "X API",
                "base_url": "https://api.twitter.com/2",
                "auth_method": "oauth2",
                "rate_limit": 50,  # requests per 15 minutes
                "supported_operations": ["tweet", "delete", "analytics"],
                "mock_enabled": True
            }
        }
    
    def _initialize_rate_limit_trackers(self) -> Dict[str, Dict[str, Any]]:
        """Initialize rate limit trackers for each platform."""
        trackers = {}
        for platform in self.platform_clients.keys():
            trackers[platform] = {
                "requests_made": 0,
                "window_start": datetime.utcnow().isoformat(),
                "window_duration": 3600,  # 1 hour in seconds
                "limit": self.platform_clients[platform].get("rate_limit", 100)
            }
        return trackers
    
    async def _process_loop(self):
        """Main processing loop for content publishing."""
        while self.is_running:
            try:
                # Check for pending packages
                if not self.pending_packages.empty():
                    package_data = await self.pending_packages.get()
                    
                    self.logger.info(f"Processing package: {package_data.get('package_id', 'unknown')}")
                    
                    # Publish content package
                    published_posts = await self.publish_content_package(package_data)
                    
                    if published_posts:
                        # Save to ledger
                        for post in published_posts:
                            self._save_published_post(post)
                        
                        # Send to Analytics Agent
                        await self._distribute_published_posts(published_posts)
                    
                    self.pending_packages.task_done()
                
                # Process scheduled posts
                await self._process_scheduled_posts()
                
                # Update rate limit trackers
                self._update_rate_limit_trackers()
                
                # Wait before next check
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in publishing loop: {e}")
                await asyncio.sleep(30)
    
    async def _process_scheduled_posts(self):
        """Process posts that are scheduled for future publishing."""
        try:
            # Get scheduled posts from ledger
            published_posts = self._read_ledger("published_posts", limit=100)
            
            now = datetime.utcnow()
            for post in published_posts:
                if post.get("scheduled_publish", False) and not post.get("published", False):
                    scheduled_time = datetime.fromisoformat(post.get("scheduled_time", ""))
                    
                    if scheduled_time <= now:
                        # Time to publish
                        self.logger.info(f"Publishing scheduled post: {post.get('post_id', 'unknown')}")
                        
                        # Update and publish
                        post["scheduled_publish"] = False
                        post["published_at"] = now.isoformat()
                        
                        # In real implementation, would call platform API
                        # For now, just mark as published
                        post["published"] = True
                        
                        # Update ledger
                        self._update_published_post(post)
            
        except Exception as e:
            self.logger.error(f"Error processing scheduled posts: {e}")
    
    def _update_rate_limit_trackers(self):
        """Update rate limit trackers and reset if window expired."""
        now = datetime.utcnow()
        
        for platform, tracker in self.rate_limit_trackers.items():
            window_start = datetime.fromisoformat(tracker["window_start"])
            window_end = window_start + timedelta(seconds=tracker["window_duration"])
            
            if now >= window_end:
                # Reset tracker
                tracker["requests_made"] = 0
                tracker["window_start"] = now.isoformat()
                self.logger.debug(f"Rate limit window reset for {platform}")
    
    def _check_rate_limit(self, platform: str) -> bool:
        """Check if rate limit allows another request."""
        tracker = self.rate_limit_trackers.get(platform)
        if not tracker:
            return True
        
        return tracker["requests_made"] < tracker["limit"]
    
    def _increment_rate_limit(self, platform: str):
        """Increment rate limit counter."""
        tracker = self.rate_limit_trackers.get(platform)
        if tracker:
            tracker["requests_made"] += 1
    
    async def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intent for content publishing.
        
        Args:
            intent_data: Intent payload with package information
            
        Returns:
            Response with publishing status
        """
        operation_id = self._log_operation(
            operation="content_publishing_intent",
            status="pending",
            details={"package_id": intent_data.get("package_id", "unknown")}
        )
        
        try:
            # Add to processing queue
            await self.pending_packages.put(intent_data)
            
            self._log_operation(
                operation="content_publishing_intent",
                status="success",
                details={
                    "package_id": intent_data.get("package_id", "unknown"),
                    "queue_position": self.pending_packages.qsize()
                }
            )
            
            return {
                "status": "queued",
                "operation_id": operation_id,
                "queue_position": self.pending_packages.qsize(),
                "estimated_wait": self.pending_packages.qsize() * 60  # 60 seconds per package
            }
            
        except Exception as e:
            self._log_operation(
                operation="content_publishing_intent",
                status="failure",
                details={"error": str(e)}
            )
            
            return {
                "status": "error",
                "operation_id": operation_id,
                "error": str(e)
            }
    
    async def publish_content_package(
        self,
        package_data: Dict[str, Any]
    ) -> List[PublishedPost]:
        """
        Publish a content package to platforms.
        
        Args:
            package_data: Content package data
            
        Returns:
            List of PublishedPost objects
        """
        operation_id = self._log_operation(
            operation="content_publishing",
            status="pending",
            details={"package_id": package_data.get("package_id", "unknown")}
        )
        
        start_time = time.time()
        
        try:
            # Extract package information
            package_id = package_data.get("package_id", "")
            brief_id = package_data.get("brief_id", "")
            script_id = package_data.get("script_id", "")
            platform_packages = package_data.get("platform_packages", {})
            captions = package_data.get("captions", {})
            hashtags = package_data.get("hashtags", {})
            posting_schedule = package_data.get("posting_schedule", {})
            compliance_check_passed = package_data.get("compliance_check_passed", False)
            disclosures_included = package_data.get("disclosures_included", False)
            
            if not platform_packages:
                self.logger.warning(f"No platform packages in package {package_id}")
                return []
            
            # Check compliance
            if not compliance_check_passed:
                self.logger.warning(f"Package {package_id} failed compliance check, skipping publish")
                return []
            
            # Publish to each platform
            published_posts = []
            
            for platform_str, platform_package in platform_packages.items():
                try:
                    platform = ContentPlatform(platform_str)
                    
                    # Check rate limit
                    if not self._check_rate_limit(platform.value):
                        self.logger.warning(f"Rate limit exceeded for {platform.value}, skipping")
                        continue
                    
                    # Publish to platform
                    published_post = await self._publish_to_platform(
                        platform=platform,
                        platform_package=platform_package,
                        caption=captions.get(platform_str, ""),
                        hashtags=hashtags.get(platform_str, []),
                        scheduled_time=posting_schedule.get(platform_str),
                        disclosures_included=disclosures_included,
                        package_id=package_id,
                        brief_id=brief_id,
                        script_id=script_id
                    )
                    
                    if published_post:
                        published_posts.append(published_post)
                        self._increment_rate_limit(platform.value)
                        
                        self.logger.info(f"Published to {platform.value}: {published_post.platform_post_id}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to publish to {platform_str}: {e}")
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="content_publishing",
                status="success",
                details={
                    "package_id": package_id,
                    "platforms_published": [p.platform.value for p in published_posts],
                    "posts_published": len(published_posts)
                },
                duration_seconds=duration
            )
            
            return published_posts
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="content_publishing",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to publish content package: {e}")
            return []
    
    async def _publish_to_platform(
        self,
        platform: ContentPlatform,
        platform_package: Dict[str, Any],
        caption: str,
        hashtags: List[str],
        scheduled_time: Optional[str],
        disclosures_included: bool,
        package_id: str,
        brief_id: str,
        script_id: str
    ) -> Optional[PublishedPost]:
        """Publish content to a specific platform."""
        platform_client = self.platform_clients.get(platform.value, {})
        
        # Check if mock is enabled
        if platform_client.get("mock_enabled", True):
            return await self._mock_publish_to_platform(
                platform=platform,
                platform_package=platform_package,
                caption=caption,
                hashtags=hashtags,
                scheduled_time=scheduled_time,
                disclosures_included=disclosures_included,
                package_id=package_id,
                brief_id=brief_id,
                script_id=script_id
            )
        else:
            # Real API implementation would go here
            self.logger.warning(f"Real API not implemented for {platform.value}, using mock")
            return await self._mock_publish_to_platform(
                platform=platform,
                platform_package=platform_package,
                caption=caption,
                hashtags=hashtags,
                scheduled_time=scheduled_time,
                disclosures_included=disclosures_included,
                package_id=package_id,
                brief_id=brief_id,
                script_id=script_id
            )
    
    async def _mock_publish_to_platform(
        self,
        platform: ContentPlatform,
        platform_package: Dict[str, Any],
        caption: str,
        hashtags: List[str],
        scheduled_time: Optional[str],
        disclosures_included: bool,
        package_id: str,
        brief_id: str,
        script_id: str
    ) -> Optional[PublishedPost]:
        """Mock publishing to a platform."""
        try:
            # Simulate API call delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Generate mock platform post ID
            platform_post_id = f"{platform.value}_{random.randint(100000, 999999)}"
            
            # Generate mock URL
            post_url = self._generate_mock_post_url(platform, platform_post_id)
            
            # Generate tracking links
            tracking_links = self._generate_tracking_links(
                platform=platform,
                platform_post_id=platform_post_id,
                brief_id=brief_id,
                script_id=script_id
            )
            
            # Generate affiliate links (if available in brief)
            affiliate_links = self._generate_affiliate_links(brief_id)
            
            # Determine if scheduled
            is_scheduled = scheduled_time is not None
            publish_time = scheduled_time if scheduled_time else datetime.utcnow().isoformat()
            
            # Create published post
            published_post = PublishedPost(
                post_id=f"post_{platform_post_id}",
                package_id=package_id,
                platform=platform,
                platform_post_id=platform_post_id,
                post_url=post_url,
                published_at=publish_time,
                scheduled_publish=is_scheduled,
                publisher_agent=self.agent_id,
                tracking_links=tracking_links,
                affiliate_links=affiliate_links,
                initial_views=random.randint(100, 1000) if not is_scheduled else 0,
                initial_likes=random.randint(10, 100) if not is_scheduled else 0,
                initial_shares=random.randint(1, 20) if not is_scheduled else 0,
                initial_comments=random.randint(0, 10) if not is_scheduled else 0
            )
            
            return published_post
            
        except Exception as e:
            self.logger.error(f"Mock publish failed for {platform.value}: {e}")
            return None
    
    def _generate_mock_post_url(self, platform: ContentPlatform, post_id: str) -> str:
        """Generate mock post URL."""
        url_templates = {
            ContentPlatform.TIKTOK: f"https://tiktok.com/@kashclaw/video/{post_id}",
            ContentPlatform.YOUTUBE_SHORTS: f"https://youtube.com/shorts/{post_id}",
            ContentPlatform.INSTAGRAM_REELS: f"https://instagram.com/reel/{post_id}",
            ContentPlatform.X: f"https://x.com/kashclaw/status/{post_id}",
            ContentPlatform.FACEBOOK: f"https://facebook.com/kashclaw/posts/{post_id}",
            ContentPlatform.LINKEDIN: f"https://linkedin.com/feed/update/{post_id}"
        }
        return url_templates.get(platform, f"https://example.com/post/{post_id}")
    
    def _generate_tracking_links(
        self,
        platform: ContentPlatform,
        platform_post_id: str,
        brief_id: str,
        script_id: str
    ) -> Dict[str, str]:
        """Generate UTM tracking links."""
        base_url = "https://kashclaw.com/track"
        
        utm_params = {
            "utm_source": platform.value,
            "utm_medium": "social",
            "utm_campaign": f"content_{brief_id}" if brief_id else "content",
            "utm_content": script_id,
            "utm_term": platform_post_id
        }
        
        # Create tracking URL
        param_string = "&".join([f"{k}={v}" for k, v in utm_params.items()])
        tracking_url = f"{base_url}?{param_string}"
        
        return {
            "click_tracking": tracking_url,
            "utm_parameters": utm_params
        }
    
    def _generate_affiliate_links(self, brief_id: str) -> List[str]:
        """Generate affiliate links from brief data."""
        if not brief_id:
            return []
        
        # Get brief data
        briefs = self._read_ledger("content_briefs", limit=100)
        for brief in briefs:
            if brief.get("brief_id") == brief_id:
                primary_offer = brief.get("primary_offer")
                if primary_offer and "affiliate_link" in primary_offer:
                    return [primary_offer["affiliate_link"]]
        
        return []
    
    def _save_published_post(self, post: PublishedPost):
        """Save published post to ledger."""
        from dataclasses import asdict
        
        record = asdict(post)
        
        # Convert enum values to strings
        record["platform"] = post.platform.value
        
        self._append_to_ledger("published_posts", record)
    
    def _update_published_post(self, post_data: Dict[str, Any]):
        """Update published post in ledger."""
        # This is a simplified implementation
        # In production, you'd want to update specific records
        
        # For now, just append the update
        self._append_to_ledger("published_updates", post_data)
    
    async def _distribute_published_posts(self, posts: List[PublishedPost]):
        """Distribute published posts to Analytics Agent."""
        try:
            for post in posts:
                # Prepare intent data for Analytics Agent
                intent_data = {
                    "post_id": post.post_id,
                    "platform": post.platform.value,
                    "platform_post_id": post.platform_post_id,
                    "post_url": post.post_url,
                    "published_at": post.published_at,
                    "tracking_links": post.tracking_links,
                    "affiliate_links": post.affiliate_links,
                    "initial_metrics": {
                        "views": post.initial_views,
                        "likes": post.initial_likes,
                        "shares": post.initial_shares,
                        "comments": post.initial_comments
                    }
                }
                
                response = self._send_intent("media.performance_tracking", intent_data)
                
                if response:
                    self.logger.info(f"Distributed post {post.post_id} to Analytics Agent")
                else:
                    self.logger.warning(f"Failed to distribute post {post.post_id}")
                    
        except Exception as e:
            self.logger.error(f"Error distributing published posts: {e}")
    
    async def retry_failed_posts(self, hours_old: int = 24) -> List[Dict[str, Any]]:
        """
        Retry failed posts from the last N hours.
        
        Args:
            hours_old: How many hours back to look for failed posts
            
        Returns:
            List of retry results
        """
        operation_id = self._log_operation(
            operation="retry_failed_posts",
            status="pending",
            details={"hours_old": hours_old}
        )
        
        try:
            # Get failed posts from ledger
            # This is a simplified implementation
            # In production, you'd query for posts with failure status
            
            self.logger.info(f"Retrying failed posts from last {hours_old} hours")
            
            # For now, return empty list
            result = []
            
            self._log_operation(
                operation="retry_failed_posts",
                status="success",
                details={"posts_retried": len(result)}
            )
            
            return result
            
        except Exception as e:
            self._log_operation(
                operation="retry_failed_posts",
                status="failure",
                details={"error": str(e)}
            )
            self.logger.error(f"Failed to retry posts: {e}")
            return []
    
    def get_recent_posts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent published posts."""
        return self._read_ledger("published_posts", limit=limit)
    
    def get_publishing_statistics(self) -> Dict[str, Any]:
        """Get publishing statistics."""
        posts = self._read_ledger("published_posts", limit=100)
        operations = self._read_ledger("operations", limit=100)
        
        if not posts:
            return {"status": "no_data", "message": "No posts published yet"}
        
        # Calculate statistics
        publishing_operations = [op for op in operations if op.get("operation") == "content_publishing"]
        
        success_count = sum(1 for op in publishing_operations if op.get("status") == "success")
        failure_count = sum(1 for op in publishing_operations if op.get("status") == "failure")
        
        # Platform distribution
        platform_counts = {}
        scheduled_count = 0
        immediate_count = 0
        
        for post in posts:
            platform = post.get("platform", "unknown")
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            if post.get("scheduled_publish", False):
                scheduled_count += 1
            else:
                immediate_count += 1
        
        # Engagement statistics
        total_views = sum(post.get("initial_views", 0) for post in posts)
        total_likes = sum(post.get("initial_likes", 0) for post in posts)
        total_shares = sum(post.get("initial_shares", 0) for post in posts)
        total_comments = sum(post.get("initial_comments", 0) for post in posts)
        
        avg_views = total_views / len(posts) if posts else 0
        engagement_rate = ((total_likes + total_shares + total_comments) / total_views * 100) if total_views > 0 else 0
        
        # Rate limit status
        rate_limit_status = {}
        for platform, tracker in self.rate_limit_trackers.items():
            rate_limit_status[platform] = {
                "used": tracker["requests_made"],
                "limit": tracker["limit"],
                "remaining": tracker["limit"] - tracker["requests_made"],
                "window_reset": tracker["window_start"]
            }
        
        return {
            "status": "success",
            "statistics": {
                "total_posts": len(posts),
                "success_rate": f"{(success_count / len(publishing_operations) * 100):.1f}%" if publishing_operations else "0%",
                "platform_distribution": platform_counts,
                "scheduled_posts": scheduled_count,
                "immediate_posts": immediate_count,
                "total_views": total_views,
                "average_views": f"{avg_views:.1f}",
                "engagement_rate": f"{engagement_rate:.2f}%",
                "rate_limit_status": rate_limit_status,
                "pending_queue": self.pending_packages.qsize()
            },
            "recent_posts": posts[:10]
        }


# Factory function for creating the agent
def create_publisher_agent(
    agent_id: str = "publisher_agent",
    data_dir: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 60
) -> PublisherAgent:
    """Create and return a Publisher Agent instance."""
    return PublisherAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        max_retries=max_retries,
        retry_delay=retry_delay
    )