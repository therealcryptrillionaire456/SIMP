"""
SIMP Task Memory

Manages persistent task memory as structured markdown files.
Each task gets its own .md file with standardized sections.
"""

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_TASK_TEMPLATE = """\
# {title}

## Status
{status}

## Goal
{goal}

## Current State
{current_state}

## Key Decisions
{decisions}

## Open Questions
{open_questions}

## Code Locations
{code_locations}

## Dependencies
{dependencies}

## History
{history}
"""


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:80]


class TaskMemory:
    """Manages markdown-based task memory files."""

    def __init__(self, base_dir: str = "memory/tasks"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create_task(
        self,
        title: str,
        slug: Optional[str] = None,
        status: str = "active",
        goal: str = "",
        current_state: str = "",
        decisions: Optional[List[str]] = None,
        open_questions: Optional[List[str]] = None,
        code_locations: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        history: Optional[List[str]] = None,
    ) -> str:
        """
        Create a new task memory file from the standard template.

        Returns:
            The task slug (filename stem).
        """
        slug = slug or _slugify(title)
        decisions_text = "\n".join(f"- {d}" for d in (decisions or [])) or "- (none yet)"
        questions_text = "\n".join(f"- {q}" for q in (open_questions or [])) or "- (none yet)"
        locations_text = "\n".join(f"- {loc}" for loc in (code_locations or [])) or "- (none yet)"
        deps_text = "\n".join(f"- {dep}" for dep in (dependencies or [])) or "- (none)"
        history_text = "\n".join(f"- {h}" for h in (history or [])) or f"- {datetime.utcnow().strftime('%Y-%m-%d')} — Task created"

        content = _TASK_TEMPLATE.format(
            title=title,
            status=status,
            goal=goal or "(not specified)",
            current_state=current_state or "(not specified)",
            decisions=decisions_text,
            open_questions=questions_text,
            code_locations=locations_text,
            dependencies=deps_text,
            history=history_text,
        )

        with self._lock:
            path = self.base_dir / f"{slug}.md"
            path.write_text(content)
        return slug

    def update_task(self, slug: str, updates: Dict[str, str]) -> bool:
        """
        Update specific sections of a task memory file.

        Args:
            slug: Task file slug.
            updates: Dict mapping section names to new content.
                     e.g. {"Status": "completed", "Current State": "Deployed to prod"}

        Returns:
            True if updated successfully.
        """
        with self._lock:
            path = self.base_dir / f"{slug}.md"
            if not path.exists():
                return False

            content = path.read_text()
            for section, new_value in updates.items():
                # Match "## Section\n<content>" up to next "## " or end of file
                pattern = rf"(## {re.escape(section)}\n).*?(?=\n## |\Z)"
                replacement = rf"\g<1>{new_value}"
                content = re.sub(pattern, replacement, content, flags=re.DOTALL)

            path.write_text(content)
            return True

    def add_history_entry(self, slug: str, entry: str) -> bool:
        """Append an entry to the History section."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        line = f"- {date_str} — {entry}"
        with self._lock:
            path = self.base_dir / f"{slug}.md"
            if not path.exists():
                return False

            content = path.read_text()
            # Find History section and append
            if "## History" in content:
                content = content.rstrip() + f"\n{line}\n"
            else:
                content += f"\n## History\n{line}\n"

            path.write_text(content)
            return True

    def add_decision(self, slug: str, decision: str) -> bool:
        """Add a decision to the Key Decisions section."""
        line = f"- {decision}"
        with self._lock:
            path = self.base_dir / f"{slug}.md"
            if not path.exists():
                return False

            content = path.read_text()
            # Replace "(none yet)" placeholder or append to decisions section
            if "## Key Decisions\n- (none yet)" in content:
                content = content.replace(
                    "## Key Decisions\n- (none yet)",
                    f"## Key Decisions\n{line}",
                )
            elif "## Key Decisions" in content:
                # Insert before the next section
                pattern = r"(## Key Decisions\n(?:- .*\n)*)"
                match = re.search(pattern, content)
                if match:
                    insert_pos = match.end()
                    content = content[:insert_pos] + f"{line}\n" + content[insert_pos:]

            path.write_text(content)
            return True

    def add_open_question(self, slug: str, question: str) -> bool:
        """Add a question to the Open Questions section."""
        line = f"- {question}"
        with self._lock:
            path = self.base_dir / f"{slug}.md"
            if not path.exists():
                return False

            content = path.read_text()
            if "## Open Questions\n- (none yet)" in content:
                content = content.replace(
                    "## Open Questions\n- (none yet)",
                    f"## Open Questions\n{line}",
                )
            elif "## Open Questions" in content:
                pattern = r"(## Open Questions\n(?:- .*\n)*)"
                match = re.search(pattern, content)
                if match:
                    insert_pos = match.end()
                    content = content[:insert_pos] + f"{line}\n" + content[insert_pos:]

            path.write_text(content)
            return True

    def get_task(self, slug: str) -> Optional[Dict[str, Any]]:
        """Parse a task memory markdown file into a dict."""
        with self._lock:
            path = self.base_dir / f"{slug}.md"
            if not path.exists():
                return None

            content = path.read_text()

        result: Dict[str, Any] = {"slug": slug, "raw": content}

        # Extract title
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        if title_match:
            result["title"] = title_match.group(1).strip()

        # Extract sections
        sections = re.findall(
            r"## (.+?)\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        for section_name, section_body in sections:
            key = section_name.strip().lower().replace(" ", "_")
            body = section_body.strip()

            # Parse bullet lists into arrays
            lines = [
                line.lstrip("- ").strip()
                for line in body.split("\n")
                if line.strip().startswith("- ")
            ]
            if lines:
                result[key] = lines
            else:
                result[key] = body

        # Normalize status to a simple string
        if isinstance(result.get("status"), list):
            result["status"] = result["status"][0] if result["status"] else "unknown"

        return result

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all task memory files with basic metadata."""
        tasks = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.md")):
                slug = path.stem
                content = path.read_text()

                title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else slug

                status_match = re.search(
                    r"## Status\n(.+?)(?=\n## |\Z)", content, re.DOTALL
                )
                status = status_match.group(1).strip() if status_match else "unknown"

                tasks.append({
                    "slug": slug,
                    "title": title,
                    "status": status,
                })
        return tasks
