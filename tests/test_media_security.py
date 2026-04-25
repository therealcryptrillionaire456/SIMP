"""
Security hardening tests for the KashClaw Media Grid organ.

Covers:
- UTM parameter sanitization (allowlist, value validation, reject malicious)
- Affiliate URL validation (reject javascript:, data:, non-https)
- ContentBrief.validate()
- AffiliateOffer.validate()
- Fuzz: random special characters in UTM values
"""
import asyncio
import json
import os
import random
import string
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from simp.organs.media.agents.publisher_agent import (
    sanitize_utm_params,
    validate_affiliate_url,
    ALLOWED_UTM_KEYS,
)
from simp.organs.media.models import (
    AffiliateOffer,
    ContentBrief,
    OfferCategory,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _random_special_chars(length: int = 8) -> str:
    """Generate a string with random special/control characters."""
    special = string.punctuation + " \t\n\r\x00\x1f\x7f"
    return "".join(random.choice(special) for _ in range(length))


# ── UTM Sanitization Tests ──────────────────────────────────────────────────

class TestUtmSanitization(unittest.TestCase):
    """Tests for :func:`sanitize_utm_params`."""

    def test_allowlist_passes_valid(self):
        """All five allowed UTM keys with clean values should be preserved."""
        params = {
            "utm_source": "twitter",
            "utm_medium": "social",
            "utm_campaign": "spring_sale_2025",
            "utm_content": "hero_banner",
            "utm_term": "ai_tools",
        }
        result = sanitize_utm_params(params)
        self.assertEqual(result, params)

    def test_unknown_keys_stripped(self):
        """Any key not in the allowlist must be dropped."""
        params = {
            "utm_source": "twitter",
            "utm_campaign": "test",
            "utm_term": "abc",
            "fbclid": "should_be_stripped",
            "gclid": "should_be_stripped",
            "custom_utm_bogus": "dropped",
        }
        result = sanitize_utm_params(params)
        self.assertIn("utm_source", result)
        self.assertIn("utm_campaign", result)
        self.assertIn("utm_term", result)
        self.assertNotIn("fbclid", result)
        self.assertNotIn("gclid", result)
        self.assertNotIn("custom_utm_bogus", result)

    def test_rejects_html_in_value(self):
        """Values containing HTML angle brackets should be dropped."""
        params = {"utm_source": "<script>alert(1)</script>"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_javascript_protocol(self):
        """Values containing javascript: should be dropped."""
        params = {"utm_source": "javascript:alert(1)"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_data_protocol(self):
        """Values containing data: should be dropped."""
        params = {"utm_source": "data:text/html,<script>alert(1)</script>"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_vbscript_protocol(self):
        """Values containing vbscript: should be dropped."""
        params = {"utm_term": "vbscript:msgbox('xss')"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_quotes_in_value(self):
        """Values containing double or single quotes should be dropped."""
        params = {
            "utm_source": 'foo"bar',
            "utm_medium": "baz'qux",
        }
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_backtick(self):
        """Values containing backticks should be dropped."""
        params = {"utm_source": "foo`bar"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_rejects_overlong_value(self):
        """Values longer than 100 characters should be dropped."""
        params = {"utm_source": "a" * 101}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_accepts_100_char_value(self):
        """A value exactly 100 characters long should be accepted."""
        value = "a" * 100
        params = {"utm_source": value}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {"utm_source": value})

    def test_rejects_non_string_value(self):
        """Non-string values should be dropped."""
        params = {"utm_source": 12345}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})

    def test_empty_params(self):
        """Empty dict input should return empty dict."""
        self.assertEqual(sanitize_utm_params({}), {})

    def test_mixed_valid_and_invalid(self):
        """Valid params survive alongside dropped invalid ones."""
        params = {
            "utm_source": "twitter",
            "utm_campaign": "good_campaign",
            "utm_content": "<img src=x onerror=alert(1)>",
            "gclid": "dropped",
        }
        result = sanitize_utm_params(params)
        self.assertEqual(result, {"utm_source": "twitter", "utm_campaign": "good_campaign"})

    def test_value_with_underscore_and_dash(self):
        """Alphanumeric, underscore, and dash are allowed in values."""
        params = {"utm_medium": "social_media-feed_v2"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, params)

    def test_value_with_spaces_rejected(self):
        """Values with spaces (not alphanumeric+_+dash) should be rejected."""
        params = {"utm_source": "my campaign jan"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})


# ── Affiliate URL Validation Tests ──────────────────────────────────────────

class TestAffiliateUrlValidation(unittest.TestCase):
    """Tests for :func:`validate_affiliate_url`."""

    def test_valid_https_url(self):
        """A standard https URL should be accepted."""
        self.assertTrue(validate_affiliate_url("https://example.com/offer"))

    def test_valid_https_url_with_query(self):
        """https URL with query parameters should be accepted."""
        self.assertTrue(
            validate_affiliate_url("https://clickbank.net/hop/12345?tid=abc")
        )

    def test_rejects_non_https(self):
        """http:// URLs must be rejected."""
        self.assertFalse(validate_affiliate_url("http://example.com/offer"))

    def test_rejects_javascript_url(self):
        """javascript: URLs must be rejected."""
        self.assertFalse(validate_affiliate_url("javascript:alert(1)"))

    def test_rejects_data_url(self):
        """data: URLs must be rejected."""
        self.assertFalse(validate_affiliate_url("data:text/html,<script>alert(1)</script>"))

    def test_rejects_vbscript_url(self):
        """vbscript: URLs must be rejected."""
        self.assertFalse(validate_affiliate_url("vbscript:msgbox('xss')"))

    def test_rejects_empty_string(self):
        """Empty string must be rejected."""
        self.assertFalse(validate_affiliate_url(""))

    def test_rejects_overlong_url(self):
        """URLs longer than 2000 characters must be rejected."""
        long_url = "https://example.com/" + "a" * 1990
        self.assertFalse(validate_affiliate_url(long_url))

    def test_accepts_2000_char_url(self):
        """URL exactly 2000 characters should be accepted."""
        prefix = "https://example.com/"
        padding = 2000 - len(prefix)
        url = prefix + "a" * padding
        self.assertEqual(len(url), 2000)
        self.assertTrue(validate_affiliate_url(url))

    def test_rejects_non_string(self):
        """Non-string inputs must be rejected."""
        self.assertFalse(validate_affiliate_url(None))
        self.assertFalse(validate_affiliate_url(123))

    def test_https_with_javascript_in_path(self):
        """Even https URLs must not contain javascript: anywhere."""
        self.assertFalse(
            validate_affiliate_url("https://example.com/javascript:alert(1)")
        )

    def test_https_with_data_in_path(self):
        """Even https URLs must not contain data: anywhere."""
        self.assertFalse(
            validate_affiliate_url("https://example.com/data:image/svg+xml")
        )


# ── ContentBrief Validation Tests ───────────────────────────────────────────

class TestContentBriefValidation(unittest.TestCase):
    """Tests for :meth:`ContentBrief.validate`."""

    def test_valid_brief(self):
        """A default-initialized brief is valid (no errors)."""
        brief = ContentBrief(title="My Title", description="A short description.")
        errors = brief.validate()
        self.assertEqual(errors, [])

    def test_title_too_long(self):
        """Title longer than 200 characters should produce an error."""
        brief = ContentBrief(title="x" * 201)
        errors = brief.validate()
        self.assertIn("title", " ".join(errors).lower())

    def test_title_200_ok(self):
        """Title exactly 200 characters is acceptable."""
        brief = ContentBrief(title="x" * 200)
        errors = brief.validate()
        self.assertEqual(errors, [])

    def test_description_too_long(self):
        """Description longer than 2000 characters should produce an error."""
        brief = ContentBrief(description="x" * 2001)
        errors = brief.validate()
        self.assertIn("description", " ".join(errors).lower())

    def test_description_2000_ok(self):
        """Description exactly 2000 characters is acceptable."""
        brief = ContentBrief(description="x" * 2000)
        errors = brief.validate()
        self.assertEqual(errors, [])

    def test_rejects_html_in_title(self):
        """Title containing HTML tags must be rejected."""
        brief = ContentBrief(title="<b>Bold Title</b>")
        errors = brief.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("html", " ".join(errors).lower())

    def test_rejects_html_in_description(self):
        """Description containing HTML tags must be rejected."""
        brief = ContentBrief(
            title="Safe",
            description='<script>alert("xss")</script>Check this out',
        )
        errors = brief.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("html", " ".join(errors).lower())

    def test_plain_text_passes_html_check(self):
        """Plain text with angle brackets in natural language must pass."""
        brief = ContentBrief(
            title="5 > 3 is True",
            description="Use the <3 emoji in your content strategy",
        )
        errors = brief.validate()
        # These are not HTML tags, so they should pass
        self.assertEqual(errors, [])


# ── AffiliateOffer Validation Tests ─────────────────────────────────────────

class TestAffiliateOfferValidation(unittest.TestCase):
    """Tests for :meth:`AffiliateOffer.validate`."""

    def test_valid_offer(self):
        """An offer with https links and valid commission is valid."""
        offer = AffiliateOffer(
            name="Test Tool",
            affiliate_link="https://example.com/test",
            commission_rate=25.0,
        )
        errors = offer.validate()
        self.assertEqual(errors, [])

    def test_valid_offer_landing_page_only(self):
        """An offer with landing_page_url (no affiliate_link) is valid."""
        offer = AffiliateOffer(
            name="Test Tool",
            landing_page_url="https://example.com/landing",
            commission_rate=10.0,
        )
        errors = offer.validate()
        self.assertEqual(errors, [])

    def test_rejects_http_affiliate_link(self):
        """affiliate_link must start with https://."""
        offer = AffiliateOffer(
            name="Test Tool",
            affiliate_link="http://example.com/offer",
        )
        errors = offer.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("affiliate_link", " ".join(errors).lower())

    def test_rejects_http_landing_page(self):
        """landing_page_url must start with https://."""
        offer = AffiliateOffer(
            name="Test Tool",
            landing_page_url="http://example.com/landing",
        )
        errors = offer.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("landing_page_url", " ".join(errors).lower())

    def test_rejects_negative_commission(self):
        """Commission rate must be >= 0."""
        offer = AffiliateOffer(
            name="Test Tool",
            affiliate_link="https://example.com/test",
            commission_rate=-5.0,
        )
        errors = offer.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("commission", " ".join(errors).lower())

    def test_rejects_over_100_commission(self):
        """Commission rate must be <= 100."""
        offer = AffiliateOffer(
            name="Test Tool",
            affiliate_link="https://example.com/test",
            commission_rate=150.0,
        )
        errors = offer.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("commission", " ".join(errors).lower())

    def test_commission_zero_is_valid(self):
        """Commission rate of 0 is valid (free product promotion)."""
        offer = AffiliateOffer(
            name="Free Tool",
            affiliate_link="https://example.com/free",
            commission_rate=0.0,
        )
        errors = offer.validate()
        self.assertEqual(errors, [])

    def test_commission_100_is_valid(self):
        """Commission rate of 100 is valid."""
        offer = AffiliateOffer(
            name="Full Commission",
            affiliate_link="https://example.com/full",
            commission_rate=100.0,
        )
        errors = offer.validate()
        self.assertEqual(errors, [])


# ── Fuzz Tests ──────────────────────────────────────────────────────────────

class TestUtmFuzz(unittest.TestCase):
    """Fuzz tests: random special characters in UTM values.

    These should never crash and should never produce dangerous output.
    """

    def test_fuzz_special_chars(self):
        """Random punctuation/special chars must be rejected safely."""
        for _ in range(50):
            value = _random_special_chars(random.randint(1, 20))
            params = {"utm_source": value}
            result = sanitize_utm_params(params)
            # The function should always return a plain dict — no crash
            self.assertIsInstance(result, dict)
            # The result should never contain dangerous patterns
            result_str = json.dumps(result)
            for dangerous in ("<", ">", "javascript:", "data:", "vbscript:"):
                self.assertNotIn(dangerous, result_str)

    def test_fuzz_control_chars(self):
        """Control characters and null bytes must be rejected safely."""
        for code in range(0x00, 0x20):
            params = {"utm_source": f"test{chr(code)}value"}
            result = sanitize_utm_params(params)
            self.assertIsInstance(result, dict)

    def test_fuzz_unicode(self):
        """Unicode characters outside ASCII alphanumeric must be rejected."""
        params = {"utm_source": "café_100%_über"}
        result = sanitize_utm_params(params)
        self.assertEqual(result, {})


# ── Integration: UTM + URL Round Trip ───────────────────────────────────────

class TestUtmUrlCombined(unittest.TestCase):
    """Combined UTM sanitisation and affiliate URL validation."""

    def test_build_tracking_with_sanitized_utm(self):
        """Simulate the full round-trip through both functions."""
        raw_utm = {
            "utm_source": "twitter",
            "utm_medium": "social",
            "utm_campaign": "<script>alert(1)</script>",  # malicious
            "gclid": "google_click_id",                   # non-allowlist
            "utm_term": "safe_term",
        }
        clean = sanitize_utm_params(raw_utm)

        # Only valid, allowlisted keys should remain
        self.assertIn("utm_source", clean)
        self.assertIn("utm_medium", clean)
        self.assertIn("utm_term", clean)
        self.assertNotIn("utm_campaign", clean)   # dropped for malicious content
        self.assertNotIn("gclid", clean)          # dropped for non-allowlist

        # Round-trip through a tracking URL
        base = "https://example.com/track"
        param_str = "&".join(f"{k}={v}" for k, v in clean.items())
        url = f"{base}?{param_str}"

        self.assertTrue(validate_affiliate_url(url))


if __name__ == "__main__":
    unittest.main()
