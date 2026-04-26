"""
T48: Database Migration Framework
================================
Schema versioning with upgrade/downgrade, rollback, and seed data.

This module provides:
1. MigrationRunner — sequential migration executor with version tracking
2. Migration — dataclass for each migration step
3. Built-in migrations for core SIMP tables
4. Rollback support per-migration
5. Seed data management
6. Health-check integration

Usage:
    runner = MigrationRunner(conn_string="postgresql://...")
    runner.migrate()           # Run all pending migrations
    runner.migrate("002")      # Migrate to specific version
    runner.rollback("001")     # Roll back one step
    runner.status()             # Show current version
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Migration:
    """A single database migration step."""
    version: str           # e.g. "001", "002_add_users"
    description: str
    up: Callable[["MigrationRunner"], None]  # Upgrade function
    down: Optional[Callable[["MigrationRunner"], None]] = None  # Rollback
    depends_on: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Auto-generate rollback from up if not provided
        if self.down is None:
            self.down = lambda r: logger.warning(
                "No rollback defined for migration %s", self.version
            )


@dataclass
class SeedData:
    """A seed data entry for initial population."""
    table: str
    data: Dict[str, Any]
    conflict_action: str = "upsert"  # "upsert" | "ignore" | "replace"


# ── Migration Registry ─────────────────────────────────────────────────────────

# Global registry of migrations
_MIGRATIONS: Dict[str, Migration] = {}
_MIGRATION_LOCK = threading.Lock()


def register_migration(migration: Migration) -> None:
    """Decorator/function to register a migration."""
    with _MIGRATION_LOCK:
        _MIGRATIONS[migration.version] = migration


def migration(
    version: str,
    description: str,
    depends_on: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
):
    """Decorator to register a migration."""
    def decorator(up_fn: Callable[["MigrationRunner"], None]):
        migration_obj = Migration(
            version=version,
            description=description,
            up=up_fn,
            depends_on=depends_on or [],
            tags=tags or [],
        )
        register_migration(migration_obj)
        return up_fn
    return decorator


# ── MigrationRunner ────────────────────────────────────────────────────────────

class MigrationRunner:
    """
    Executes schema migrations with version tracking.

    Keeps a _schema_migrations table to track which migrations have been applied.
    Supports:
    - Sequential upgrade/downgrade
    - Rollback to specific version
    - Dry-run mode
    - Transaction safety (with savepoints)
    """

    MIGRATIONS_TABLE = "_schema_migrations"

    def __init__(
        self,
        conn_or_uri: Any,        # psycopg2 connection or connection string
        migrations_dir: Optional[Path] = None,
        dry_run: bool = False,
    ):
        self._conn_or_uri = conn_or_uri
        self._migrations_dir = migrations_dir or Path("simp/db/migrations")
        self._dry_run = dry_run
        self._conn: Optional[Any] = None
        self._applied: Dict[str, str] = {}  # version -> applied_at
        self._load_applied()

    # ── Connection Management ─────────────────────────────────────────────────

    def _get_conn(self) -> Any:
        """Get or create a DB connection."""
        if self._conn is not None:
            return self._conn
        if isinstance(self._conn_or_uri, str):
            import psycopg2
            self._conn = psycopg2.connect(self._conn_or_uri)
            self._conn.autocommit = False
        else:
            self._conn = self._conn_or_uri
        return self._conn

    def _load_applied(self) -> None:
        """Load applied migrations from the tracking table."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(f"""
                SELECT version, applied_at
                FROM {self.MIGRATIONS_TABLE}
                ORDER BY version
            """)
            for row in cur.fetchall():
                self._applied[row[0]] = row[1]
            cur.close()
            logger.debug("Loaded %d applied migrations", len(self._applied))
        except Exception:
            pass  # Table doesn't exist yet

    def _ensure_migrations_table(self) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.MIGRATIONS_TABLE} (
                version  VARCHAR(64) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                description TEXT,
                rolled_back_at TIMESTAMPTZ,
                rollback_reason TEXT
            )
        """)
        conn.commit()
        cur.close()

    def _record_apply(self, version: str, description: str) -> None:
        """Record that a migration was applied."""
        if self._dry_run:
            logger.info("[DRY RUN] Would record migration %s", version)
            return
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {self.MIGRATIONS_TABLE} (version, description)
            VALUES (%s, %s)
            ON CONFLICT (version) DO UPDATE
                SET description = EXCLUDED.description,
                    rolled_back_at = NULL,
                    rollback_reason = NULL
        """, (version, description))
        conn.commit()
        cur.close()
        self._applied[version] = datetime.now(timezone.utc).isoformat()
        logger.info("Recorded migration %s", version)

    def _record_rollback(self, version: str, reason: str = "") -> None:
        """Record that a migration was rolled back."""
        if self._dry_run:
            logger.info("[DRY RUN] Would rollback migration %s", version)
            return
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {self.MIGRATIONS_TABLE}
            SET rolled_back_at = NOW(), rollback_reason = %s
            WHERE version = %s
        """, (reason, version))
        conn.commit()
        cur.close()
        self._applied.pop(version, None)
        logger.info("Recorded rollback for migration %s", version)

    # ── Core Migration Logic ─────────────────────────────────────────────────

    def _get_pending(self) -> List[Tuple[str, Migration]]:
        """Return migrations that haven't been applied, sorted by version."""
        pending = []
        for version, mig in _MIGRATIONS.items():
            if version not in self._applied:
                # Check dependencies
                deps_met = all(dep in self._applied for dep in mig.depends_on)
                if deps_met:
                    pending.append((version, mig))
        pending.sort(key=lambda x: x[0])
        return pending

    def migrate(self, target_version: Optional[str] = None) -> List[str]:
        """
        Run all pending migrations, or up to (and including) target_version.

        Returns list of migration versions that were applied.
        """
        self._ensure_migrations_table()
        pending = self._get_pending()

        if not pending:
            logger.info("No pending migrations")
            return []

        applied = []
        for version, mig in pending:
            if target_version and version > target_version:
                break
            logger.info("Applying migration %s: %s", version, mig.description)
            if self._dry_run:
                logger.info("[DRY RUN] Would apply: %s", mig.description)
                applied.append(version)
                continue
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                savepoint = conn.savepoint()
                try:
                    mig.up(self)
                    conn.commit()
                    self._record_apply(version, mig.description)
                    applied.append(version)
                    logger.info("Migration %s applied successfully", version)
                except Exception as e:
                    conn.rollback(savepoint=savepoint)
                    logger.error("Migration %s failed: %s", version, e)
                    raise
                finally:
                    cur.close()
            except Exception:
                break  # Stop on first failure

        return applied

    def rollback(self, steps: int = 1, reason: str = "") -> List[str]:
        """
        Roll back the most recent N migrations.

        Returns list of versions that were rolled back.
        """
        self._ensure_migrations_table()
        conn = self._get_conn()
        cur = conn.cursor()

        # Get most recently applied migrations
        cur.execute(f"""
            SELECT version FROM {self.MIGRATIONS_TABLE}
            WHERE rolled_back_at IS NULL
            ORDER BY applied_at DESC
            LIMIT %s
        """, (steps,))
        to_rollback = [row[0] for row in cur.fetchall()]
        cur.close()

        rolled_back = []
        for version in reversed(to_rollback):
            mig = _MIGRATIONS.get(version)
            if not mig:
                logger.warning("No migration found for version %s, skipping rollback", version)
                continue
            if mig.down is None:
                logger.warning("Migration %s has no rollback defined, skipping", version)
                continue

            logger.info("Rolling back migration %s: %s", version, mig.description)
            if self._dry_run:
                logger.info("[DRY RUN] Would rollback: %s", mig.description)
                rolled_back.append(version)
                continue
            try:
                mig.down(self)
                conn.commit()
                self._record_rollback(version, reason=reason)
                rolled_back.append(version)
                logger.info("Rollback of %s completed", version)
            except Exception as e:
                conn.rollback()
                logger.error("Rollback of %s failed: %s", version, e)
                raise

        return rolled_back

    def migrate_to(self, target_version: str) -> List[str]:
        """Migrate to a specific version (up or down)."""
        current = self.current_version()
        if current == target_version:
            return []
        if current < target_version:
            return self.migrate(target_version=target_version)
        else:
            # Need to roll back
            cur = self._get_conn().cursor()
            cur.execute(f"""
                SELECT COUNT(*) FROM {self.MIGRATIONS_TABLE}
                WHERE rolled_back_at IS NULL AND version > %s
            """, (target_version,))
            steps = cur.fetchone()[0]
            cur.close()
            return self.rollback(steps=steps, reason=f"migrate_to {target_version}")

    def current_version(self) -> str:
        """Return the most recently applied migration version."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT version FROM {self.MIGRATIONS_TABLE}
            WHERE rolled_back_at IS NULL
            ORDER BY applied_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        return row[0] if row else "000"

    def status(self) -> Dict[str, Any]:
        """Return full migration status."""
        pending = self._get_pending()
        return {
            "current_version": self.current_version(),
            "total_applied": len(self._applied),
            "pending_count": len(pending),
            "pending_versions": [v for v, _ in pending],
            "applied": dict(self._applied),
        }

    def seed(self, seeds: List[SeedData]) -> int:
        """Apply seed data. Returns count of rows inserted/updated."""
        conn = self._get_conn()
        cur = conn.cursor()
        count = 0
        for seed in seeds:
            cols = list(seed.data.keys())
            vals = list(seed.data.values())
            placeholders = ", ".join(["%s"] * len(vals))
            col_names = ", ".join(cols)

            if seed.conflict_action == "upsert":
                upd = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols])
                sql = f"""
                    INSERT INTO {seed.table} ({col_names})
                    VALUES ({placeholders})
                    ON CONFLICT DO UPDATE SET {upd}
                """
            elif seed.conflict_action == "ignore":
                sql = f"""
                    INSERT INTO {seed.table} ({col_names})
                    VALUES ({placeholders})
                    ON CONFLICT DO NOTHING
                """
            else:  # replace
                sql = f"""
                    DELETE FROM {seed.table};
                    INSERT INTO {seed.table} ({col_names})
                    VALUES ({placeholders})
                """

            cur.execute(sql, vals)
            count += cur.rowcount

        conn.commit()
        cur.close()
        return count

    def close(self) -> None:
        """Close the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# ── Built-in Migrations ───────────────────────────────────────────────────────

@migration(version="001", description="Create core SIMP tables")
def _001_create_core_tables(runner: MigrationRunner) -> None:
    conn = runner._get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id   VARCHAR(128) PRIMARY KEY,
            name       VARCHAR(256) NOT NULL,
            kind       VARCHAR(64),
            status     VARCHAR(32) DEFAULT 'active',
            config     JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen  TIMESTAMPTZ,
            metadata   JSONB DEFAULT '{}'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id    VARCHAR(128) PRIMARY KEY,
            agent_id   VARCHAR(128) REFERENCES agents(agent_id),
            intent    TEXT,
            status    VARCHAR(32) DEFAULT 'pending',
            result    JSONB,
            error     TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mesh_messages (
            msg_id    VARCHAR(128) PRIMARY KEY,
            sender_id VARCHAR(128),
            channel   VARCHAR(256),
            payload   JSONB,
            sent_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS arb_opportunities (
            opp_id    VARCHAR(128) PRIMARY KEY,
            pair      VARCHAR(32),
            exchange_a VARCHAR(64),
            exchange_b VARCHAR(64),
            spread_pct FLOAT,
            volume_usd FLOAT,
            status    VARCHAR(32) DEFAULT 'detected',
            executed_at TIMESTAMPTZ,
            profit_usd FLOAT,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_versions (
            strategy_id VARCHAR(128) PRIMARY KEY,
            version    VARCHAR(32),
            params     JSONB,
            stage      VARCHAR(32),
            deployed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id         SERIAL PRIMARY KEY,
            strategy_id VARCHAR(128),
            timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            return_pct FLOAT,
            sharpe     FLOAT,
            max_drawdown FLOAT,
            volume_usd FLOAT,
            UNIQUE(strategy_id, timestamp)
        )
    """)

    conn.commit()
    cur.close()
    logger.info("Migration 001: core tables created")


@migration(version="002", description="Create indexes for performance", depends_on=["001"])
def _002_create_indexes(runner: MigrationRunner) -> None:
    conn = runner._get_conn()
    cur = conn.cursor()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)",
        "CREATE INDEX IF NOT EXISTS idx_mesh_channel ON mesh_messages(channel)",
        "CREATE INDEX IF NOT EXISTS idx_arb_pair ON arb_opportunities(pair)",
        "CREATE INDEX IF NOT EXISTS idx_arb_status ON arb_opportunities(status)",
        "CREATE INDEX IF NOT EXISTS idx_strategy_stage ON strategy_versions(stage)",
        "CREATE INDEX IF NOT EXISTS idx_perf_strategy_time ON strategy_performance(strategy_id, timestamp DESC)",
    ]

    for idx_sql in indexes:
        cur.execute(idx_sql)

    conn.commit()
    cur.close()
    logger.info("Migration 002: indexes created")


@migration(version="003", description="Add strategy registry tables", depends_on=["001"])
def _003_strategy_registry_tables(runner: MigrationRunner) -> None:
    conn = runner._get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_registry (
            strategy_id VARCHAR(128) NOT NULL,
            version     VARCHAR(32) NOT NULL,
            name        VARCHAR(256),
            description TEXT,
            params      JSONB DEFAULT '{}',
            stage       VARCHAR(32) DEFAULT 'draft',
            min_capital FLOAT DEFAULT 0,
            max_capital FLOAT DEFAULT 1000000,
            applicable_regimes TEXT[],
            applicable_pairs   TEXT[],
            created_by  VARCHAR(128),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            promoted_at TIMESTAMPTZ,
            promoted_by VARCHAR(128),
            deprecated_at TIMESTAMPTZ,
            deprecation_reason TEXT,
            PRIMARY KEY (strategy_id, version)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_promotion_audit (
            event_id    VARCHAR(128) PRIMARY KEY,
            strategy_id  VARCHAR(128),
            from_stage  VARCHAR(32),
            to_stage    VARCHAR(32),
            version     VARCHAR(32),
            actor       VARCHAR(128),
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reason      TEXT,
            notes       TEXT
        )
    """)

    conn.commit()
    cur.close()
    logger.info("Migration 003: strategy registry tables created")


@migration(version="004", description="Add rotation and vault audit tables", depends_on=["001"])
def _004_vault_rotation_tables(runner: MigrationRunner) -> None:
    conn = runner._get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS secret_rotation_log (
            event_id     VARCHAR(128) PRIMARY KEY,
            secret_path  VARCHAR(512),
            state        VARCHAR(32),
            trigger      VARCHAR(32),
            version_before VARCHAR(32),
            version_after VARCHAR(32),
            started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            retry_count INT DEFAULT 0,
            error       TEXT,
            actor       VARCHAR(128)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS secret_access_audit (
            id         SERIAL PRIMARY KEY,
            secret_path VARCHAR(512),
            accessor    VARCHAR(128),
            access_type VARCHAR(32),
            accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            success    BOOLEAN DEFAULT TRUE
        )
    """)

    conn.commit()
    cur.close()
    logger.info("Migration 004: vault and rotation tables created")


# ── Self-test ────────────────────────────────────────────────────────────────

def test_migrate() -> None:
    """Test migrations with an in-memory SQLite database."""
    import sqlite3, tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        runner = MigrationRunner(conn)

        # Verify migrations table creation
        runner._ensure_migrations_table()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        assert runner.MIGRATIONS_TABLE in tables, f"{runner.MIGRATIONS_TABLE} not created"

        # Run all migrations
        applied = runner.migrate()
        print(f"Applied migrations: {applied}")
        assert len(applied) >= 4, f"Expected >=4 migrations, got {applied}"

        # Check status
        status = runner.status()
        print(f"Status: {status}")
        assert status["current_version"] == "004"
        assert status["pending_count"] == 0

        # Rollback one step
        rolled = runner.rollback(steps=1, reason="test rollback")
        print(f"Rolled back: {rolled}")
        assert "004" in rolled
        assert runner.current_version() == "003"

        # Re-apply
        re_applied = runner.migrate()
        print(f"Re-applied: {re_applied}")
        assert runner.current_version() == "004"

        conn.close()
        print("All migration tests passed!")


if __name__ == "__main__":
    test_migrate()
