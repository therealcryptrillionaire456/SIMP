"""
SIMP System Memory

Structured persistent memory for episodes, lessons, and policy candidates.
This complements the markdown/json memory layer with a queryable system of
record that future agents can use for continuity and self-improvement.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Episode:
    """A concrete runtime event or condensed execution artifact."""

    episode_type: str
    source: str
    entity: str
    summary: str
    occurred_at: str
    payload: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Lesson:
    """A promoted learning extracted from one or more episodes."""

    title: str
    summary: str
    lesson_type: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    source_episode_ids: List[str] = field(default_factory=list)
    status: str = "active"
    lesson_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)


@dataclass
class PolicyCandidate:
    """A concrete operational change proposed from lessons."""

    title: str
    rationale: str
    priority: str
    payload: Dict[str, Any] = field(default_factory=dict)
    source_lesson_ids: List[str] = field(default_factory=list)
    status: str = "proposed"
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)


class SystemMemoryStore:
    """SQLite-backed structured memory for the SIMP runtime."""

    def __init__(self, db_path: str = "memory/system_memory.sqlite3"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS episodes (
                        episode_id TEXT PRIMARY KEY,
                        episode_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        entity TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        tags_json TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS lessons (
                        lesson_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL UNIQUE,
                        summary TEXT NOT NULL,
                        lesson_type TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        evidence_json TEXT NOT NULL,
                        source_episode_ids_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS policy_candidates (
                        policy_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL UNIQUE,
                        rationale TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        source_lesson_ids_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def add_episode(self, episode: Episode) -> str:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO episodes (
                        episode_id, episode_type, source, entity, summary,
                        occurred_at, payload_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode.episode_id,
                        episode.episode_type,
                        episode.source,
                        episode.entity,
                        episode.summary,
                        episode.occurred_at,
                        json.dumps(episode.payload, default=str),
                        json.dumps(episode.tags, default=str),
                    ),
                )
                conn.commit()
                return episode.episode_id
            finally:
                conn.close()

    def upsert_lesson(self, lesson: Lesson) -> str:
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT lesson_id, created_at FROM lessons WHERE title = ?",
                    (lesson.title,),
                ).fetchone()
                lesson_id = existing["lesson_id"] if existing else lesson.lesson_id
                created_at = existing["created_at"] if existing else lesson.created_at
                conn.execute(
                    """
                    INSERT OR REPLACE INTO lessons (
                        lesson_id, title, summary, lesson_type, confidence,
                        evidence_json, source_episode_ids_json, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson_id,
                        lesson.title,
                        lesson.summary,
                        lesson.lesson_type,
                        lesson.confidence,
                        json.dumps(lesson.evidence, default=str),
                        json.dumps(lesson.source_episode_ids, default=str),
                        lesson.status,
                        created_at,
                        _utcnow(),
                    ),
                )
                conn.commit()
                return lesson_id
            finally:
                conn.close()

    def upsert_policy_candidate(self, candidate: PolicyCandidate) -> str:
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT policy_id, created_at FROM policy_candidates WHERE title = ?",
                    (candidate.title,),
                ).fetchone()
                policy_id = existing["policy_id"] if existing else candidate.policy_id
                created_at = existing["created_at"] if existing else candidate.created_at
                conn.execute(
                    """
                    INSERT OR REPLACE INTO policy_candidates (
                        policy_id, title, rationale, priority, payload_json,
                        source_lesson_ids_json, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        policy_id,
                        candidate.title,
                        candidate.rationale,
                        candidate.priority,
                        json.dumps(candidate.payload, default=str),
                        json.dumps(candidate.source_lesson_ids, default=str),
                        candidate.status,
                        created_at,
                        _utcnow(),
                    ),
                )
                conn.commit()
                return policy_id
            finally:
                conn.close()

    def list_episodes(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._list_rows(
            "SELECT * FROM episodes ORDER BY occurred_at DESC LIMIT ?",
            (limit,),
            row_type="episode",
        )

    def list_lessons(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._list_rows(
            "SELECT * FROM lessons ORDER BY updated_at DESC LIMIT ?",
            (limit,),
            row_type="lesson",
        )

    def list_policy_candidates(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._list_rows(
            "SELECT * FROM policy_candidates ORDER BY updated_at DESC LIMIT ?",
            (limit,),
            row_type="policy",
        )

    def _list_rows(
        self,
        sql: str,
        params: tuple,
        row_type: str,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()

        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if row_type == "episode":
                item["payload"] = json.loads(item.pop("payload_json"))
                item["tags"] = json.loads(item.pop("tags_json"))
            elif row_type == "lesson":
                item["evidence"] = json.loads(item.pop("evidence_json"))
                item["source_episode_ids"] = json.loads(item.pop("source_episode_ids_json"))
            else:
                item["payload"] = json.loads(item.pop("payload_json"))
                item["source_lesson_ids"] = json.loads(item.pop("source_lesson_ids_json"))
            result.append(item)
        return result
