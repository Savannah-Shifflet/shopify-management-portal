"""Tests for product CRUD endpoints."""
import pytest


def test_list_products_empty(client, auth_headers):
    resp = client.get("/api/v1/products/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_create_product(client, auth_headers):
    resp = client.post("/api/v1/products/", json={
        "title": "Test Widget",
        "base_price": "29.99",
        "product_type": "Widget",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Widget"
    assert data["status"] == "draft"
    assert data["sync_status"] == "never_synced"
    assert len(data["variants"]) == 1  # default variant created
    return data["id"]


def test_get_product(client, auth_headers):
    # Create first
    create_resp = client.post("/api/v1/products/", json={"title": "Get Me"}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Me"


def test_get_product_not_found(client, auth_headers):
    resp = client.get("/api/v1/products/00000000-0000-0000-0000-000000000999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_product(client, auth_headers):
    create_resp = client.post("/api/v1/products/", json={"title": "Original"}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    resp = client.patch(f"/api/v1/products/{product_id}", json={"title": "Updated"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


def test_delete_product(client, auth_headers):
    create_resp = client.post("/api/v1/products/", json={"title": "Delete Me"}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    resp = client.delete(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Should be archived, not truly deleted
    get_resp = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "archived"


def test_product_isolation_between_users(client, db):
    """Products from user A should not be visible to user B."""
    from app.routers.auth import _hash_password, _create_token
    from app.models.user import User
    import uuid

    user_b = User(id=uuid.uuid4(), email="b@example.com", hashed_password=_hash_password("pw"))
    db.add(user_b)
    db.commit()
    headers_b = {"Authorization": f"Bearer {_create_token(str(user_b.id))}"}

    # Create product as user A (auth_headers from test_user fixture won't work here)
    # So create user A manually
    user_a = User(id=uuid.uuid4(), email="a@example.com", hashed_password=_hash_password("pw"))
    db.add(user_a)
    db.commit()
    headers_a = {"Authorization": f"Bearer {_create_token(str(user_a.id))}"}

    client.post("/api/v1/products/", json={"title": "User A Product"}, headers=headers_a)

    # User B should see 0 products
    resp = client.get("/api/v1/products/", headers=headers_b)
    assert resp.json()["total"] == 0


def test_bulk_approve(client, auth_headers):
    create_resp = client.post("/api/v1/products/", json={"title": "Bulk Test"}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    resp = client.post("/api/v1/products/bulk", json={
        "action": "approve",
        "product_ids": [product_id],
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    get_resp = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "approved"


def test_list_products_requires_auth(client):
    resp = client.get("/api/v1/products/")
    assert resp.status_code == 401


def test_search_products(client, auth_headers):
    client.post("/api/v1/products/", json={"title": "Red Widget"}, headers=auth_headers)
    client.post("/api/v1/products/", json={"title": "Blue Gadget"}, headers=auth_headers)

    resp = client.get("/api/v1/products/?search=widget", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Red Widget"
