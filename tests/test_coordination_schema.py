"""
test_coordination_schema.py
===========================
Test harness for simp/models/coordination_schema.py

Part of the triple-verification process for the coordination-layer feature.
Run from the SIMP repo root:

    python tests/test_coordination_schema.py

All tests use stdlib only. No pytest required (though it works with pytest too).
Exit code 0 = all tests passed. Non-zero = failure.

Verification gate: ALL tests must pass before coordination_schema.py
is considered ready for `local_test` verification status.
"""

import json
import os
import sys
import tempfile
import traceback
import unittest

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.models.coordination_schema import (
    CoordinationCategory,
    CoordinationIntent,
    CoordinationOriginator,
    VerificationStatus,
    export_json_schema,
)


class TestCoordinationCategory(unittest.TestCase):
    def test_all_categories_defined(self):
        expected = {
            "proposal", "test_result", "status_report",
            "change_request", "handoff", "observation", "incident"
        }
        actual = {c.value for c in CoordinationCategory}
        self.assertEqual(expected, actual)

    def test_category_is_str_enum(self):
        self.assertEqual(CoordinationCategory.PROPOSAL, "proposal")
        self.assertIsInstance(CoordinationCategory.HANDOFF, str)


class TestVerificationStatus(unittest.TestCase):
    def test_ordered_levels_exist(self):
        expected = {"none", "static_review", "local_test", "e2e_test", "triple_verified"}
        actual = {v.value for v in VerificationStatus}
        self.assertEqual(expected, actual)

    def test_triple_is_highest(self):
        self.assertEqual(VerificationStatus.TRIPLE.value, "triple_verified")


class TestCoordinationIntentFactory(unittest.TestCase):
    def _make_basic(self, **kwargs) -> CoordinationIntent:
        defaults = dict(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="Test proposal summary",
        )
        defaults.update(kwargs)
        return CoordinationIntent.create(**defaults)

    def test_create_generates_unique_ids(self):
        a = self._make_basic()
        b = self._make_basic()
        self.assertNotEqual(a.coordination_id, b.coordination_id)

    def test_id_format(self):
        intent = self._make_basic()
        self.assertTrue(intent.coordination_id.startswith("coord-"))
        self.assertEqual(len(intent.coordination_id), len("coord-") + 12)

    def test_source_agent_mirrors_originator(self):
        intent = self._make_basic(originator="perplexity")
        self.assertEqual(intent.source_agent, "perplexity")

    def test_default_target_is_simp_router(self):
        intent = self._make_basic()
        self.assertEqual(intent.target_agent, "simp_router")

    def test_custom_target_agent(self):
        intent = self._make_basic(target_agent="kloutbot")
        self.assertEqual(intent.target_agent, "kloutbot")

    def test_default_requires_human_review(self):
        intent = self._make_basic()
        self.assertTrue(intent.requires_human_review)

    def test_default_verification_none(self):
        intent = self._make_basic()
        self.assertEqual(intent.verification_status, VerificationStatus.NONE)

    def test_default_intent_type_is_coordination(self):
        intent = self._make_basic()
        self.assertEqual(intent.intent_type, "coordination")

    def test_timestamp_is_iso8601(self):
        import datetime
        intent = self._make_basic()
        # Should not raise
        datetime.datetime.fromisoformat(intent.timestamp.replace("Z", "+00:00"))

    def test_affected_agents_list(self):
        intent = self._make_basic(affected_agents=["bullbear_predictor", "kashclaw"])
        self.assertEqual(intent.affected_agents, ["bullbear_predictor", "kashclaw"])

    def test_affected_files_list(self):
        intent = self._make_basic(affected_files=["simp/server/broker.py"])
        self.assertEqual(intent.affected_files, ["simp/server/broker.py"])

    def test_roadmap_items_list(self):
        intent = self._make_basic(roadmap_items=["Day 4 - Multi-Agent Orchestration"])
        self.assertEqual(intent.roadmap_items, ["Day 4 - Multi-Agent Orchestration"])

    def test_git_fields(self):
        intent = self._make_basic(
            git_branch="feature/coordination-layer",
            git_commit="abc1234"
        )
        self.assertEqual(intent.git_branch, "feature/coordination-layer")
        self.assertEqual(intent.git_commit, "abc1234")

    def test_details_dict(self):
        intent = self._make_basic(details={"test_count": 17, "all_passed": True})
        self.assertEqual(intent.details["test_count"], 17)
        self.assertTrue(intent.details["all_passed"])


class TestSerialization(unittest.TestCase):
    def _make_full_intent(self) -> CoordinationIntent:
        return CoordinationIntent.create(
            category=CoordinationCategory.TEST_RESULT,
            originator=CoordinationOriginator.COWORK,
            summary="Verified coordination_schema.py imports cleanly, 17 tests pass",
            affected_agents=["simp_router"],
            affected_files=["simp/models/coordination_schema.py"],
            roadmap_items=["Coordination layer — Enhancement A"],
            verification_status=VerificationStatus.LOCAL_TEST,
            requires_human_review=True,
            git_branch="feature/coordination-layer",
            details={
                "tests_run": 17,
                "tests_passed": 17,
                "tests_failed": 0,
                "runner": "python tests/test_coordination_schema.py",
            },
        )

    def test_to_dict_is_serializable(self):
        intent = self._make_full_intent()
        d = intent.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)

    def test_to_json_produces_valid_json(self):
        intent = self._make_full_intent()
        json_str = intent.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["intent_type"], "coordination")
        self.assertEqual(parsed["category"], "test_result")

    def test_roundtrip_from_dict(self):
        original = self._make_full_intent()
        d = original.to_dict()
        restored = CoordinationIntent.from_dict(d)
        self.assertEqual(original.coordination_id, restored.coordination_id)
        self.assertEqual(original.category, restored.category)
        self.assertEqual(original.originator, restored.originator)
        self.assertEqual(original.summary, restored.summary)
        self.assertEqual(original.verification_status, restored.verification_status)
        self.assertEqual(original.details, restored.details)

    def test_roundtrip_from_json(self):
        original = self._make_full_intent()
        json_str = original.to_json()
        restored = CoordinationIntent.from_json(json_str)
        self.assertEqual(original.coordination_id, restored.coordination_id)

    def test_roundtrip_from_file(self):
        original = self._make_full_intent()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = original.write_artifact(tmpdir)
            self.assertTrue(os.path.exists(path))
            self.assertIn("coordination_coord-", os.path.basename(path))
            restored = CoordinationIntent.from_file(path)
            self.assertEqual(original.coordination_id, restored.coordination_id)

    def test_enum_values_in_dict(self):
        """Enums must serialize to their string values, not enum repr."""
        intent = self._make_full_intent()
        d = intent.to_dict()
        self.assertEqual(d["category"], "test_result")
        self.assertEqual(d["verification_status"], "local_test")


class TestValidation(unittest.TestCase):
    def test_from_dict_missing_required_raises(self):
        with self.assertRaises(ValueError) as ctx:
            CoordinationIntent.from_dict({"category": "proposal", "originator": "cowork"})
        self.assertIn("summary", str(ctx.exception))

    def test_from_dict_invalid_category_raises(self):
        with self.assertRaises(ValueError) as ctx:
            CoordinationIntent.from_dict({
                "coordination_id": "coord-aabbccddeeff",
                "category": "execute_trade",   # Not a valid coordination category
                "originator": "cowork",
                "summary": "Test"
            })
        self.assertIn("execute_trade", str(ctx.exception))

    def test_validate_blank_summary_warns(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="   ",
        )
        warnings = intent.validate()
        self.assertTrue(any("summary" in w for w in warnings))

    def test_validate_wrong_intent_type_warns(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="Valid summary",
        )
        intent.intent_type = "trade"   # Simulate accidental mutation
        warnings = intent.validate()
        self.assertTrue(any("intent_type" in w for w in warnings))

    def test_validate_change_request_no_files_warns(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.CHANGE_REQUEST,
            originator="cowork",
            summary="Patch broker.py",
            affected_files=[],   # Should trigger warning
        )
        warnings = intent.validate()
        self.assertTrue(any("affected_files" in w for w in warnings))

    def test_validate_handoff_no_details_warns(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.HANDOFF,
            originator="cowork",
            summary="Hand off to Perplexity",
            details={},   # Should trigger warning
        )
        warnings = intent.validate()
        self.assertTrue(any("details" in w for w in warnings))

    def test_validate_clean_intent_no_warnings(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.STATUS_REPORT,
            originator="cowork",
            summary="All 17 tests passing. SIMP broker online.",
        )
        warnings = intent.validate()
        self.assertEqual(warnings, [])


class TestSafetyGate(unittest.TestCase):
    def test_not_safe_if_requires_review(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.CHANGE_REQUEST,
            originator="cowork",
            summary="Patch",
            verification_status=VerificationStatus.TRIPLE,
            requires_human_review=True,   # Still requires review
        )
        self.assertFalse(intent.is_safe_to_apply())

    def test_not_safe_if_not_triple_verified(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.CHANGE_REQUEST,
            originator="cowork",
            summary="Patch",
            verification_status=VerificationStatus.LOCAL_TEST,
            requires_human_review=False,
        )
        self.assertFalse(intent.is_safe_to_apply())

    def test_safe_only_when_triple_and_cleared(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.CHANGE_REQUEST,
            originator="cowork",
            summary="Patch approved by Kasey",
            verification_status=VerificationStatus.TRIPLE,
            requires_human_review=False,
        )
        self.assertTrue(intent.is_safe_to_apply())


class TestArtifactPersistence(unittest.TestCase):
    def test_write_creates_file_with_correct_name(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.STATUS_REPORT,
            originator="cowork",
            summary="Artifact persistence test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = intent.write_artifact(tmpdir)
            filename = os.path.basename(path)
            self.assertTrue(filename.startswith("coordination_coord-"))
            self.assertTrue(filename.endswith(".json"))
            # File must be valid JSON
            with open(path) as f:
                parsed = json.load(f)
            self.assertEqual(parsed["coordination_id"], intent.coordination_id)

    def test_write_creates_output_dir_if_missing(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.OBSERVATION,
            originator="cowork",
            summary="Dir creation test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "signals", "output")
            path = intent.write_artifact(nested)
            self.assertTrue(os.path.exists(nested))
            self.assertTrue(os.path.exists(path))

    def test_bullbear_watcher_safe_naming(self):
        """
        BullBear watcher looks for signal_*.json, intent_*.json,
        executiondecision_*.json. Coordination files use coordination_*.json
        prefix — verify the naming doesn't collide.
        """
        intent = CoordinationIntent.create(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="Naming collision test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = intent.write_artifact(tmpdir)
            filename = os.path.basename(path)
            self.assertFalse(filename.startswith("signal_"))
            self.assertFalse(filename.startswith("intent_"))
            self.assertFalse(filename.startswith("executiondecision_"))
            self.assertTrue(filename.startswith("coordination_"))


class TestJsonSchemaExport(unittest.TestCase):
    def test_schema_is_valid_dict(self):
        schema = export_json_schema()
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["$schema"], "http://json-schema.org/draft-07/schema#")
        self.assertEqual(schema["title"], "CoordinationIntent")

    def test_schema_includes_all_required_fields(self):
        schema = export_json_schema()
        required = schema.get("required", [])
        self.assertIn("coordination_id", required)
        self.assertIn("category", required)
        self.assertIn("originator", required)
        self.assertIn("summary", required)

    def test_schema_categories_match_enum(self):
        schema = export_json_schema()
        schema_cats = set(schema["properties"]["category"]["enum"])
        enum_cats = {c.value for c in CoordinationCategory}
        self.assertEqual(schema_cats, enum_cats)

    def test_schema_is_json_serializable(self):
        schema = export_json_schema()
        json_str = json.dumps(schema, indent=2)
        self.assertIsInstance(json_str, str)
        # Round-trip
        reparsed = json.loads(json_str)
        self.assertEqual(reparsed["title"], "CoordinationIntent")

    def test_intent_type_is_const_coordination(self):
        schema = export_json_schema()
        self.assertEqual(
            schema["properties"]["intent_type"]["const"],
            "coordination"
        )


class TestStr(unittest.TestCase):
    def test_str_contains_key_fields(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="Add capabilities field to broker",
        )
        s = str(intent)
        self.assertIn("proposal", s)
        self.assertIn("cowork", s)
        self.assertIn("NEEDS HUMAN REVIEW", s)

    def test_str_cleared_when_not_requires_review(self):
        intent = CoordinationIntent.create(
            category=CoordinationCategory.PROPOSAL,
            originator="cowork",
            summary="Cleared proposal",
            requires_human_review=False,
        )
        self.assertIn("CLEARED", str(intent))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("SIMP Coordination Schema — Test Harness")
    print("Triple-verification gate: static_review → local_test")
    print("=" * 70)
    result = run_tests()
    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    print("=" * 70)
    print(f"Results: {total - failures}/{total} passed", end="  ")
    if failures == 0:
        print("✓ ALL TESTS PASS — local_test gate CLEARED")
    else:
        print(f"✗ {failures} FAILURES — local_test gate NOT cleared")
        for f in result.failures + result.errors:
            print(f"  FAIL: {f[0]}")
    print("=" * 70)
    sys.exit(0 if failures == 0 else 1)
