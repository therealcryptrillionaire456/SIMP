from __future__ import annotations

from pathlib import Path

from simp.organs.ktc.api import app as app_module


def _configure_temp_app(tmp_path: Path):
    db_path = tmp_path / "ktc_frontend_contract.db"
    app_module.CONFIG["database_path"] = str(db_path)
    app_module._social_store_cache.pop(str(db_path), None)
    client = app_module.app.test_client()
    return client


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_and_auth_me(tmp_path):
    client = _configure_temp_app(tmp_path)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "casey",
            "email": "casey@example.com",
            "password": "secret123",
            "full_name": "Casey Smith",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["username"] == "casey"
    assert body["token"]

    me = client.get("/api/auth/me", headers=_auth_headers(body["token"]))
    assert me.status_code == 200
    me_body = me.get_json()
    assert me_body["email"] == "casey@example.com"
    assert me_body["full_name"] == "Casey Smith"


def test_post_creation_feed_and_auto_invest_rules(tmp_path):
    client = _configure_temp_app(tmp_path)
    register = client.post(
        "/api/auth/register",
        json={
            "username": "jules",
            "email": "jules@example.com",
            "password": "secret123",
            "full_name": "Jules Parker",
        },
    )
    token = register.get_json()["token"]
    headers = _auth_headers(token)

    rule_response = client.post(
        "/api/crypto/auto-rules",
        headers=headers,
        json={
            "cryptocurrency": "solana",
            "percentage": 25,
            "min_savings_threshold": 5,
            "is_enabled": True,
        },
    )
    assert rule_response.status_code == 200

    create_post = client.post(
        "/api/posts",
        headers=headers,
        json={
            "title": "Bulk buy win",
            "description": "Locked in a solid grocery price cut.",
            "product_name": "Protein Bars",
            "original_price": 24.0,
            "your_price": 16.0,
            "retailer": "Target",
            "image_url": "https://example.com/bars.jpg",
            "tags": ["grocery", "deal"],
        },
    )
    assert create_post.status_code == 201
    post_body = create_post.get_json()
    assert post_body["savings_amount"] == 8.0
    assert len(post_body["auto_invested"]) == 1
    assert post_body["auto_invested"][0]["amount_usd"] == 2.0

    feed = client.get("/api/posts", headers=headers)
    assert feed.status_code == 200
    feed_body = feed.get_json()
    assert any(post["id"] == post_body["id"] for post in feed_body)

    portfolio = client.get("/api/crypto/portfolio", headers=headers)
    assert portfolio.status_code == 200
    portfolio_body = portfolio.get_json()
    assert portfolio_body["total_invested"] == 2.0
