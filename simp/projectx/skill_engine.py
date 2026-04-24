"""
ProjectX Skill Engine — Phase 2 (Deep Integration)

Loads SIMP skill definitions (.md files in simp/skills/) and registers
them as SubsystemConfig entries in the SubsystemRegistry. Also maps
each skill's declared intent_types to canonical SIMP intent types so
the orchestrator can route SIMP intents directly to the right subsystem.

Skill .md format (from existing simp/skills/*.md):
  ## Description
  ## System Prompt
  ## Tools
  ## Intent Types
  ## Constraints

After loading, each skill becomes callable via:
    registry.route(task, executor, preferred="deep_research")

Also provides reverse lookup: given a canonical intent type, which skill
handles it? This powers the IntentAdapter.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Directory containing skill .md files (relative to repo root)
_DEFAULT_SKILLS_DIR = "simp/skills"

# Canonical intent → subsystem name fallback table (populated from skill files,
# then falls back to this hardcoded mapping for types not declared in any skill)
_INTENT_SUBSYSTEM_MAP: Dict[str, str] = {
    "code_task":        "code_gen",
    "code_editing":     "code_gen",
    "code_review":      "code_gen",
    "planning":         "planning",
    "orchestration":    "planning",
    "research":         "deep_research",
    "market_analysis":  "deep_research",
    "native_agent_repo_scan": "deep_research",
    "research_request": "deep_research",
    "analysis":         "analysis",
    "prediction_signal": "analysis",
    "detect_signal":    "analysis",
    "analyze_patterns": "analysis",
    "improve_tree":     "strategy_optimization",
    "submit_goal":      "strategy_optimization",
    "summarization":    "analysis",
    "docs":             "code_gen",
    "spec":             "planning",
    "architecture":     "planning",
    "creative":         "creative",
    "brainstorm":       "creative",
}


@dataclass
class SkillDefinition:
    """Parsed representation of a .md skill file."""
    name: str
    description: str
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    intent_types: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    source_file: str = ""

    def to_subsystem_config(self):
        """Convert to a SubsystemConfig for the SubsystemRegistry."""
        from simp.projectx.subsystems import SubsystemConfig
        return SubsystemConfig(
            name=self.name,
            role=self.description,
            system_prompt=self.system_prompt + (
                ("\n\nConstraints:\n" + "\n".join(f"- {c}" for c in self.constraints))
                if self.constraints else ""
            ),
            max_calls_per_minute=10,
            memory_enabled=True,
            web_enabled="websearch" in self.tools or "crawl" in self.tools,
            tags=self.intent_types[:8],
        )


class SkillEngine:
    """
    Discovers and loads SIMP skill definitions into the SubsystemRegistry.

    Usage::

        engine = SkillEngine()
        engine.load_all()                     # loads simp/skills/*.md
        engine.load_file("simp/skills/deep-research.md")
        subsystem = engine.get("deep_research")
        intent_subsystem = engine.subsystem_for_intent("market_analysis")
    """

    def __init__(
        self,
        skills_dir: Optional[str] = None,
        registry=None,
    ) -> None:
        self._skills_dir = Path(skills_dir or _DEFAULT_SKILLS_DIR)
        self._registry = registry  # SubsystemRegistry, injected or lazy-loaded
        self._skills: Dict[str, SkillDefinition] = {}
        self._intent_map: Dict[str, str] = dict(_INTENT_SUBSYSTEM_MAP)  # copy

    # ── Public API ────────────────────────────────────────────────────────

    def load_all(self, skills_dir: Optional[str] = None) -> List[str]:
        """
        Discover and load all .md files in the skills directory.

        Returns list of loaded skill names.
        """
        target = Path(skills_dir) if skills_dir else self._skills_dir
        if not target.exists():
            logger.debug("Skills dir not found: %s", target)
            return []
        loaded = []
        for md_file in sorted(target.glob("*.md")):
            skill = self._parse_skill_file(md_file)
            if skill:
                self._register(skill)
                loaded.append(skill.name)
        logger.info("SkillEngine loaded %d skills: %s", len(loaded), loaded)
        return loaded

    def load_file(self, path: str) -> Optional[SkillDefinition]:
        """Load a single skill .md file."""
        skill = self._parse_skill_file(Path(path))
        if skill:
            self._register(skill)
        return skill

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def all_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def subsystem_for_intent(self, intent_type: str) -> Optional[str]:
        """
        Return the subsystem name that handles a given canonical intent type.
        Returns None if no skill claims this intent type.
        """
        return self._intent_map.get(intent_type)

    def list_intent_mappings(self) -> Dict[str, str]:
        """Return all intent_type → subsystem_name mappings."""
        return dict(self._intent_map)

    # ── Parsing ───────────────────────────────────────────────────────────

    def _parse_skill_file(self, path: Path) -> Optional[SkillDefinition]:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Cannot read skill file %s: %s", path, exc)
            return None

        # Derive canonical name from filename (e.g. "deep-research" → "deep_research")
        name = re.sub(r"[^a-zA-Z0-9]+", "_", path.stem).lower().strip("_")

        description = self._extract_section(text, "Description")
        system_prompt = self._extract_section(text, "System Prompt")
        tools_raw = self._extract_section(text, "Tools")
        intent_raw = self._extract_section(text, "Intent Types")
        constraints_raw = self._extract_section(text, "Constraints")

        if not system_prompt:
            logger.debug("Skill %s has no System Prompt — skipping", name)
            return None

        tools = [t.strip() for t in re.split(r"[,\s]+", tools_raw) if t.strip()]
        intent_types = [t.strip() for t in re.split(r"[,\s]+", intent_raw) if t.strip()]
        constraints = [
            line.lstrip("- •").strip()
            for line in constraints_raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        return SkillDefinition(
            name=name,
            description=description.strip(),
            system_prompt=system_prompt.strip(),
            tools=tools,
            intent_types=intent_types,
            constraints=constraints,
            source_file=str(path),
        )

    @staticmethod
    def _extract_section(text: str, heading: str) -> str:
        """Extract content under a ## Heading until the next ## heading."""
        pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    # ── Registration ──────────────────────────────────────────────────────

    def _register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name] = skill

        # Update intent → subsystem mapping
        for intent_type in skill.intent_types:
            self._intent_map[intent_type] = skill.name

        # Register with SubsystemRegistry if available
        registry = self._get_registry()
        if registry:
            try:
                config = skill.to_subsystem_config()
                registry.register(config)
                logger.debug("Registered skill '%s' in SubsystemRegistry", skill.name)
            except Exception as exc:
                logger.warning("Failed to register skill '%s': %s", skill.name, exc)

    def _get_registry(self):
        if self._registry is not None:
            return self._registry
        try:
            from simp.projectx.subsystems import get_subsystem_registry
            self._registry = get_subsystem_registry()
            return self._registry
        except Exception:
            return None


# Module-level singleton
_engine: Optional[SkillEngine] = None


def get_skill_engine(skills_dir: Optional[str] = None) -> SkillEngine:
    global _engine
    if _engine is None:
        _engine = SkillEngine(skills_dir=skills_dir)
        _engine.load_all()
    return _engine
