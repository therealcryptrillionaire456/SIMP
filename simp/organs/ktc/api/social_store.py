from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class KTCSocialStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_demo_content()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ktc_users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                wallet_address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_savings REAL DEFAULT 0.0,
                total_invested REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS ktc_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_posts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                product_name TEXT NOT NULL,
                original_price REAL NOT NULL,
                your_price REAL NOT NULL,
                savings_amount REAL NOT NULL,
                retailer TEXT,
                image_url TEXT,
                tags_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_follows (
                follower_id TEXT NOT NULL,
                followed_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (follower_id, followed_id)
            );

            CREATE TABLE IF NOT EXISTS ktc_post_likes (
                user_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, post_id)
            );

            CREATE TABLE IF NOT EXISTS ktc_post_saves (
                user_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, post_id)
            );

            CREATE TABLE IF NOT EXISTS ktc_post_comments (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                from_user_id TEXT,
                type TEXT NOT NULL,
                post_id TEXT,
                comment_id TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_auto_rules (
                user_id TEXT NOT NULL,
                cryptocurrency TEXT NOT NULL,
                percentage REAL NOT NULL,
                min_savings_threshold REAL NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, cryptocurrency)
            );

            CREATE TABLE IF NOT EXISTS ktc_crypto_transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                cryptocurrency TEXT NOT NULL,
                symbol TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                crypto_amount REAL NOT NULL,
                price_usd REAL NOT NULL,
                rule_percentage REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_shopper_profiles (
                user_id TEXT PRIMARY KEY,
                onboarding_complete INTEGER NOT NULL DEFAULT 0,
                google_connected INTEGER NOT NULL DEFAULT 0,
                social_links_json TEXT NOT NULL DEFAULT '[]',
                card_last4 TEXT NOT NULL DEFAULT '',
                zip_code TEXT NOT NULL DEFAULT '',
                spend_limit REAL NOT NULL DEFAULT 75.0,
                express_shipping INTEGER NOT NULL DEFAULT 1,
                preferred_crypto TEXT NOT NULL DEFAULT 'bitcoin',
                subscription_tier TEXT NOT NULL DEFAULT 'free',
                in_store_mode INTEGER NOT NULL DEFAULT 0,
                trial_hunter_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ktc_producer_offers (
                id TEXT PRIMARY KEY,
                producer_name TEXT NOT NULL,
                producer_slug TEXT NOT NULL,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                offer_price REAL NOT NULL,
                market_price REAL NOT NULL,
                shipping_fee REAL NOT NULL DEFAULT 0.0,
                express_shipping INTEGER NOT NULL DEFAULT 0,
                image_url TEXT,
                region TEXT NOT NULL DEFAULT 'national',
                tags_json TEXT NOT NULL DEFAULT '[]',
                trial_available INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'producer',
                created_at TEXT NOT NULL
            );
            """
        )

        self._ensure_column(conn, "ktc_users", "username", "TEXT")
        self._ensure_column(conn, "ktc_users", "full_name", "TEXT")
        self._ensure_column(conn, "ktc_users", "password_hash", "TEXT")
        self._ensure_column(conn, "ktc_users", "bio", "TEXT")
        self._ensure_column(conn, "ktc_users", "profile_image_url", "TEXT")
        self._ensure_column(conn, "ktc_users", "is_demo", "INTEGER DEFAULT 0")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ktc_users_username ON ktc_users(username)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ktc_posts_created_at ON ktc_posts(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ktc_notifications_user_read ON ktc_notifications(user_id, is_read)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ktc_offers_item_name ON ktc_producer_offers(item_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ktc_offers_category ON ktc_producer_offers(category)"
        )
        conn.commit()
        conn.close()

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _seed_demo_content(self) -> None:
        conn = self._connect()
        existing = conn.execute("SELECT COUNT(*) AS count FROM ktc_users").fetchone()["count"]
        if not existing:
            now = datetime.utcnow()
            demo_users = [
                {
                    "id": "demo_alex",
                    "username": "alexdeals",
                    "email": "alex@keepthechange.demo",
                    "full_name": "Alex Rivera",
                    "bio": "Finds pantry wins and auto-invests the difference.",
                    "profile_image_url": "",
                    "total_savings": 214.45,
                    "total_invested": 83.2,
                },
                {
                    "id": "demo_maya",
                    "username": "mayasaves",
                    "email": "maya@keepthechange.demo",
                    "full_name": "Maya Chen",
                    "bio": "Beauty deals, grocery math, and long-term crypto.",
                    "profile_image_url": "",
                    "total_savings": 184.1,
                    "total_invested": 71.9,
                },
                {
                    "id": "demo_noah",
                    "username": "noahshopsmart",
                    "email": "noah@keepthechange.demo",
                    "full_name": "Noah Brooks",
                    "bio": "Every deal gets posted. Every dollar gets a job.",
                    "profile_image_url": "",
                    "total_savings": 263.77,
                    "total_invested": 109.55,
                },
            ]
            for user in demo_users:
                conn.execute(
                    """
                    INSERT INTO ktc_users (
                        id, email, wallet_address, created_at, total_savings, total_invested,
                        username, full_name, password_hash, bio, profile_image_url, is_demo
                    ) VALUES (?, ?, '', ?, ?, ?, ?, ?, '', ?, ?, 1)
                    """,
                    (
                        user["id"],
                        user["email"],
                        _utc_now(),
                        user["total_savings"],
                        user["total_invested"],
                        user["username"],
                        user["full_name"],
                        user["bio"],
                        user["profile_image_url"],
                    ),
                )

            demo_posts = [
                {
                    "id": "post_demo_1",
                    "user_id": "demo_alex",
                    "title": "Grabbed the same oats for way less this week.",
                    "description": "Swapped stores and banked enough to send a little more into SOL.",
                    "product_name": "Organic Rolled Oats",
                    "original_price": 8.49,
                    "your_price": 5.99,
                    "retailer": "Target",
                    "image_url": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?w=900&auto=format&fit=crop",
                    "tags": ["grocery", "deal", "oats"],
                },
                {
                    "id": "post_demo_2",
                    "user_id": "demo_maya",
                    "title": "Weekend skincare restock, but not at mall pricing.",
                    "description": "Price compared three stores and kept the savings moving into BTC.",
                    "product_name": "Vitamin C Serum",
                    "original_price": 39.0,
                    "your_price": 27.0,
                    "retailer": "Amazon",
                    "image_url": "https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=900&auto=format&fit=crop",
                    "tags": ["beauty", "skincare", "btc"],
                },
                {
                    "id": "post_demo_3",
                    "user_id": "demo_noah",
                    "title": "Meal prep haul came in under budget again.",
                    "description": "Bulk chicken, rice, fruit, and a clean auto-invest on the change.",
                    "product_name": "Meal Prep Grocery Haul",
                    "original_price": 64.35,
                    "your_price": 49.8,
                    "retailer": "Walmart",
                    "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=900&auto=format&fit=crop",
                    "tags": ["mealprep", "walmart", "savings"],
                },
            ]
            for index, post in enumerate(demo_posts):
                created_at = (now - timedelta(hours=(index + 1) * 5)).replace(microsecond=0).isoformat() + "Z"
                savings = round(post["original_price"] - post["your_price"], 2)
                conn.execute(
                    """
                    INSERT INTO ktc_posts (
                        id, user_id, title, description, product_name,
                        original_price, your_price, savings_amount, retailer,
                        image_url, tags_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post["id"],
                        post["user_id"],
                        post["title"],
                        post["description"],
                        post["product_name"],
                        post["original_price"],
                        post["your_price"],
                        savings,
                        post["retailer"],
                        post["image_url"],
                        json.dumps(post["tags"]),
                        created_at,
                    ),
                )

            conn.execute(
                "INSERT OR IGNORE INTO ktc_post_likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                ("demo_maya", "post_demo_1", _utc_now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO ktc_post_likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                ("demo_noah", "post_demo_1", _utc_now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO ktc_post_likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                ("demo_alex", "post_demo_2", _utc_now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO ktc_follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                ("demo_maya", "demo_alex", _utc_now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO ktc_follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                ("demo_noah", "demo_alex", _utc_now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO ktc_follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                ("demo_alex", "demo_maya", _utc_now()),
            )

        offer_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_producer_offers"
        ).fetchone()["count"]
        if offer_count == 0:
            demo_offers = [
                {
                    "id": "offer_berries",
                    "producer_name": "Blue Orchard Co.",
                    "producer_slug": "blue-orchard",
                    "item_name": "Organic Strawberries",
                    "category": "produce",
                    "offer_price": 4.29,
                    "market_price": 6.19,
                    "shipping_fee": 1.49,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1464965911861-746a04b4bca6?w=900&auto=format&fit=crop",
                    "tags": ["organic", "berry-box", "express"],
                    "trial_available": 1,
                },
                {
                    "id": "offer_yogurt",
                    "producer_name": "Peak Culture Dairy",
                    "producer_slug": "peak-culture",
                    "item_name": "Greek Yogurt",
                    "category": "dairy",
                    "offer_price": 4.89,
                    "market_price": 6.25,
                    "shipping_fee": 0.99,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=900&auto=format&fit=crop",
                    "tags": ["protein", "breakfast"],
                    "trial_available": 0,
                },
                {
                    "id": "offer_spinach",
                    "producer_name": "GreenLine Growers",
                    "producer_slug": "greenline-growers",
                    "item_name": "Baby Spinach",
                    "category": "produce",
                    "offer_price": 2.39,
                    "market_price": 3.69,
                    "shipping_fee": 0.89,
                    "express_shipping": 0,
                    "image_url": "https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=900&auto=format&fit=crop",
                    "tags": ["greens", "salad"],
                    "trial_available": 0,
                },
                {
                    "id": "offer_chicken",
                    "producer_name": "Prairie Reserve Meats",
                    "producer_slug": "prairie-reserve",
                    "item_name": "Chicken Breast",
                    "category": "protein",
                    "offer_price": 10.99,
                    "market_price": 14.49,
                    "shipping_fee": 2.49,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=900&auto=format&fit=crop",
                    "tags": ["family-pack", "high-protein"],
                    "trial_available": 0,
                },
                {
                    "id": "offer_oats",
                    "producer_name": "Morning Forge Foods",
                    "producer_slug": "morning-forge",
                    "item_name": "Organic Rolled Oats",
                    "category": "pantry",
                    "offer_price": 5.19,
                    "market_price": 8.49,
                    "shipping_fee": 0.0,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?w=900&auto=format&fit=crop",
                    "tags": ["fiber", "bulk-buy"],
                    "trial_available": 1,
                },
                {
                    "id": "offer_serum",
                    "producer_name": "Luma Skin Lab",
                    "producer_slug": "luma-skin",
                    "item_name": "Vitamin C Serum",
                    "category": "beauty",
                    "offer_price": 26.5,
                    "market_price": 39.0,
                    "shipping_fee": 0.0,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=900&auto=format&fit=crop",
                    "tags": ["skincare", "brightening"],
                    "trial_available": 1,
                },
                {
                    "id": "offer_oatmilk",
                    "producer_name": "River Oat Collective",
                    "producer_slug": "river-oat",
                    "item_name": "Unsweetened Oat Milk",
                    "category": "beverages",
                    "offer_price": 3.59,
                    "market_price": 4.99,
                    "shipping_fee": 1.29,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=900&auto=format&fit=crop",
                    "tags": ["dairy-free", "breakfast"],
                    "trial_available": 1,
                },
                {
                    "id": "offer_bread",
                    "producer_name": "Hearth & Grain",
                    "producer_slug": "hearth-grain",
                    "item_name": "Whole Wheat Bread",
                    "category": "bakery",
                    "offer_price": 2.79,
                    "market_price": 4.19,
                    "shipping_fee": 0.99,
                    "express_shipping": 0,
                    "image_url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=900&auto=format&fit=crop",
                    "tags": ["bakery", "daily-staple"],
                    "trial_available": 0,
                },
                {
                    "id": "offer_coffee",
                    "producer_name": "North Roast Supply",
                    "producer_slug": "north-roast",
                    "item_name": "Cold Brew Coffee",
                    "category": "beverages",
                    "offer_price": 6.49,
                    "market_price": 8.39,
                    "shipping_fee": 0.0,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=900&auto=format&fit=crop",
                    "tags": ["caffeine", "grab-and-go"],
                    "trial_available": 1,
                },
                {
                    "id": "offer_salmon",
                    "producer_name": "Harbor Catch Direct",
                    "producer_slug": "harbor-catch",
                    "item_name": "Atlantic Salmon Fillet",
                    "category": "protein",
                    "offer_price": 12.99,
                    "market_price": 17.49,
                    "shipping_fee": 2.99,
                    "express_shipping": 1,
                    "image_url": "https://images.unsplash.com/photo-1544943910-4c1dc44aab44?w=900&auto=format&fit=crop",
                    "tags": ["omega-3", "flash-sale"],
                    "trial_available": 0,
                },
            ]
            for offer in demo_offers:
                conn.execute(
                    """
                    INSERT INTO ktc_producer_offers (
                        id, producer_name, producer_slug, item_name, category, offer_price,
                        market_price, shipping_fee, express_shipping, image_url, region,
                        tags_json, trial_available, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'national', ?, ?, 'producer', ?)
                    """,
                    (
                        offer["id"],
                        offer["producer_name"],
                        offer["producer_slug"],
                        offer["item_name"],
                        offer["category"],
                        offer["offer_price"],
                        offer["market_price"],
                        offer["shipping_fee"],
                        offer["express_shipping"],
                        offer["image_url"],
                        json.dumps(offer["tags"]),
                        offer["trial_available"],
                        _utc_now(),
                    ),
                )

        conn.commit()
        conn.close()

    def _user_counts(self, conn: sqlite3.Connection, user_id: str) -> Dict[str, int]:
        posts_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_posts WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        followers_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_follows WHERE followed_id = ?",
            (user_id,),
        ).fetchone()["count"]
        following_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_follows WHERE follower_id = ?",
            (user_id,),
        ).fetchone()["count"]
        return {
            "posts_count": posts_count,
            "followers_count": followers_count,
            "following_count": following_count,
        }

    def _serialize_user(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        viewer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        counts = self._user_counts(conn, row["id"])
        is_following = False
        if viewer_id and viewer_id != row["id"]:
            result = conn.execute(
                "SELECT 1 FROM ktc_follows WHERE follower_id = ? AND followed_id = ?",
                (viewer_id, row["id"]),
            ).fetchone()
            is_following = result is not None
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "full_name": row["full_name"] or row["username"],
            "bio": row["bio"] or "",
            "profile_image_url": row["profile_image_url"] or "",
            "total_savings": float(row["total_savings"] or 0.0),
            "total_crypto_invested": float(row["total_invested"] or 0.0),
            "is_following": is_following,
            **counts,
        }

    def _author_payload(self, conn: sqlite3.Connection, user_id: str) -> Dict[str, Any]:
        user = conn.execute(
            "SELECT * FROM ktc_users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return {
            "id": user["id"],
            "username": user["username"],
            "profile_image_url": user["profile_image_url"] or "",
        }

    def _serialize_post(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        viewer_id: Optional[str],
    ) -> Dict[str, Any]:
        likes_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_post_likes WHERE post_id = ?",
            (row["id"],),
        ).fetchone()["count"]
        comments_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_post_comments WHERE post_id = ?",
            (row["id"],),
        ).fetchone()["count"]
        is_liked = False
        is_saved = False
        if viewer_id:
            is_liked = conn.execute(
                "SELECT 1 FROM ktc_post_likes WHERE post_id = ? AND user_id = ?",
                (row["id"], viewer_id),
            ).fetchone() is not None
            is_saved = conn.execute(
                "SELECT 1 FROM ktc_post_saves WHERE post_id = ? AND user_id = ?",
                (row["id"], viewer_id),
            ).fetchone() is not None

        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []

        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "product_name": row["product_name"],
            "original_price": float(row["original_price"] or 0.0),
            "your_price": float(row["your_price"] or 0.0),
            "savings_amount": float(row["savings_amount"] or 0.0),
            "retailer": row["retailer"] or "",
            "image_url": row["image_url"] or "",
            "tags": tags,
            "created_at": row["created_at"],
            "likes_count": likes_count,
            "comments_count": comments_count,
            "is_liked": is_liked,
            "is_saved": is_saved,
            "author": self._author_payload(conn, row["user_id"]),
        }

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self._connect()
        existing = conn.execute(
            "SELECT 1 FROM ktc_users WHERE email = ? OR username = ?",
            (email.lower(), username.lower()),
        ).fetchone()
        if existing:
            conn.close()
            raise ValueError("An account with that email or username already exists.")

        user_id = str(uuid.uuid4())
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO ktc_users (
                id, email, wallet_address, created_at, total_savings, total_invested,
                username, full_name, password_hash, bio, profile_image_url, is_demo
            ) VALUES (?, ?, '', ?, 0, 0, ?, ?, ?, '', '', 0)
            """,
            (
                user_id,
                email.lower(),
                now,
                username.lower(),
                (full_name or username).strip(),
                _hash_password(password),
            ),
        )
        token = self._create_session(conn, user_id)
        row = conn.execute("SELECT * FROM ktc_users WHERE id = ?", (user_id,)).fetchone()
        user = self._serialize_user(conn, row, viewer_id=user_id)
        conn.commit()
        conn.close()
        user["token"] = token
        return user

    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM ktc_users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        if not row or (row["password_hash"] or "") != _hash_password(password):
            conn.close()
            raise ValueError("Invalid email or password.")

        token = self._create_session(conn, row["id"])
        user = self._serialize_user(conn, row, viewer_id=row["id"])
        conn.commit()
        conn.close()
        user["token"] = token
        return user

    def _create_session(self, conn: sqlite3.Connection, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO ktc_sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, _utc_now()),
        )
        return token

    def delete_session(self, token: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM ktc_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    def get_user_by_token(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        conn = self._connect()
        row = conn.execute(
            """
            SELECT u.*
            FROM ktc_sessions s
            JOIN ktc_users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            conn.close()
            return None
        user = self._serialize_user(conn, row, viewer_id=row["id"])
        conn.close()
        return user

    def get_user(self, user_id: str, viewer_id: Optional[str]) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM ktc_users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            conn.close()
            return None
        user = self._serialize_user(conn, row, viewer_id=viewer_id)
        conn.close()
        return user

    def update_profile(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        conn.execute(
            """
            UPDATE ktc_users
            SET full_name = ?, bio = ?, profile_image_url = ?
            WHERE id = ?
            """,
            (
                (payload.get("full_name") or "").strip(),
                (payload.get("bio") or "").strip(),
                (payload.get("profile_image_url") or "").strip(),
                user_id,
            ),
        )
        row = conn.execute("SELECT * FROM ktc_users WHERE id = ?", (user_id,)).fetchone()
        user = self._serialize_user(conn, row, viewer_id=user_id)
        conn.commit()
        conn.close()
        return user

    def search_users(self, viewer_id: str, query: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        pattern = f"%{query.strip().lower()}%"
        rows = conn.execute(
            """
            SELECT * FROM ktc_users
            WHERE id != ?
              AND (LOWER(username) LIKE ? OR LOWER(COALESCE(full_name, '')) LIKE ?)
            ORDER BY is_demo DESC, created_at DESC
            LIMIT 20
            """,
            (viewer_id, pattern, pattern),
        ).fetchall()
        users = [self._serialize_user(conn, row, viewer_id=viewer_id) for row in rows]
        conn.close()
        return users

    def suggested_users(self, viewer_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT *
            FROM ktc_users
            WHERE id != ?
              AND id NOT IN (
                SELECT followed_id FROM ktc_follows WHERE follower_id = ?
              )
            ORDER BY is_demo DESC, total_savings DESC, created_at DESC
            LIMIT 8
            """,
            (viewer_id, viewer_id),
        ).fetchall()
        users = [self._serialize_user(conn, row, viewer_id=viewer_id) for row in rows]
        conn.close()
        return users

    def _default_subscription_tiers(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "free",
                "name": "Free",
                "monthly_price": 0,
                "offer_access": "Top marketplace offers",
                "return_share": 0.0,
                "assistant_scope": "Single basket planning",
            },
            {
                "id": "plus",
                "name": "Plus",
                "monthly_price": 12,
                "offer_access": "Priority offers + faster reroutes",
                "return_share": 0.15,
                "assistant_scope": "Multi-store optimization",
            },
            {
                "id": "pro",
                "name": "Pro",
                "monthly_price": 29,
                "offer_access": "Producer-direct inventory and trial drops",
                "return_share": 0.25,
                "assistant_scope": "Family basket + predictive replenishment",
            },
        ]

    def list_subscription_tiers(self) -> List[Dict[str, Any]]:
        return self._default_subscription_tiers()

    def _ensure_shopper_profile(self, conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        existing = conn.execute(
            "SELECT * FROM ktc_shopper_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if existing:
            return existing
        conn.execute(
            """
            INSERT INTO ktc_shopper_profiles (
                user_id, onboarding_complete, google_connected, social_links_json,
                card_last4, zip_code, spend_limit, express_shipping, preferred_crypto,
                subscription_tier, in_store_mode, trial_hunter_enabled, updated_at
            ) VALUES (?, 0, 0, '[]', '', '', 75.0, 1, 'bitcoin', 'free', 0, 1, ?)
            """,
            (user_id, _utc_now()),
        )
        return conn.execute(
            "SELECT * FROM ktc_shopper_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    def _serialize_shopper_profile(self, row: sqlite3.Row) -> Dict[str, Any]:
        try:
            social_links = json.loads(row["social_links_json"] or "[]")
        except json.JSONDecodeError:
            social_links = []
        return {
            "onboarding_complete": bool(row["onboarding_complete"]),
            "google_connected": bool(row["google_connected"]),
            "social_links": social_links,
            "card_last4": row["card_last4"] or "",
            "zip_code": row["zip_code"] or "",
            "spend_limit": float(row["spend_limit"] or 75.0),
            "express_shipping": bool(row["express_shipping"]),
            "preferred_crypto": row["preferred_crypto"] or "bitcoin",
            "subscription_tier": row["subscription_tier"] or "free",
            "in_store_mode": bool(row["in_store_mode"]),
            "trial_hunter_enabled": bool(row["trial_hunter_enabled"]),
            "updated_at": row["updated_at"],
        }

    def get_shopper_profile(self, user_id: str) -> Dict[str, Any]:
        conn = self._connect()
        row = self._ensure_shopper_profile(conn, user_id)
        profile = self._serialize_shopper_profile(row)
        conn.commit()
        conn.close()
        return profile

    def save_shopper_profile(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        existing = self._serialize_shopper_profile(self._ensure_shopper_profile(conn, user_id))
        social_links = payload.get("social_links", existing["social_links"])
        if not isinstance(social_links, list):
            social_links = existing["social_links"]
        social_links = [str(link).strip() for link in social_links if str(link).strip()]
        card_last4 = "".join(ch for ch in str(payload.get("card_last4", existing["card_last4"])) if ch.isdigit())[-4:]
        zip_code = "".join(ch for ch in str(payload.get("zip_code", existing["zip_code"])) if ch.isdigit())[:5]
        spend_limit = float(payload.get("spend_limit") or existing["spend_limit"] or 75.0)
        express_shipping = 1 if payload.get("express_shipping", existing["express_shipping"]) else 0
        google_connected = 1 if payload.get("google_connected", existing["google_connected"]) else 0
        in_store_mode = 1 if payload.get("in_store_mode", existing["in_store_mode"]) else 0
        trial_hunter_enabled = 1 if payload.get("trial_hunter_enabled", existing["trial_hunter_enabled"]) else 0
        preferred_crypto = (payload.get("preferred_crypto") or existing["preferred_crypto"] or "bitcoin").strip().lower()
        tier_ids = {tier["id"] for tier in self._default_subscription_tiers()}
        subscription_tier = (payload.get("subscription_tier") or existing["subscription_tier"] or "free").strip().lower()
        if subscription_tier not in tier_ids:
            subscription_tier = "free"
        onboarding_complete = 1 if (
            payload.get("onboarding_complete")
            or (google_connected and zip_code and spend_limit > 0)
        ) else 0
        updated_at = _utc_now()
        conn.execute(
            """
            INSERT INTO ktc_shopper_profiles (
                user_id, onboarding_complete, google_connected, social_links_json,
                card_last4, zip_code, spend_limit, express_shipping, preferred_crypto,
                subscription_tier, in_store_mode, trial_hunter_enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                onboarding_complete = excluded.onboarding_complete,
                google_connected = excluded.google_connected,
                social_links_json = excluded.social_links_json,
                card_last4 = excluded.card_last4,
                zip_code = excluded.zip_code,
                spend_limit = excluded.spend_limit,
                express_shipping = excluded.express_shipping,
                preferred_crypto = excluded.preferred_crypto,
                subscription_tier = excluded.subscription_tier,
                in_store_mode = excluded.in_store_mode,
                trial_hunter_enabled = excluded.trial_hunter_enabled,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                onboarding_complete,
                google_connected,
                json.dumps(social_links),
                card_last4,
                zip_code,
                spend_limit,
                express_shipping,
                preferred_crypto,
                subscription_tier,
                in_store_mode,
                trial_hunter_enabled,
                updated_at,
            ),
        )
        row = conn.execute(
            "SELECT * FROM ktc_shopper_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        profile = self._serialize_shopper_profile(row)
        conn.commit()
        conn.close()
        return profile

    def _serialize_offer(self, row: sqlite3.Row) -> Dict[str, Any]:
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        savings_amount = round(float(row["market_price"]) - float(row["offer_price"]), 2)
        return {
            "id": row["id"],
            "producer_name": row["producer_name"],
            "producer_slug": row["producer_slug"],
            "item_name": row["item_name"],
            "category": row["category"],
            "offer_price": float(row["offer_price"]),
            "market_price": float(row["market_price"]),
            "shipping_fee": float(row["shipping_fee"]),
            "express_shipping": bool(row["express_shipping"]),
            "image_url": row["image_url"] or "",
            "region": row["region"] or "national",
            "tags": tags,
            "trial_available": bool(row["trial_available"]),
            "source": row["source"] or "producer",
            "savings_amount": savings_amount,
            "savings_percent": round((savings_amount / float(row["market_price"])) * 100, 1)
            if float(row["market_price"])
            else 0.0,
        }

    def list_producer_offers(
        self,
        query: str = "",
        category: Optional[str] = None,
        limit: int = 24,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT *
            FROM ktc_producer_offers
            ORDER BY (market_price - offer_price) DESC, express_shipping DESC, created_at DESC
            """
        ).fetchall()
        offers = [self._serialize_offer(row) for row in rows]
        query_text = query.strip().lower()
        if category and category != "all":
            offers = [offer for offer in offers if offer["category"] == category]
        if query_text:
            offers = [
                offer
                for offer in offers
                if query_text in offer["item_name"].lower()
                or query_text in offer["producer_name"].lower()
                or any(query_text in tag.lower() for tag in offer["tags"])
            ]
        conn.close()
        return offers[: max(1, limit)]

    def _rank_offer_matches(
        self,
        item_name: str,
        require_express: bool,
    ) -> List[Dict[str, Any]]:
        normalized = item_name.strip().lower()
        tokens = [token for token in normalized.replace(",", " ").split() if token]
        offers = self.list_producer_offers(limit=100)
        matches = []
        for offer in offers:
            haystacks = [offer["item_name"].lower(), offer["producer_name"].lower()] + [
                tag.lower() for tag in offer["tags"]
            ]
            score = 0
            if normalized and normalized in offer["item_name"].lower():
                score += 5
            for token in tokens:
                if any(token in haystack for haystack in haystacks):
                    score += 2
            if score <= 0:
                continue
            if require_express and not offer["express_shipping"]:
                score -= 2
            effective_total = offer["offer_price"] + offer["shipping_fee"]
            matches.append((score, effective_total, offer))
        matches.sort(key=lambda item: (-item[0], item[1], -item[2]["savings_amount"]))
        return [item[2] for item in matches]

    def generate_shopping_plan(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        profile = self._serialize_shopper_profile(self._ensure_shopper_profile(conn, user_id))
        conn.commit()
        conn.close()

        raw_items = payload.get("items") or []
        parsed_items = []
        for entry in raw_items:
            if isinstance(entry, str):
                name = entry.strip()
                quantity = 1
            elif isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                try:
                    quantity = max(1, int(entry.get("quantity") or 1))
                except (TypeError, ValueError):
                    quantity = 1
            else:
                continue
            if name:
                parsed_items.append({"name": name, "quantity": quantity})
        if not parsed_items:
            raise ValueError("Add at least one item to build a shopper plan.")

        budget_cap = float(payload.get("budget_cap") or profile["spend_limit"] or 75.0)
        tip_amount = round(float(payload.get("tip_amount") or 0.0), 2)
        require_express = bool(payload.get("express_shipping", profile["express_shipping"]))
        preferred_crypto = (
            payload.get("preferred_crypto")
            or profile["preferred_crypto"]
            or "bitcoin"
        ).strip().lower()
        subscription_tier = (
            payload.get("subscription_tier")
            or profile["subscription_tier"]
            or "free"
        ).strip().lower()
        tiers = {tier["id"]: tier for tier in self._default_subscription_tiers()}
        tier = tiers.get(subscription_tier, tiers["free"])

        planned_items = []
        total_estimated = 0.0
        total_market = 0.0
        unavailable_count = 0
        express_ready_count = 0

        for item in parsed_items:
            matches = self._rank_offer_matches(item["name"], require_express)
            if not matches and require_express:
                matches = self._rank_offer_matches(item["name"], False)
            if not matches:
                unavailable_count += 1
                planned_items.append(
                    {
                        "requested_item": item["name"],
                        "quantity": item["quantity"],
                        "status": "unavailable",
                        "reason": "No producer-direct offer matched this item yet.",
                        "alternatives": [],
                    }
                )
                continue

            selected = matches[0]
            alternatives = matches[1:3]
            line_market = round(selected["market_price"] * item["quantity"], 2)
            line_total = round(selected["offer_price"] * item["quantity"] + selected["shipping_fee"], 2)
            line_savings = round(line_market - line_total, 2)
            total_market += line_market
            total_estimated += line_total
            if selected["express_shipping"]:
                express_ready_count += 1
            planned_items.append(
                {
                    "requested_item": item["name"],
                    "quantity": item["quantity"],
                    "status": "ready",
                    "selected_offer": {
                        **selected,
                        "line_market_price": line_market,
                        "line_total": line_total,
                        "line_savings": line_savings,
                    },
                    "alternatives": [
                        {
                            **offer,
                            "line_total": round(
                                offer["offer_price"] * item["quantity"] + offer["shipping_fee"],
                                2,
                            ),
                        }
                        for offer in alternatives
                    ],
                }
            )

        total_estimated = round(total_estimated, 2)
        total_market = round(total_market, 2)
        total_savings = round(total_market - total_estimated, 2)
        agent_keep_amount = max(total_savings, 0.0)
        agent_capital = round(agent_keep_amount + tip_amount, 2)
        projected_return_rate = 0.06
        projected_agent_return = round(agent_capital * projected_return_rate, 2)
        projected_user_share = round(projected_agent_return * tier["return_share"], 2)

        if total_estimated == 0:
            status = "rejected"
            decision = "No matched offers were strong enough to execute."
        elif total_estimated > budget_cap:
            status = "rejected"
            decision = "Rejected because the optimized basket still exceeds your spend limit."
        elif unavailable_count:
            status = "needs_review"
            decision = "Partially accepted. Some list items still need manual review."
        else:
            status = "accepted"
            decision = "Accepted. Basket is within your spend cap and ready for checkout routing."

        predicted_items = []
        lower_names = " ".join(item["name"].lower() for item in parsed_items)
        if "oat" in lower_names or "yogurt" in lower_names:
            predicted_items.append("Protein granola cups")
        if "spinach" in lower_names or "salmon" in lower_names:
            predicted_items.append("Lemon herb seasoning pack")
        if "coffee" in lower_names:
            predicted_items.append("Cold foam starter kit")

        free_trials = [
            offer["item_name"]
            for offer in self.list_producer_offers(limit=50)
            if offer["trial_available"] and any(
                token in offer["item_name"].lower()
                for item in parsed_items
                for token in item["name"].lower().split()
            )
        ][:3]

        purchase_log = [
            {
                "step": "Scan list",
                "status": "complete",
                "detail": f"Parsed {len(parsed_items)} list items against producer offers.",
            },
            {
                "step": "Compare offers",
                "status": "complete",
                "detail": f"Selected {len([item for item in planned_items if item['status'] == 'ready'])} lowest-cost producer offers.",
            },
            {
                "step": "Budget gate",
                "status": "complete" if total_estimated <= budget_cap else "blocked",
                "detail": f"Basket total ${total_estimated:.2f} against stop-limit ${budget_cap:.2f}.",
            },
            {
                "step": "Checkout route",
                "status": "ready" if status == "accepted" else "review",
                "detail": f"{express_ready_count} items can route via express-capable sellers.",
            },
            {
                "step": "Agent reinvest",
                "status": "ready",
                "detail": f"${agent_capital:.2f} available for the agent to route into {preferred_crypto}.",
            },
        ]

        return {
            "status": status,
            "decision": decision,
            "budget_cap": budget_cap,
            "tip_amount": tip_amount,
            "subscription_tier": tier,
            "preferred_crypto": preferred_crypto,
            "require_express": require_express,
            "summary": {
                "items_requested": len(parsed_items),
                "items_matched": len([item for item in planned_items if item["status"] == "ready"]),
                "items_unavailable": unavailable_count,
                "total_market_price": total_market,
                "total_estimated_price": total_estimated,
                "total_savings": total_savings,
                "agent_keep_amount": agent_keep_amount,
                "agent_capital": agent_capital,
                "projected_agent_return": projected_agent_return,
                "projected_user_share": projected_user_share,
            },
            "items": planned_items,
            "purchase_log": purchase_log,
            "predicted_items": predicted_items,
            "free_trials": free_trials,
            "recommendations": [
                "Link Google and at least one social account so the assistant can personalize future baskets."
                if not profile["google_connected"]
                else "Your Google account is linked for assistant context.",
                "Turn on in-store mode to unlock shelf-scan comparisons for physical shopping."
                if not profile["in_store_mode"]
                else "In-store mode is enabled for shelf scans.",
                "Upgrade your subscription tier if you want a share of the agent's reinvest returns."
                if tier["return_share"] == 0
                else f"Your {tier['name']} tier currently earns {int(tier['return_share'] * 100)}% of projected agent tip returns.",
            ],
        }

    def follow_user(self, follower_id: str, followed_id: str) -> None:
        if follower_id == followed_id:
            raise ValueError("You cannot follow yourself.")
        conn = self._connect()
        target = conn.execute(
            "SELECT 1 FROM ktc_users WHERE id = ?",
            (followed_id,),
        ).fetchone()
        if not target:
            conn.close()
            raise ValueError("User not found.")
        conn.execute(
            """
            INSERT OR IGNORE INTO ktc_follows (follower_id, followed_id, created_at)
            VALUES (?, ?, ?)
            """,
            (follower_id, followed_id, _utc_now()),
        )
        self._create_notification(
            conn,
            user_id=followed_id,
            from_user_id=follower_id,
            notification_type="follow",
        )
        conn.commit()
        conn.close()

    def unfollow_user(self, follower_id: str, followed_id: str) -> None:
        conn = self._connect()
        conn.execute(
            "DELETE FROM ktc_follows WHERE follower_id = ? AND followed_id = ?",
            (follower_id, followed_id),
        )
        conn.commit()
        conn.close()

    def list_posts(self, viewer_id: Optional[str], explore: bool = False) -> List[Dict[str, Any]]:
        conn = self._connect()
        order_by = (
            "(SELECT COUNT(*) FROM ktc_post_likes l WHERE l.post_id = p.id) DESC, p.created_at DESC"
            if explore
            else "p.created_at DESC"
        )
        rows = conn.execute(
            f"SELECT p.* FROM ktc_posts p ORDER BY {order_by} LIMIT 50"
        ).fetchall()
        posts = [self._serialize_post(conn, row, viewer_id) for row in rows]
        conn.close()
        return posts

    def list_user_posts(self, user_id: str, viewer_id: Optional[str]) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM ktc_posts WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        posts = [self._serialize_post(conn, row, viewer_id) for row in rows]
        conn.close()
        return posts

    def create_post(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        post_id = str(uuid.uuid4())
        original_price = float(payload.get("original_price") or 0.0)
        your_price = float(payload.get("your_price") or 0.0)
        savings = round(max(0.0, original_price - your_price), 2)
        created_at = _utc_now()
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            tags = []

        conn.execute(
            """
            INSERT INTO ktc_posts (
                id, user_id, title, description, product_name,
                original_price, your_price, savings_amount, retailer,
                image_url, tags_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                user_id,
                (payload.get("title") or "").strip(),
                (payload.get("description") or "").strip(),
                (payload.get("product_name") or "").strip(),
                original_price,
                your_price,
                savings,
                (payload.get("retailer") or "").strip(),
                (payload.get("image_url") or "").strip(),
                json.dumps(tags),
                created_at,
            ),
        )
        conn.execute(
            "UPDATE ktc_users SET total_savings = total_savings + ? WHERE id = ?",
            (savings, user_id),
        )

        auto_invested = self._apply_auto_rules(conn, user_id=user_id, savings_amount=savings)

        row = conn.execute("SELECT * FROM ktc_posts WHERE id = ?", (post_id,)).fetchone()
        post = self._serialize_post(conn, row, viewer_id=user_id)
        conn.commit()
        conn.close()
        return {
            **post,
            "auto_invested": auto_invested,
        }

    def _apply_auto_rules(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        savings_amount: float,
    ) -> List[Dict[str, Any]]:
        if savings_amount <= 0:
            return []
        rows = conn.execute(
            """
            SELECT * FROM ktc_auto_rules
            WHERE user_id = ? AND is_enabled = 1 AND min_savings_threshold <= ?
            ORDER BY updated_at DESC
            """,
            (user_id, savings_amount),
        ).fetchall()
        results = []
        for row in rows:
            amount_usd = round(savings_amount * (float(row["percentage"]) / 100.0), 2)
            if amount_usd <= 0:
                continue
            results.append(
                self._create_investment_record(
                    conn,
                    user_id=user_id,
                    amount_usd=amount_usd,
                    cryptocurrency=row["cryptocurrency"],
                    tx_type="auto_buy",
                    rule_percentage=float(row["percentage"]),
                )
            )
        return results

    def toggle_like(self, user_id: str, post_id: str) -> Dict[str, Any]:
        conn = self._connect()
        existing = conn.execute(
            "SELECT 1 FROM ktc_post_likes WHERE user_id = ? AND post_id = ?",
            (user_id, post_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM ktc_post_likes WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO ktc_post_likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                (user_id, post_id, _utc_now()),
            )
            post = conn.execute(
                "SELECT user_id FROM ktc_posts WHERE id = ?",
                (post_id,),
            ).fetchone()
            if post and post["user_id"] != user_id:
                self._create_notification(
                    conn,
                    user_id=post["user_id"],
                    from_user_id=user_id,
                    notification_type="like",
                    post_id=post_id,
                )
            liked = True
        conn.commit()
        conn.close()
        return {"liked": liked}

    def toggle_save(self, user_id: str, post_id: str) -> Dict[str, Any]:
        conn = self._connect()
        existing = conn.execute(
            "SELECT 1 FROM ktc_post_saves WHERE user_id = ? AND post_id = ?",
            (user_id, post_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM ktc_post_saves WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            )
            saved = False
        else:
            conn.execute(
                "INSERT INTO ktc_post_saves (user_id, post_id, created_at) VALUES (?, ?, ?)",
                (user_id, post_id, _utc_now()),
            )
            saved = True
        conn.commit()
        conn.close()
        return {"saved": saved}

    def list_comments(self, post_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT c.*, u.username, u.profile_image_url
            FROM ktc_post_comments c
            JOIN ktc_users u ON u.id = c.user_id
            WHERE c.post_id = ?
            ORDER BY c.created_at DESC
            """,
            (post_id,),
        ).fetchall()
        comments = [
            {
                "id": row["id"],
                "content": row["content"],
                "created_at": row["created_at"],
                "author": {
                    "id": row["user_id"],
                    "username": row["username"],
                    "profile_image_url": row["profile_image_url"] or "",
                },
            }
            for row in rows
        ]
        conn.close()
        return comments

    def add_comment(self, user_id: str, post_id: str, content: str) -> Dict[str, Any]:
        conn = self._connect()
        comment_id = str(uuid.uuid4())
        created_at = _utc_now()
        conn.execute(
            """
            INSERT INTO ktc_post_comments (id, post_id, user_id, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (comment_id, post_id, user_id, content.strip(), created_at),
        )
        post = conn.execute(
            "SELECT user_id FROM ktc_posts WHERE id = ?",
            (post_id,),
        ).fetchone()
        if post and post["user_id"] != user_id:
            self._create_notification(
                conn,
                user_id=post["user_id"],
                from_user_id=user_id,
                notification_type="comment",
                post_id=post_id,
                comment_id=comment_id,
            )
        row = conn.execute(
            """
            SELECT c.*, u.username, u.profile_image_url
            FROM ktc_post_comments c
            JOIN ktc_users u ON u.id = c.user_id
            WHERE c.id = ?
            """,
            (comment_id,),
        ).fetchone()
        comment = {
            "id": row["id"],
            "content": row["content"],
            "created_at": row["created_at"],
            "author": {
                "id": row["user_id"],
                "username": row["username"],
                "profile_image_url": row["profile_image_url"] or "",
            },
        }
        conn.commit()
        conn.close()
        return comment

    def _create_notification(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        from_user_id: Optional[str],
        notification_type: str,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
    ) -> None:
        notification_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO ktc_notifications (
                id, user_id, from_user_id, type, post_id, comment_id, is_read, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                notification_id,
                user_id,
                from_user_id,
                notification_type,
                post_id,
                comment_id,
                _utc_now(),
            ),
        )

    def list_notifications(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT n.*, u.username AS from_username, u.profile_image_url AS from_profile_image
            FROM ktc_notifications n
            LEFT JOIN ktc_users u ON u.id = n.from_user_id
            WHERE n.user_id = ?
            ORDER BY n.created_at DESC
            LIMIT 50
            """,
            (user_id,),
        ).fetchall()
        notifications = [
            {
                "id": row["id"],
                "type": row["type"],
                "is_read": bool(row["is_read"]),
                "created_at": row["created_at"],
                "from_user_id": row["from_user_id"],
                "from_username": row["from_username"] or "someone",
                "from_profile_image": row["from_profile_image"] or "",
            }
            for row in rows
        ]
        conn.close()
        return notifications

    def unread_notification_count(self, user_id: str) -> int:
        conn = self._connect()
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM ktc_notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()["count"]
        conn.close()
        return count

    def mark_notifications_read(self, user_id: str) -> None:
        conn = self._connect()
        conn.execute(
            "UPDATE ktc_notifications SET is_read = 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        conn.close()

    def list_auto_rules(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT * FROM ktc_auto_rules
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
        rules = [
            {
                "cryptocurrency": row["cryptocurrency"],
                "percentage": float(row["percentage"]),
                "min_savings_threshold": float(row["min_savings_threshold"]),
                "is_enabled": bool(row["is_enabled"]),
            }
            for row in rows
        ]
        conn.close()
        return rules

    def save_auto_rule(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        cryptocurrency = (payload.get("cryptocurrency") or "bitcoin").strip().lower()
        percentage = float(payload.get("percentage") or 10)
        min_savings_threshold = float(payload.get("min_savings_threshold") or 5)
        is_enabled = 1 if payload.get("is_enabled", True) else 0
        conn.execute(
            """
            INSERT INTO ktc_auto_rules (
                user_id, cryptocurrency, percentage, min_savings_threshold, is_enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, cryptocurrency) DO UPDATE SET
                percentage = excluded.percentage,
                min_savings_threshold = excluded.min_savings_threshold,
                is_enabled = excluded.is_enabled,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                cryptocurrency,
                percentage,
                min_savings_threshold,
                is_enabled,
                _utc_now(),
            ),
        )
        conn.commit()
        conn.close()
        return {
            "cryptocurrency": cryptocurrency,
            "percentage": percentage,
            "min_savings_threshold": min_savings_threshold,
            "is_enabled": bool(is_enabled),
        }

    def delete_auto_rule(self, user_id: str, cryptocurrency: str) -> None:
        conn = self._connect()
        conn.execute(
            "DELETE FROM ktc_auto_rules WHERE user_id = ? AND cryptocurrency = ?",
            (user_id, cryptocurrency.lower()),
        )
        conn.commit()
        conn.close()

    def get_crypto_prices(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "bitcoin",
                "name": "Bitcoin",
                "symbol": "btc",
                "current_price": 67321.15,
                "price_change_24h": 2.48,
                "image": "",
            },
            {
                "id": "ethereum",
                "name": "Ethereum",
                "symbol": "eth",
                "current_price": 3314.42,
                "price_change_24h": 1.17,
                "image": "",
            },
            {
                "id": "solana",
                "name": "Solana",
                "symbol": "sol",
                "current_price": 151.66,
                "price_change_24h": 3.92,
                "image": "",
            },
            {
                "id": "dogecoin",
                "name": "Dogecoin",
                "symbol": "doge",
                "current_price": 0.18,
                "price_change_24h": -0.84,
                "image": "",
            },
        ]

    def _price_for(self, cryptocurrency: str) -> Dict[str, Any]:
        prices = {coin["id"]: coin for coin in self.get_crypto_prices()}
        return prices.get(cryptocurrency.lower(), prices["bitcoin"])

    def _create_investment_record(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        amount_usd: float,
        cryptocurrency: str,
        tx_type: str,
        rule_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        coin = self._price_for(cryptocurrency)
        price_usd = float(coin["current_price"])
        crypto_amount = round(amount_usd / price_usd, 8) if price_usd else 0.0
        tx_id = str(uuid.uuid4())
        created_at = _utc_now()
        conn.execute(
            """
            INSERT INTO ktc_crypto_transactions (
                id, user_id, type, cryptocurrency, symbol, amount_usd,
                crypto_amount, price_usd, rule_percentage, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_id,
                user_id,
                tx_type,
                coin["id"],
                coin["symbol"],
                amount_usd,
                crypto_amount,
                price_usd,
                rule_percentage,
                created_at,
            ),
        )
        conn.execute(
            "UPDATE ktc_users SET total_invested = total_invested + ? WHERE id = ?",
            (amount_usd, user_id),
        )
        return {
            "id": tx_id,
            "type": tx_type,
            "cryptocurrency": coin["id"],
            "symbol": coin["symbol"],
            "amount_usd": round(amount_usd, 2),
            "crypto_amount": crypto_amount,
            "price_usd": price_usd,
            "rule_percentage": rule_percentage,
            "created_at": created_at,
        }

    def create_manual_investment(
        self,
        user_id: str,
        amount_usd: float,
        cryptocurrency: str,
    ) -> Dict[str, Any]:
        conn = self._connect()
        tx = self._create_investment_record(
            conn,
            user_id=user_id,
            amount_usd=amount_usd,
            cryptocurrency=cryptocurrency,
            tx_type="manual_buy",
        )
        conn.commit()
        conn.close()
        return tx

    def list_transactions(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT * FROM ktc_crypto_transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        transactions = [
            {
                "id": row["id"],
                "type": row["type"],
                "cryptocurrency": row["cryptocurrency"],
                "symbol": row["symbol"],
                "amount_usd": float(row["amount_usd"]),
                "crypto_amount": float(row["crypto_amount"]),
                "price_usd": float(row["price_usd"]),
                "rule_percentage": float(row["rule_percentage"]) if row["rule_percentage"] is not None else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        conn.close()
        return transactions

    def get_portfolio(self, user_id: str) -> Dict[str, Any]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT cryptocurrency, symbol,
                   SUM(amount_usd) AS total_invested,
                   SUM(crypto_amount) AS total_amount,
                   AVG(price_usd) AS avg_buy_price
            FROM ktc_crypto_transactions
            WHERE user_id = ?
            GROUP BY cryptocurrency, symbol
            """,
            (user_id,),
        ).fetchall()
        holdings = []
        total_value = 0.0
        total_invested = 0.0
        for row in rows:
            coin = self._price_for(row["cryptocurrency"])
            current_value = float(row["total_amount"] or 0.0) * float(coin["current_price"])
            total_value += current_value
            total_invested += float(row["total_invested"] or 0.0)
            holdings.append(
                {
                    "cryptocurrency": row["cryptocurrency"],
                    "symbol": row["symbol"],
                    "amount": float(row["total_amount"] or 0.0),
                    "avg_buy_price": float(row["avg_buy_price"] or 0.0),
                    "current_value": round(current_value, 2),
                }
            )
        conn.close()
        return {
            "holdings": holdings,
            "total_value": round(total_value, 2),
            "total_invested": round(total_invested, 2),
        }

    def build_receipt_scan(self, filename: str = "receipt.jpg") -> Dict[str, Any]:
        items = [
            {"name": "Organic Strawberries", "price": 4.99},
            {"name": "Greek Yogurt", "price": 5.49},
            {"name": "Spinach", "price": 2.79},
            {"name": "Chicken Breast", "price": 12.99},
        ]
        total = round(sum(item["price"] for item in items), 2)
        store_name = "Whole Foods" if "whole" in filename.lower() else "Target"
        return {
            "success": True,
            "receipt_data": {
                "store_name": store_name,
                "total": total,
                "items": items,
                "scanned_at": _utc_now(),
            },
        }

    def build_price_comparison(self, product_name: str, base_price: float) -> Dict[str, Any]:
        matches = self._rank_offer_matches(product_name, require_express=False)
        comparisons = []
        if matches:
            for offer in matches[:4]:
                comparisons.append(
                    {
                        "retailer": offer["producer_name"],
                        "price": round(offer["offer_price"] + offer["shipping_fee"], 2),
                        "in_stock": True,
                        "product_name": offer["item_name"],
                        "source": offer["source"],
                        "express_shipping": offer["express_shipping"],
                        "savings_amount": offer["savings_amount"],
                    }
                )
        else:
            deltas = [
                ("Walmart", -0.18),
                ("Target", -0.07),
                ("Amazon", 0.03),
            ]
            for retailer, delta in deltas:
                price = round(max(0.5, base_price * (1 + delta)), 2)
                comparisons.append(
                    {
                        "retailer": retailer,
                        "price": price,
                        "in_stock": True,
                        "product_name": product_name,
                    }
                )
        comparisons.sort(key=lambda item: item["price"])
        return {"comparisons": comparisons}
