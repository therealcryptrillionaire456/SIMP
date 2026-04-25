"""
Landing Page Agent for the KashClaw Media Grid.

Generates, renders, deploys, and tracks affiliate landing pages
with A/B testing support, UTM tracking, and performance monitoring.
"""
import asyncio
import functools
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    AffiliateOffer, LandingPage, ContentPlatform, ContentFormat
)

# ── Mock Templates ──────────────────────────────────────────────────────────

MOCK_TEMPLATES = [
    {
        "name": "default",
        "description": "Balanced all-purpose landing page with hero, benefits, features, testimonials, FAQ, and CTA.",
        "sections": ["hero", "problem_solution", "benefits", "features", "testimonials", "faq", "cta", "footer"],
        "primary_color": "#3B82F6",
        "font_family": "Inter, sans-serif",
    },
    {
        "name": "minimalist",
        "description": "Clean, distraction-free design with minimal sections — hero, benefits, CTA.",
        "sections": ["hero", "benefits", "cta", "footer"],
        "primary_color": "#111827",
        "font_family": "Inter, sans-serif",
    },
    {
        "name": "review",
        "description": "Review-focused layout with rating stars, detailed pros/cons table, and testimonial carousel.",
        "sections": ["hero", "rating_overview", "pros_cons", "testimonials", "faq", "cta", "footer"],
        "primary_color": "#F59E0B",
        "font_family": "Inter, sans-serif",
    },
    {
        "name": "comparison",
        "description": "Side-by-side comparison of the promoted offer vs alternatives with a clear winner callout.",
        "sections": ["hero", "comparison_table", "benefits", "testimonials", "cta", "footer"],
        "primary_color": "#8B5CF6",
        "font_family": "Inter, sans-serif",
    },
    {
        "name": "webinar",
        "description": "Event-style page with countdown, speaker bio, agenda, and registration CTA.",
        "sections": ["hero_countdown", "speaker", "agenda", "benefits", "cta", "footer"],
        "primary_color": "#EC4899",
        "font_family": "Inter, sans-serif",
    },
]


class LandingPageAgent(BaseMediaAgent):
    """Agent that generates, renders, deploys, and tracks affiliate landing pages."""

    def __init__(
        self,
        agent_id: str = "landing_page_agent",
        agent_name: str = "Landing Page Agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        template_dir: Optional[str] = None,
    ):
        """
        Initialize Landing Page Agent.

        Args:
            agent_id: Unique identifier for this agent
            agent_name: Human-readable name
            data_dir: Directory for data storage (defaults to data/media/)
            log_level: Logging level
            template_dir: Directory for page templates (defaults to data/landing_pages/templates)
        """
        super().__init__(agent_id=agent_id, agent_name=agent_name, data_dir=data_dir, log_level=log_level)

        # Template directory
        resolved_template_dir = template_dir or f"{self.data_dir}/landing_pages/templates"
        self.template_dir = Path(resolved_template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Load mock templates so they are available off the bat
        self.mock_templates = self._load_mock_templates()

        # ── LRU Cache for Landing Pages (Tranche 7) ────────────────────────
        self._cache_ttl_seconds: float = 300.0  # 5 minutes
        # Each entry: {cache_key: (page_dict, insertion_timestamp)}
        self._landing_page_cache: Dict[Any, Any] = {}
        # Underlying lru_cache bound method — cleared on config change
        self._cached_generate = functools.lru_cache(maxsize=128)(
            self._generate_uncached
        )

        self.logger.info(f"LandingPageAgent ready — template_dir={self.template_dir}")

    # ── Template Helpers ─────────────────────────────────────────────────────

    def _load_mock_templates(self) -> List[Dict[str, Any]]:
        """Return the built-in list of landing page templates."""
        return list(MOCK_TEMPLATES)

    def _get_template(self, name: str) -> Dict[str, Any]:
        """Look up a template by name; fall back to 'default'."""
        for tpl in self.mock_templates:
            if tpl["name"] == name:
                return tpl
        self.logger.warning(f"Template '{name}' not found, using 'default'")
        return MOCK_TEMPLATES[0]

    # ── Helper: safely pull content from an AffiliateOffer dict ────────────

    @staticmethod
    def _offer_str(offer: Dict, *keys: str, default: str = "") -> str:
        """Dig through an offer dict for the first present key."""
        for key in keys:
            val = offer.get(key, None)
            if val is not None:
                return str(val)
        return default

    # ── Method 1: generate_landing_page (LRU-cached, TTL-aware) ──────────────

    def generate_landing_page(
        self,
        offer: Dict[str, Any],
        template_name: str = "default",
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a landing page dict from an AffiliateOffer-like dictionary.

        Uses an LRU cache (maxsize=128) keyed by (offer_id, template_name, platform).
        Entries older than ``_cache_ttl_seconds`` (default 300 s / 5 min) are
        re-generated. Pass customizations to force a fresh uncached build.

        Args:
            offer: Dictionary with AffiliateOffer fields (or a dataclass-asdict)
            template_name: Name of the template to use
            customizations: Optional overrides for any LandingPage field

        Returns:
            LandingPage-compatible dictionary
        """
        # If customizations are provided, always bypass cache
        if customizations:
            return self._generate_uncached(offer, template_name, customizations)

        # Determine platform from offer tags or default
        platform = self._offer_str(offer, "platform", default="web")
        cache_key = (str(offer.get("offer_id", "")), template_name, platform)

        now = time.time()

        # TTL check
        if cache_key in self._landing_page_cache:
            cached_page, cached_time = self._landing_page_cache[cache_key]
            if (now - cached_time) <= self._cache_ttl_seconds:
                return cached_page

        # Cache miss or expired — generate via lru_cache-decorated method
        page = self._cached_generate(offer, template_name, customizations)
        self._landing_page_cache[cache_key] = (page, now)
        return page

    def _generate_uncached(
        self,
        offer: Dict[str, Any],
        template_name: str = "default",
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal landing page builder — no caching, always fresh.

        This is the method wrapped by ``functools.lru_cache`` so that repeated
        calls with the same arguments within TTL hit the lru_cache, while the
        public ``generate_landing_page`` adds TTL invalidation on top.
        """
        customizations = customizations or {}
        tpl = self._get_template(template_name)

        offer_name = self._offer_str(offer, "name", "title", default="Our Recommended Tool")
        offer_desc = self._offer_str(offer, "description", default="")
        offer_link = self._offer_str(offer, "affiliate_link", "landing_page_url", default="#")
        disclosures_raw = offer.get("disclosure_requirements", [])
        if isinstance(disclosures_raw, list):
            disclosures = [str(d) for d in disclosures_raw]
        else:
            disclosures = ["This page contains affiliate links. We may earn a commission at no extra cost to you."]

        # ----- Generate content fields -----
        headline = customizations.get(
            "headline",
            f"Stop Wasting Time — {offer_name} Does The Heavy Lifting",
        )
        subheadline = customizations.get(
            "subheadline",
            f"See why thousands of professionals are switching to {offer_name} every month.",
        )
        problem_statement = customizations.get(
            "problem_statement",
            "Most tools promise the world but deliver frustration — endless setup, steep learning curves, and hidden fees that eat into your budget.",
        )
        solution_description = customizations.get(
            "solution_description",
            f"{offer_name} changes the game. It's built for real people who want real results without the headache. {offer_desc[:200] if offer_desc else ''}",
        )
        benefits = customizations.get(
            "benefits",
            [
                "Save 10+ hours per week with automation",
                "No credit card required to start",
                "24/7 customer support from real humans",
                f"Trusted by {offer_name} users worldwide",
            ],
        )
        features = customizations.get(
            "features",
            [
                f"Seamless {offer_name} integration with your existing stack",
                "One-click setup — running in under 5 minutes",
                "Real-time analytics dashboard",
                "AI-powered recommendations",
                "Enterprise-grade security & compliance",
            ],
        )
        testimonials = customizations.get(
            "testimonials",
            [
                {"name": "Sarah J.", "role": "Marketing Lead", "text": f"{offer_name} cut our workflow time in half. I can't imagine going back."},
                {"name": "Marcus T.", "role": "Freelancer", "text": "I was skeptical, but the results speak for themselves. Worth every penny."},
                {"name": "Aisha K.", "role": "Product Manager", "text": "We tried three other tools before this. Nothing compares to the simplicity."},
            ],
        )
        faqs = customizations.get(
            "faqs",
            [
                {"question": "How does the free trial work?", "answer": f"You get full access to {offer_name} for 14 days. No credit card required."},
                {"question": "Can I cancel anytime?", "answer": "Yes. There are no long-term contracts. Cancel with one click."},
                {"question": "Is my data secure?", "answer": "Absolutely. We use bank-level encryption and never share your data with third parties."},
            ],
        )

        # ----- Assemble page dict -----
        page: Dict[str, Any] = {
            "page_id": f"page_{uuid.uuid4().hex[:8]}",
            "offer_id": str(offer.get("offer_id", "")),
            "title": customizations.get("title", f"{offer_name} – Full Review & Honest Opinion"),
            "headline": headline,
            "subheadline": subheadline,
            "problem_statement": problem_statement,
            "solution_description": solution_description,
            "benefits": benefits,
            "features": features,
            "testimonials": testimonials,
            "faqs": faqs,
            "template": template_name,
            "primary_color": customizations.get("primary_color", tpl["primary_color"]),
            "secondary_color": customizations.get("secondary_color", ""),
            "font_family": customizations.get("font_family", tpl["font_family"]),
            "tracking_code": customizations.get("tracking_code", ""),
            "utm_parameters": customizations.get("utm_parameters", {}),
            "affiliate_link": offer_link,
            "email_capture": customizations.get("email_capture", True),
            "email_placeholder": customizations.get("email_placeholder", "Enter your email for exclusive tips"),
            "disclosures": disclosures,
            "privacy_policy_link": customizations.get("privacy_policy_link", ""),
            "terms_link": customizations.get("terms_link", ""),
            "html_url": "",
            "screenshot_url": "",
            "metadata": {
                "offer_name": offer_name,
                "generated_by": self.agent_id,
                **customizations.get("metadata", {}),
            },
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self._log_operation("generate_landing_page", "success", {
            "page_id": page["page_id"],
            "template": template_name,
            "offer": offer_name,
        })
        return page

    def clear_landing_page_cache(self) -> int:
        """
        Invalidate the entire landing page LRU cache.

        Intended to be called when configuration changes that might affect
        page generation (e.g. new template set, updated copy defaults).

        Returns:
            Number of entries that were in the cache before clearing.
        """
        old_size = self._cached_generate.cache_info().currsize
        self._cached_generate.cache_clear()
        self._landing_page_cache.clear()
        self.logger.info(f"Landing page cache cleared ({old_size} entries)")
        return old_size

    # ── Method 2: render_html ────────────────────────────────────────────────

    def render_html(self, page: Dict[str, Any]) -> str:
        """
        Convert a LandingPage-compatible dict into a self-contained HTML string.

        Output is mobile-responsive, uses inline CSS, and has zero external
        dependencies. All affiliate links get UTM injection at render time.
        """
        # Destructure with fallbacks
        headline = page.get("headline", "Headline")
        subheadline = page.get("subheadline", "")
        problem = page.get("problem_statement", "")
        solution = page.get("solution_description", "")
        benefits: List[str] = page.get("benefits", [])
        features: List[str] = page.get("features", [])
        testimonials: List[Dict[str, str]] = page.get("testimonials", [])
        faqs: List[Dict[str, str]] = page.get("faqs", [])
        primary_color = page.get("primary_color", "#3B82F6")
        font = page.get("font_family", "Inter, sans-serif")
        aff_link = page.get("affiliate_link", "#")
        disclosures: List[str] = page.get("disclosures", [])
        page_id = page.get("page_id", "unknown")
        email_capture = page.get("email_capture", True)
        email_placeholder = page.get("email_placeholder", "Enter your email")

        # ── Inject UTM parameters into affiliate links ──
        utm = page.get("utm_parameters", {})
        tracked_link = self._inject_utm(aff_link, utm)

        # ── Emoji icons per section ──
        benefit_icons = ["⚡", "🎯", "💬", "🌟"]
        feature_icons = ["🔧", "⚙️", "📊", "🤖", "🔒"]

        # ── Build testimonial cards ──
        testimonial_html = ""
        for i, t in enumerate(testimonials):
            name = t.get("name", "Verified User")
            role = t.get("role", "")
            text = t.get("text", "")
            testimonial_html += f"""
                <div class="testimonial-card" style="min-width:280px;flex-shrink:0;background:{primary_color}0d;border-radius:16px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <p style="font-size:16px;line-height:1.6;color:#374151;margin:0 0 16px 0;">"{text}"</p>
                    <div style="font-weight:600;color:#111827;">{name}</div>
                    {f'<div style="font-size:14px;color:#6B7280;">{role}</div>' if role else ''}
                </div>"""

        # ── Build FAQ accordion ──
        faq_html = ""
        for i, item in enumerate(faqs):
            q = item.get("question", "")
            a = item.get("answer", "")
            faq_html += f"""
                <details class="faq-item" style="border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;margin-bottom:8px;cursor:pointer;">
                    <summary style="font-weight:600;font-size:16px;color:#111827;outline:none;">{q}</summary>
                    <p style="margin-top:12px;color:#6B7280;font-size:15px;line-height:1.6;">{a}</p>
                </details>"""

        # ── Benefits grid ──
        benefit_cards = ""
        for idx, b in enumerate(benefits):
            icon = benefit_icons[idx % len(benefit_icons)]
            benefit_cards += f"""
                <div class="benefit-card" style="text-align:center;padding:20px;">
                    <div style="font-size:32px;margin-bottom:12px;">{icon}</div>
                    <p style="font-size:16px;font-weight:500;color:#111827;margin:0;">{b}</p>
                </div>"""

        # ── Features list ──
        feature_items = ""
        for idx, feat in enumerate(features):
            icon = feature_icons[idx % len(feature_icons)]
            feature_items += f"""
                <li style="display:flex;align-items:center;gap:12px;padding:10px 0;font-size:16px;color:#374151;">
                    <span style="font-size:22px;flex-shrink:0;">{icon}</span>
                    <span>{feat}</span>
                </li>"""

        # ── Assemble full HTML ──
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page.get("title", "Landing Page")}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: {font}; color: #111827; background: #FFFFFF; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
  .container {{ max-width: 1040px; margin: 0 auto; padding: 0 24px; }}
  .section {{ padding: 64px 0; }}
  .section-alt {{ background: #F9FAFB; }}
  .section-title {{ font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 12px; color: #111827; }}
  .section-subtitle {{ font-size: 18px; text-align: center; color: #6B7280; margin-bottom: 40px; }}

  /* Hero */
  .hero {{ padding: 80px 0 64px; text-align: center; background: linear-gradient(135deg, {primary_color} 0%, #1E3A8A 100%); color: #FFFFFF; }}
  .hero h1 {{ font-size: 44px; font-weight: 800; line-height: 1.2; margin-bottom: 16px; }}
  .hero p {{ font-size: 20px; opacity: 0.9; margin-bottom: 32px; max-width: 640px; margin-left: auto; margin-right: auto; }}
  .cta-btn {{ display: inline-block; background: #FFFFFF; color: {primary_color}; font-weight: 700; font-size: 18px; padding: 16px 40px; border-radius: 40px; text-decoration: none; box-shadow: 0 8px 24px rgba(0,0,0,0.2); transition: transform 0.2s; }}
  .cta-btn:hover {{ transform: translateY(-2px); }}

  /* Problem / Solution */
  .problem-solution-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
  @media (max-width: 640px) {{ .problem-solution-grid {{ grid-template-columns: 1fr; }} }}

  /* Benefits */
  .benefits-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; }}

  /* Features */
  .feature-list {{ list-style: none; max-width: 540px; margin: 0 auto; }}

  /* Testimonials carousel (CSS-only) */
  .testimonial-track {{ display: flex; gap: 24px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 8px 0 16px; -webkit-overflow-scrolling: touch; }}
  .testimonial-track::-webkit-scrollbar {{ height: 6px; }}
  .testimonial-track::-webkit-scrollbar-thumb {{ background: #D1D5DB; border-radius: 3px; }}

  /* FAQ accordion */
  .faq-item[open] {{ background: {primary_color}08; }}
  .faq-item summary::-webkit-details-marker {{ display: none; }}
  .faq-item summary::after {{ content: "+"; float: right; font-size: 20px; font-weight: 600; color: {primary_color}; }}
  .faq-item[open] summary::after {{ content: "–"; }}

  /* Email capture */
  .email-box {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-top: 24px; }}
  .email-box input {{ flex: 1; min-width: 240px; padding: 14px 18px; border: 1px solid #D1D5DB; border-radius: 32px; font-size: 16px; outline: none; }}
  .email-box input:focus {{ border-color: {primary_color}; }}
  .email-box button {{ background: {primary_color}; color: #FFF; border: none; padding: 14px 32px; border-radius: 32px; font-size: 16px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }}
  .email-box button:hover {{ opacity: 0.9; }}

  /* Footer */
  .footer {{ padding: 32px 0; text-align: center; font-size: 13px; color: #9CA3AF; }}
  .footer a {{ color: #6B7280; text-decoration: underline; }}
  .disclosures {{ margin-top: 16px; font-size: 12px; color: #9CA3AF; line-height: 1.6; }}
</style>
</head>
<body>

<!-- ============ HERO ============ -->
<section class="hero">
  <div class="container">
    <h1>{headline}</h1>
    <p>{subheadline}</p>
    <a class="cta-btn" href="{tracked_link}" target="_blank" rel="noopener noreferrer">Get Started Now →</a>
  </div>
</section>

<!-- ============ PROBLEM / SOLUTION ============ -->
<section class="section">
  <div class="container problem-solution-grid">
    <div>
      <h3 style="font-size:22px;font-weight:700;margin-bottom:12px;color:#DC2626;">😞 The Problem</h3>
      <p style="font-size:16px;line-height:1.7;color:#6B7280;">{problem}</p>
    </div>
    <div>
      <h3 style="font-size:22px;font-weight:700;margin-bottom:12px;color:{primary_color};">✅ The Solution</h3>
      <p style="font-size:16px;line-height:1.7;color:#6B7280;">{solution}</p>
    </div>
  </div>
</section>

<!-- ============ BENEFITS ============ -->
<section class="section section-alt">
  <div class="container">
    <h2 class="section-title">Why People Love It</h2>
    <p class="section-subtitle">Real benefits that make a difference every day.</p>
    <div class="benefits-grid">{benefit_cards}</div>
  </div>
</section>

<!-- ============ FEATURES ============ -->
<section class="section">
  <div class="container">
    <h2 class="section-title">Everything You Need</h2>
    <p class="section-subtitle">Packed with powerful features — no fluff.</p>
    <ul class="feature-list">{feature_items}</ul>
    <div style="text-align:center;margin-top:32px;">
      <a class="cta-btn" href="{tracked_link}" target="_blank" rel="noopener noreferrer" style="background:{primary_color};color:#FFF;box-shadow:0 4px 16px {primary_color}44;">See Full Feature List →</a>
    </div>
  </div>
</section>

<!-- ============ TESTIMONIALS ============ -->
<section class="section section-alt">
  <div class="container">
    <h2 class="section-title">What Users Are Saying</h2>
    <p class="section-subtitle">Join thousands of happy customers.</p>
    <div class="testimonial-track">{testimonial_html}</div>
  </div>
</section>

<!-- ============ FAQ ============ -->
<section class="section">
  <div class="container" style="max-width:680px;">
    <h2 class="section-title">Frequently Asked Questions</h2>
    <p class="section-subtitle">Everything you need to know before getting started.</p>
    {faq_html}
  </div>
</section>

<!-- ============ CTA ============ -->
<section class="section section-alt" style="text-align:center;">
  <div class="container">
    <h2 class="section-title">Ready to Get Started?</h2>
    <p class="section-subtitle" style="margin-bottom:8px;">Join thousands of satisfied users today.</p>
    <a class="cta-btn" href="{tracked_link}" target="_blank" rel="noopener noreferrer" style="background:{primary_color};color:#FFF;box-shadow:0 4px 16px {primary_color}44;font-size:20px;padding:18px 48px;">Try {page.get("metadata", {}).get("offer_name", "It")} Now →</a>
    {f'''
    <div class="email-box">
      <input type="email" placeholder="{email_placeholder}" />
      <button>Send Me Tips</button>
    </div>''' if email_capture else ''}
  </div>
</section>

<!-- ============ FOOTER ============ -->
<footer class="footer">
  <div class="container">
    <p style="margin-bottom:8px;">
      <a href="{tracked_link}" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
      &nbsp;·&nbsp;
      <a href="{tracked_link}" target="_blank" rel="noopener noreferrer">Terms of Service</a>
    </p>
    <p style="font-size:12px;">Page ID: {page_id}</p>
    {f'<div class="disclosures">{"<br>".join(disclosures)}</div>' if disclosures else ''}
  </div>
</footer>

</body>
</html>"""

    # ── Method 3: deploy_page ─────────────────────────────────────────────────

    def deploy_page(self, page_id: str, html_content: str, domain: str = "localhost:8080") -> Dict[str, Any]:
        """
        Write rendered HTML to disk and return deployment metadata.

        Args:
            page_id: Unique page identifier
            html_content: Full HTML string to write
            domain: Base domain for the deployed URL

        Returns:
            Dict with deployed_url, page_id, timestamp, file_path
        """
        deploy_dir = self.data_dir / "landing_pages" / "deployed"
        deploy_dir.mkdir(parents=True, exist_ok=True)

        file_path = deploy_dir / f"{page_id}.html"
        file_path.write_text(html_content, encoding="utf-8")

        result = {
            "page_id": page_id,
            "deployed_url": f"http://{domain}/{page_id}.html",
            "file_path": str(file_path),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._append_to_ledger("landing_page_deployments", result)
        self._log_operation("deploy_page", "success", result)
        return result

    # ── Method 4: add_tracking ────────────────────────────────────────────────

    def add_tracking(
        self,
        page: Dict[str, Any],
        utm_source: str,
        utm_medium: str = "social",
        utm_campaign: str = "",
    ) -> Dict[str, Any]:
        """
        Attach UTM parameters to a page dict.

        Args:
            page: LandingPage-compatible dictionary
            utm_source: UTM source value (e.g. 'twitter', 'facebook')
            utm_medium: UTM medium value (default 'social')
            utm_campaign: UTM campaign name

        Returns:
            Updated page dict with utm_parameters set
        """
        updated = dict(page)
        updated["utm_parameters"] = {
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign or f"landing_{updated.get('page_id', 'unknown')}",
            "utm_content": updated.get("template", "default"),
        }
        updated["updated_at"] = datetime.utcnow().isoformat()

        self._log_operation("add_tracking", "success", {
            "page_id": updated.get("page_id"),
            "utm_source": utm_source,
        })
        return updated

    # ── Method 5: get_performance ─────────────────────────────────────────────

    def get_performance(self, page_id: str) -> Dict[str, Any]:
        """
        Read performance data from the 'landing_page_performance' ledger.

        Args:
            page_id: Page identifier

        Returns:
            Dict with views, clicks, conversions, conversion_rate, or zeros
        """
        records = self._find_in_ledger("landing_page_performance", "page_id", page_id, limit=1)
        if records:
            rec = records[0]
            return {
                "page_id": page_id,
                "views": rec.get("views", 0),
                "clicks": rec.get("clicks", 0),
                "conversions": rec.get("conversions", 0),
                "conversion_rate": rec.get("conversion_rate", 0.0),
            }

        # Return zeroed data if none found
        return {
            "page_id": page_id,
            "views": 0,
            "clicks": 0,
            "conversions": 0,
            "conversion_rate": 0.0,
        }

    # ── Method 6: track_visit ─────────────────────────────────────────────────

    def track_visit(self, page_id: str, source: str) -> str:
        """
        Log a page visit to the 'landing_page_visits' ledger.

        Args:
            page_id: Page that was visited
            source: Traffic source label

        Returns:
            Record ID of the visit entry
        """
        record = {
            "page_id": page_id,
            "source": source,
            "user_agent": "landing_page_agent/tracker",
        }
        return self._append_to_ledger("landing_page_visits", record)

    # ── Method 7: create_variant ──────────────────────────────────────────────

    def create_variant(
        self,
        original_page: Dict[str, Any],
        variant_name: str,
        changes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Clone a page with modifications for A/B testing.

        Args:
            original_page: Original LandingPage-compatible dict
            variant_name: Name/label for this variant
            changes: Dict of LandingPage fields to override

        Returns:
            New page dict with a fresh page_id and parent_page_id
        """
        variant = dict(original_page)
        variant["page_id"] = f"page_{uuid.uuid4().hex[:8]}"
        variant["parent_page_id"] = original_page.get("page_id", "")
        variant["variant_name"] = variant_name
        variant["template"] = changes.get("template", variant.get("template", "default"))
        variant["created_at"] = datetime.utcnow().isoformat()
        variant["updated_at"] = variant["created_at"]

        # Apply changes
        for key, value in changes.items():
            if key in ("headline", "subheadline", "primary_color", "font_family",
                       "benefits", "features", "testimonials", "faqs", "cta_text",
                       "email_capture", "email_placeholder"):
                variant[key] = value

        self._append_to_ledger("landing_page_variants", {
            "variant_id": variant["page_id"],
            "parent_page_id": variant.get("parent_page_id"),
            "variant_name": variant_name,
            "changes": changes,
        })

        self._log_operation("create_variant", "success", {
            "variant_id": variant["page_id"],
            "parent": variant.get("parent_page_id"),
            "name": variant_name,
        })
        return variant

    # ── Method 8: list_deployed_pages ─────────────────────────────────────────

    def list_deployed_pages(self) -> List[Dict[str, Any]]:
        """
        List all deployed landing pages.

        Returns:
            List of metadata dicts per deployed page
        """
        deploy_dir = self.data_dir / "landing_pages" / "deployed"
        if not deploy_dir.exists():
            return []

        pages: List[Dict[str, Any]] = []
        for fpath in sorted(deploy_dir.glob("*.html"), reverse=True):
            pages.append({
                "page_id": fpath.stem,
                "file_path": str(fpath),
                "file_size_bytes": fpath.stat().st_size,
                "deployed_at": datetime.fromtimestamp(fpath.stat().st_mtime).isoformat(),
            })
        return pages

    # ── Method 9: _process_loop (override) ────────────────────────────────────

    async def _process_loop(self) -> None:
        """
        Override base _process_loop.

        Every 30 minutes:
          - Check for pages with potentially outdated offers
          - Aggregate visit / performance data
          - Log to 'landing_page_maintenance' ledger
        """
        while self.is_running:
            try:
                self.logger.info("LandingPageAgent maintenance cycle starting...")
                pages = self.list_deployed_pages()

                maintenance_record: Dict[str, Any] = {
                    "cycle_start": datetime.utcnow().isoformat(),
                    "deployed_pages_count": len(pages),
                    "pages_checked": [p["page_id"] for p in pages],
                    "pages_needing_update": [],
                    "aggregate_views": 0,
                    "aggregate_clicks": 0,
                    "aggregate_conversions": 0,
                }

                for p in pages:
                    perf = self.get_performance(p["page_id"])
                    maintenance_record["aggregate_views"] += perf.get("views", 0)
                    maintenance_record["aggregate_clicks"] += perf.get("clicks", 0)
                    maintenance_record["aggregate_conversions"] += perf.get("conversions", 0)

                self._append_to_ledger("landing_page_maintenance", maintenance_record)
                self.logger.info(
                    f"Maintenance complete — {len(pages)} pages, "
                    f"{maintenance_record['aggregate_views']} total views"
                )

                # Wait 30 minutes between cycles
                await asyncio.sleep(1800)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Maintenance cycle error: {e}")
                await asyncio.sleep(60)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _inject_utm(url: str, utm_params: Dict[str, str]) -> str:
        """Append UTM query parameters to a URL."""
        if not utm_params or not url or url == "#":
            return url

        # Build query string from non-empty UTM values
        params = []
        for key, value in utm_params.items():
            if value:
                params.append(f"{key}={value.replace(' ', '%20')}")

        if not params:
            return url

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{'&'.join(params)}"


# ── Module-level factory ─────────────────────────────────────────────────────

def create_landing_page_agent(
    agent_id: str = "landing_page_agent",
    data_dir: Optional[str] = None,
    log_level: str = "INFO",
    template_dir: Optional[str] = None,
) -> LandingPageAgent:
    """
    Factory function that creates and returns a LandingPageAgent instance.

    Args:
        agent_id: Unique identifier for this agent
        data_dir: Directory for data storage
        log_level: Logging level
        template_dir: Directory for page templates

    Returns:
        Configured LandingPageAgent
    """
    return LandingPageAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        log_level=log_level,
        template_dir=template_dir,
    )
