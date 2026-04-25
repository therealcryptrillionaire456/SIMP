"""
SIMP News Agent for KashClaw Media Grid.

Responsible for:
- Aggregating SIMP ecosystem news and system events
- Generating content about system updates, performance metrics
- Creating social media posts promoting SIMP capabilities
- Self-promotion and awareness campaigns
- Scheduling news distribution across platforms
"""
import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent


# ---------------------------------------------------------------------------
# News categories and templates
# ---------------------------------------------------------------------------

_NEWS_TEMPLATES = {
    "system_milestone": [
        "SIMP has processed {count} intents in the last {period} — our mesh is getting faster. 🚀",
        "Agent mesh just hit {count} successful routes. {percentage}% delivery rate. Solid. 🧠",
        "Another broker milestone: {count} intents routed, {uptime}h uptime. The mesh is alive.",
    ],
    "new_capability": [
        "New SIMP capability online: {capability}. Built by {builder}, now live in the mesh. ⚡",
        "We've deployed {capability} into the agent ecosystem. {description} 🤖",
        "Fresh protocol upgrade: {capability}. {description}. Agents updated.",
    ],
    "agent_spotlight": [
        "Agent spotlight: {agent_name}. Handles {description}. Trust score: {trust_score}. 🏆",
        "Meet {agent_name} — our {description} agent. Registered and routing. 🤝",
        "Mesh just got smarter: {agent_name} joined the grid. {description}",
    ],
    "performance_teaser": [
        "Mesh telemetry: {metric_name} at {value} — {trend} from last period. 📊",
        "SIMP internal metrics — {metric_name}: {value}. {context}",
        "System health: {metric_name} = {value}. {trend_direction} trend detected.",
    ],
    "community": [
        "SIMP is open source. Check us out: github.com/your-org/simp 🛠️",
        "Building autonomous agent swarms? SIMP protocol handles the mesh. Try it. 🧩",
        "The future of agent-to-agent communication is typed intents through a broker. SIMP does that today. 🔌",
    ],
    "roadmap": [
        "Next up on the SIMP roadmap: {feature}. Estimated: {timeline}. 📋",
        "Coming soon to the mesh: {feature}. We're building {status}. 🔨",
        "Roadmap update: {feature} moved to {status}. Target delivery: {timeline}.",
    ]
}

_SAMPLE_NEWS_ITEMS = [
    {
        "type": "system_milestone",
        "data": {
            "count": "127,430",
            "period": "30 days",
            "percentage": "99.2",
            "uptime": "720"
        }
    },
    {
        "type": "new_capability",
        "data": {
            "capability": "A2A Compat Layer v0.7",
            "builder": "Perplexity Computer",
            "description": "Full agent-to-agent communication with security, events, and task translation."
        }
    },
    {
        "type": "agent_spotlight",
        "data": {
            "agent_name": "QuantumArb",
            "description": "cross-exchange arbitrage scanning and execution",
            "trust_score": "92/100"
        }
    },
    {
        "type": "agent_spotlight",
        "data": {
            "agent_name": "ProjectX Native",
            "description": "self-maintaining kernel for system health and governance",
            "trust_score": "95/100"
        }
    },
    {
        "type": "agent_spotlight",
        "data": {
            "agent_name": "KashClaw Gemma",
            "description": "local LLM planner running on Gemma4 via Ollama",
            "trust_score": "88/100"
        }
    },
    {
        "type": "performance_teaser",
        "data": {
            "metric_name": "Intent delivery latency (p99)",
            "value": "47ms",
            "trend": "down 12%",
            "trend_direction": "improving",
            "context": "P99 under 50ms means real-time agent interactions"
        }
    },
    {
        "type": "performance_teaser",
        "data": {
            "metric_name": "Registered agents",
            "value": "10",
            "trend": "up 2",
            "trend_direction": "growing",
            "context": "Ecosystem expanding every sprint"
        }
    },
    {
        "type": "community",
        "data": {}
    },
    {
        "type": "roadmap",
        "data": {
            "feature": "DeerFlow agent spawning",
            "timeline": "Q2 2026",
            "status": "active development"
        }
    }
]


class SimpNewsAgent(BaseMediaAgent):
    """Agent that generates and distributes SIMP ecosystem news content."""

    def __init__(
        self,
        agent_id: str = "simp_news",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        news_interval_minutes: int = 120,
        max_posts_per_day: int = 4
    ):
        """Initialize the SIMP News Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="SIMP News Agent",
            data_dir=data_dir,
            log_level=log_level
        )

        self.news_interval_minutes = news_interval_minutes
        self.max_posts_per_day = max_posts_per_day

        # In-memory state
        self._news_items: List[Dict[str, Any]] = []
        self._published_items: List[Dict[str, Any]] = []
        self._scheduled_items: List[Dict[str, Any]] = []
        self._daily_post_count: int = 0
        self._last_reset_date: str = datetime.utcnow().strftime("%Y-%m-%d")

        # Seed sample news items
        self._seed_news()

        self.logger.info(
            f"SIMP News Agent initialized "
            f"(interval={news_interval_minutes}m, max_daily={max_posts_per_day})"
        )

    # ------------------------------------------------------------------
    # Data Seeding
    # ------------------------------------------------------------------

    def _seed_news(self) -> None:
        """Load sample news items from templates."""
        for item in _SAMPLE_NEWS_ITEMS:
            rendered = self._render_item(item)
            self._news_items.append({
                "item_id": f"news-{len(self._news_items) + 1:04d}",
                "type": item["type"],
                "content": rendered,
                "created_at": datetime.utcnow().isoformat(),
                "raw_data": item["data"],
                "is_published": False
            })

    def _render_item(self, item: Dict[str, Any]) -> str:
        """Render a news item using templates and provided data."""
        templates = _NEWS_TEMPLATES.get(item["type"], [])
        if not templates:
            return ""

        template = random.choice(templates)
        try:
            return template.format(**item["data"])
        except KeyError:
            # Fallback: return first template with partial fill
            return template

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def generate_news(
        self,
        news_type: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a new news item, optionally of a specific type."""
        if custom_data:
            # Generate from custom data
            item = {
                "type": news_type or "community",
                "data": custom_data
            }
            rendered = self._render_item(item)
        elif news_type and news_type in _NEWS_TEMPLATES:
            # Find an existing item of this type or generate templated
            items_of_type = [i for i in _SAMPLE_NEWS_ITEMS if i["type"] == news_type]
            if items_of_type:
                base = random.choice(items_of_type)
                item = {"type": base["type"], "data": base["data"]}
            else:
                item = {"type": news_type, "data": {}}
            rendered = self._render_item(item)
        else:
            # Pick random
            base = random.choice(_SAMPLE_NEWS_ITEMS)
            item = {"type": base["type"], "data": base["data"]}
            rendered = self._render_item(item)

        news_record = {
            "item_id": f"news-{len(self._news_items) + 1:04d}",
            "type": item["type"],
            "content": rendered,
            "created_at": datetime.utcnow().isoformat(),
            "raw_data": item["data"],
            "is_published": False
        }

        self._news_items.append(news_record)
        self._append_to_ledger("news_generation_log", news_record)
        return news_record

    def get_unpublished(self) -> List[Dict[str, Any]]:
        """Return all news items not yet published."""
        return [n for n in self._news_items if not n["is_published"]]

    def publish(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Mark a news item as published and record it."""
        for item in self._news_items:
            if item["item_id"] == item_id and not item["is_published"]:
                item["is_published"] = True
                item["published_at"] = datetime.utcnow().isoformat()

                # Reset daily counter if new day
                today = datetime.utcnow().strftime("%Y-%m-%d")
                if today != self._last_reset_date:
                    self._daily_post_count = 0
                    self._last_reset_date = today

                # Check daily limit
                if self._daily_post_count >= self.max_posts_per_day:
                    self.logger.warning("Daily post limit reached — queuing")
                    self._scheduled_items.append(item)
                    item["status"] = "queued"
                    return item

                self._daily_post_count += 1
                self._published_items.append(item)
                item["status"] = "published"

                self._append_to_ledger("publication_log", {
                    "item_id": item_id,
                    "content": item["content"],
                    "type": item["type"],
                    "published_at": item["published_at"],
                    "daily_count": self._daily_post_count
                })

                self._log_operation("item_published", "success", {
                    "item_id": item_id,
                    "type": item["type"],
                    "daily_count": self._daily_post_count
                })
                return item

        self.logger.warning(f"Item {item_id} not found or already published")
        return None

    def publish_batch(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Publish up to `limit` unpublished items respecting daily cap."""
        unpublished = self.get_unpublished()
        if not unpublished:
            return []

        results = []
        for item in unpublished[:limit]:
            result = self.publish(item["item_id"])
            if result:
                results.append(result)
        return results

    def schedule(
        self,
        item_id: str,
        publish_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Schedule a news item for future publication."""
        for item in self._news_items:
            if item["item_id"] == item_id:
                schedule_time = publish_at or (
                    datetime.utcnow() + timedelta(hours=2)
                ).isoformat()
                scheduled = {
                    **item,
                    "scheduled_at": schedule_time,
                    "status": "scheduled"
                }
                self._scheduled_items.append(scheduled)
                self._append_to_ledger("schedule_log", scheduled)
                return scheduled

        return {"error": f"Item {item_id} not found"}

    def get_daily_brief(self) -> Dict[str, Any]:
        """Generate a daily brief of SIMP activity."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        published_today = [
            p for p in self._published_items
            if p.get("published_at", "").startswith(today)
        ]
        scheduled = [s for s in self._scheduled_items if s.get("status") == "scheduled"]

        return {
            "date": today,
            "total_published_today": len(published_today),
            "total_scheduled": len(scheduled),
            "unpublished_count": len(self.get_unpublished()),
            "published_items": published_today,
            "categories_covered": list(set(p["type"] for p in published_today)),
            "daily_limit": self.max_posts_per_day,
            "remaining_today": max(0, self.max_posts_per_day - self._daily_post_count)
        }

    def get_campaign_summary(self) -> Dict[str, Any]:
        """Generate a summary of news activity for reporting."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        published_today = sum(
            1 for p in self._published_items
            if p.get("published_at", "").startswith(today)
        )

        by_type: Dict[str, int] = {}
        for p in self._published_items:
            t = p.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_items_created": len(self._news_items),
            "total_published": len(self._published_items),
            "published_today": published_today,
            "scheduled": len(self._scheduled_items),
            "unpublished": len(self.get_unpublished()),
            "publish_rate": len(self._published_items) / max(1, len(self._news_items)),
            "breakdown_by_type": by_type
        }

    # ------------------------------------------------------------------
    # SIMP-specific content generators
    # ------------------------------------------------------------------

    def announce_milestone(
        self,
        milestone: str,
        value: str
    ) -> Dict[str, Any]:
        """Generate a milestone announcement post."""
        custom_data = {
            "count": value,
            "period": "current",
            "percentage": "99+",
            "uptime": "continuous"
        }
        return self.generate_news(news_type="system_milestone", custom_data=custom_data)

    def announce_capability(
        self,
        capability: str,
        description: str,
        builder: str = "SIMP Team"
    ) -> Dict[str, Any]:
        """Generate a new capability announcement post."""
        custom_data = {
            "capability": capability,
            "description": description,
            "builder": builder
        }
        return self.generate_news(news_type="new_capability", custom_data=custom_data)

    def spotlight_agent(
        self,
        agent_name: str,
        description: str,
        trust_score: str = "N/A"
    ) -> Dict[str, Any]:
        """Generate an agent spotlight post."""
        custom_data = {
            "agent_name": agent_name,
            "description": description,
            "trust_score": trust_score
        }
        return self.generate_news(news_type="agent_spotlight", custom_data=custom_data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the news generation loop."""
        self.is_running = True
        self.logger.info("SIMP News Agent started")
        asyncio.create_task(self._news_loop())

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self.is_running = False
        self.logger.info("SIMP News Agent stopped")

    async def _news_loop(self) -> None:
        """Periodically generate and attempt to publish news."""
        while self.is_running:
            try:
                # Generate fresh news
                fresh = self.generate_news()
                self._log_operation("news_generation", "success", {
                    "item_id": fresh["item_id"],
                    "type": fresh["type"],
                    "content_preview": fresh["content"][:80]
                })

                # Try to publish a batch
                published = self.publish_batch(limit=2)
                if published:
                    self._log_operation("batch_publish", "info", {
                        "count": len(published),
                        "items": [p["item_id"] for p in published]
                    })
                else:
                    self.logger.debug("No items published — daily limit or none unpublished")

            except Exception as e:
                self.logger.error(f"News loop error: {e}")

            await asyncio.sleep(self.news_interval_minutes * 60)


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def create_simp_news_agent(
    agent_id: str = "simp_news",
    data_dir: Optional[str] = None,
    log_level: str = "INFO",
    news_interval_minutes: int = 120
) -> SimpNewsAgent:
    """Factory function for SimpNewsAgent."""
    return SimpNewsAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        log_level=log_level,
        news_interval_minutes=news_interval_minutes
    )
