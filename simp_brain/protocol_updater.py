"""protocol_updater.py — SIMP protocol knowledge base updater.

Part of ProjectX's self-maintaining kernel. Reads protocol changes
from commits and updates the structured KB at simp_brain/facts/protocol/.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FACTS_DIR = Path(__file__).parent / "facts" / "protocol"


def ensure_facts_dir() -> Path:
    """Ensure the protocol facts directory exists."""
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    return FACTS_DIR


def load_protocol_facts(category: str = "all") -> Dict[str, Any]:
    """Load protocol facts from the KB.

    Args:
        category: Which fact category to load, or 'all' for everything.

    Returns:
        Dict of protocol facts.
    """
    facts_dir = ensure_facts_dir()
    facts = {}

    if category == "all":
        for f in facts_dir.glob("*.json"):
            try:
                facts[f.stem] = json.loads(f.read_text())
            except json.JSONDecodeError as exc:
                logger.warning(f"Failed to load {f}: {exc}")
    else:
        path = facts_dir / f"{category}.json"
        if path.exists():
            try:
                facts = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                logger.warning(f"Failed to load {path}: {exc}")

    return facts


def save_protocol_facts(facts: Dict[str, Any], category: str = "general") -> None:
    """Save protocol facts to the KB.

    Args:
        facts: Dict of facts to save.
        category: Category name (used as filename).
    """
    facts_dir = ensure_facts_dir()
    path = facts_dir / f"{category}.json"

    enriched = {
        **facts,
        "_updated_at": datetime.now(timezone.utc).isoformat(),
        "_category": category,
    }

    path.write_text(json.dumps(enriched, indent=2, default=str))
    logger.info(f"Saved protocol facts: {path}")


def extract_protocol_changes(diff_text: str) -> List[Dict[str, Any]]:
    """Extract protocol-relevant changes from a git diff.

    Looks for changes to intent schemas, routing rules, and safety policies.

    Args:
        diff_text: Raw git diff output.

    Returns:
        List of change dicts with file, type, and description.
    """
    changes = []
    current_file = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else None

        if current_file and any(keyword in (current_file or "") for keyword in [
            "intent", "schema", "routing", "protocol", "policy", "canonical"
        ]):
            if line.startswith("+") and not line.startswith("+++"):
                changes.append({
                    "file": current_file,
                    "type": "addition",
                    "content": line[1:].strip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif line.startswith("-") and not line.startswith("---"):
                changes.append({
                    "file": current_file,
                    "type": "removal",
                    "content": line[1:].strip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    return changes


def run_protocol_sweep(repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Run a protocol sweep — diff latest commit and extract changes.

    This is the core of ProjectX's self-update loop.

    Args:
        repo_path: Path to the SIMP repo. Defaults to parent of simp_brain.

    Returns:
        Dict with sweep results.
    """
    import subprocess

    if repo_path is None:
        repo_path = str(Path(__file__).parent.parent)

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--stat"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        last_commit = result.stdout.strip()

        diff_result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--", "*.py", "*.json", "*.md"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        changes = extract_protocol_changes(diff_result.stdout)

        sweep_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_path": repo_path,
            "last_commit_summary": last_commit[:500],
            "protocol_changes": changes,
            "changes_count": len(changes),
        }

        if changes:
            save_protocol_facts(sweep_result, category="latest_sweep")
            logger.info(f"Protocol sweep complete: {len(changes)} changes found")
        else:
            logger.info("Protocol sweep complete: no protocol-relevant changes")

        return sweep_result

    except subprocess.TimeoutExpired:
        return {"error": "Git command timed out", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {"error": str(exc), "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_protocol_sweep()
    print(json.dumps(result, indent=2, default=str))
