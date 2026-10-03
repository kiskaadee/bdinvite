from unittest.mock import ANY, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import Identity, get_auth_adapter


def test_remote_user_header_strictly_ignored(client: TestClient):
    """Negative gate: legacy Remote-User header without authenticated session must return 401."""
    res = client.get("/birthday/api/admin/rsvps", headers={"Remote-User": "kiskaadee"})
    assert res.status_code == 401


def test_admin_endpoints_require_authentication(client: TestClient):
    """Anonymous requests to admin endpoints must receive HTTP 401 Unauthorized."""
    endpoints = [
        ("GET", "/birthday/api/admin/rsvps"),
        ("GET", "/birthday/api/admin/export"),
        ("GET", "/birthday/api/admin/config"),
        ("PUT", "/birthday/api/admin/config"),
        ("PATCH", "/birthday/api/admin/config"),
        ("POST", "/birthday/api/admin/map-preview/generate"),
        ("DELETE", "/birthday/api/admin/rsvps/1"),
        ("PATCH", "/birthday/api/admin/rsvps/1"),
    ]
    for method, path in endpoints:
        res = client.request(method, path)
        assert res.status_code == 401, f"{method} {path} should require authentication"
        assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_admin_endpoints_require_remote_user(client: TestClient):
    """Backwards-compatible test: verify anonymous or legacy header calls are rejected with 401."""
    endpoints = [
        "/birthday/api/admin/rsvps",
        "/birthday/api/admin/export",
        "/birthday/api/admin/config",
    ]
    for path in endpoints:
        res = client.get(path)
        assert res.status_code == 401, f"GET {path} should require authentication"
        res_legacy = client.get(path, headers={"Remote-User": "kiskaadee"})
        assert res_legacy.status_code == 401, f"GET {path} with Remote-User must still be rejected"


def test_admin_endpoints_forbidden_for_non_admin_users(client: TestClient, guest_session_cookie: dict[str, str]):
    """Authenticated non-admin users must receive HTTP 403 Forbidden."""
    for k, v in guest_session_cookie.items():
        client.cookies.set(k, v)

    endpoints = [
        ("GET", "/birthday/api/admin/rsvps"),
        ("GET", "/birthday/api/admin/export"),
        ("GET", "/birthday/api/admin/config"),
        ("PUT", "/birthday/api/admin/config"),
        ("PATCH", "/birthday/api/admin/config"),
        ("POST", "/birthday/api/admin/map-preview/generate"),
        ("DELETE", "/birthday/api/admin/rsvps/1"),
        ("PATCH", "/birthday/api/admin/rsvps/1"),
    ]
    for method, path in endpoints:
        res = client.request(method, path)
        assert res.status_code == 403, f"{method} {path} should be forbidden for guest user"
        assert "bdinvite_admins" in res.json().get("detail", "")

    # Even if non-admin injects Remote-User header, session identity governs -> 403
    res_spoof = client.get("/birthday/api/admin/rsvps", headers={"Remote-User": "admin"})
    assert res_spoof.status_code == 403


def test_admin_list_and_search_rsvps(admin_client: TestClient):
    """Authenticated admin user can list and search RSVPs."""
    # Initially 0
    res = admin_client.get("/birthday/api/admin/rsvps")
    assert res.status_code == 200
    assert res.json()["count"] == 0

    # Add 3 invitees
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Carlos Gomez", "phone": "300 111 2233", "email": "carlos@test.com"},
    )
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Maria Perez", "phone": "315 222 3344", "email": "maria@test.com"},
    )
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Juan Gomez", "phone": "320 333 4455", "email": None},
    )

    # List all
    res = admin_client.get("/birthday/api/admin/rsvps")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 3

    # Search by name
    res_search = admin_client.get("/birthday/api/admin/rsvps?search=Gomez")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["count"] == 2

    # Search by phone substring
    res_phone = admin_client.get("/birthday/api/admin/rsvps?search=315222")
    assert res_phone.status_code == 200
    assert res_phone.json()["count"] == 1
    assert res_phone.json()["rsvps"][0]["name"] == "Maria Perez"


def test_admin_export_csv(admin_client: TestClient):
    """Authenticated admin user can export RSVPs as CSV."""
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Sofia Vergara", "phone": "301 999 8877", "email": "sofia@hollywood.com"},
    )

    res = admin_client.get("/birthday/api/admin/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="rsvps.csv"' in res.headers["content-disposition"]

    content = res.text
    lines = content.strip().split("\r\n") if "\r\n" in content else content.strip().split("\n")
    assert lines[0] == "name,phone,email,created_at"
    assert "Sofia Vergara,3019998877,sofia@hollywood.com" in lines[1]


def test_admin_delete_rsvp(client: TestClient, admin_client: TestClient):
    """Admin can delete RSVPs; anonymous requests are rejected."""
    # Unauthorized without session
    res_unauth = client.delete("/birthday/api/admin/rsvps/1")
    assert res_unauth.status_code == 401

    # 404 for non-existent RSVP
    res_404 = admin_client.delete("/birthday/api/admin/rsvps/9999")
    assert res_404.status_code == 404

    # Create an RSVP
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Lucas Silva", "phone": "300 444 5566", "email": "lucas@test.com"},
    )
    list_res = admin_client.get("/birthday/api/admin/rsvps")
    assert list_res.status_code == 200
    rsvps = list_res.json()["rsvps"]
    assert len(rsvps) == 1
    rsvp_id = rsvps[0]["id"]

    # Delete successfully
    del_res = admin_client.delete(f"/birthday/api/admin/rsvps/{rsvp_id}")
    assert del_res.status_code == 204

    # Confirm deletion
    list_after = admin_client.get("/birthday/api/admin/rsvps")
    assert list_after.json()["count"] == 0


def test_admin_update_rsvp(client: TestClient, admin_client: TestClient):
    """Admin can update RSVPs; anonymous requests are rejected."""
    # Unauthorized without session
    res_unauth = client.patch("/birthday/api/admin/rsvps/1", json={"name": "New Name"})
    assert res_unauth.status_code == 401

    # 404 for non-existent RSVP
    res_404 = admin_client.patch(
        "/birthday/api/admin/rsvps/9999",
        json={"name": "New Name"},
    )
    assert res_404.status_code == 404

    # Create two RSVPs
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Person One", "phone": "300 111 2222", "email": "one@test.com"},
    )
    admin_client.post(
        "/birthday/api/rsvp",
        json={"name": "Person Two", "phone": "300 333 4444", "email": "two@test.com"},
    )

    list_res = admin_client.get("/birthday/api/admin/rsvps")
    rsvps = list_res.json()["rsvps"]
    id_one = next(r["id"] for r in rsvps if r["name"] == "Person One")
    id_two = next(r["id"] for r in rsvps if r["name"] == "Person Two")

    # Update Person One with valid new name and phone
    patch_res = admin_client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"name": "Person One Updated", "phone": "+57 300 999 8888", "email": "newone@test.com"},
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["name"] == "Person One Updated"
    assert updated_data["phone"] == "3009998888"
    assert updated_data["email"] == "newone@test.com"

    # Attempt to update Person One's phone to Person Two's phone -> 409
    dup_res = admin_client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"phone": "300 333 4444"},
    )
    assert dup_res.status_code == 409

    # Validation error for invalid phone
    val_res = admin_client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"phone": "12345"},
    )
    assert val_res.status_code in (400, 422)


def test_admin_config_endpoints(admin_client: TestClient, client: TestClient):
    """Admin can retrieve and update config via PUT and PATCH; unauthenticated calls rejected."""
    # Anonymous -> 401
    assert client.get("/birthday/api/admin/config").status_code == 401
    assert client.patch("/birthday/api/admin/config", json={}).status_code == 401
    assert client.put("/birthday/api/admin/config", json={}).status_code == 401

    # Admin GET config -> 200
    res = admin_client.get("/birthday/api/admin/config")
    assert res.status_code == 200
    current_config = res.json()
    assert current_config["honoree_name"] == "Isabelle Snow"

    # Admin PATCH config -> 200
    update_payload = {**current_config}
    update_payload["honoree_name"] = "Isabelle Updated via PATCH"
    patch_res = admin_client.patch("/birthday/api/admin/config", json=update_payload)
    assert patch_res.status_code == 200
    assert patch_res.json()["honoree_name"] == "Isabelle Updated via PATCH"

    # Admin PUT config -> 200
    update_payload["honoree_name"] = "Isabelle Updated via PUT"
    put_res = admin_client.put("/birthday/api/admin/config", json=update_payload)
    assert put_res.status_code == 200
    assert put_res.json()["honoree_name"] == "Isabelle Updated via PUT"


@patch("app.routes.admin.resolve_google_maps_coordinates")
@patch("app.routes.admin.generate_map_preview_image")
def test_admin_map_preview_generate_endpoint(
    mock_generate, mock_resolve, client: TestClient, admin_client: TestClient, tmp_path
):
    """Map preview generation requires admin; verifies successful generation."""
    mock_resolve.return_value = (34.1432, -118.2551, "https://resolved.url")
    mock_generate.return_value = tmp_path / "map_preview.png"

    # Anonymous -> 401
    res_unauth = client.post(
        "/birthday/api/admin/map-preview/generate",
        json={"map_url": "https://maps.google.com/?q=34.1,-118.2"},
    )
    assert res_unauth.status_code == 401

    # Admin -> 200
    res_admin = admin_client.post(
        "/birthday/api/admin/map-preview/generate",
        json={"map_url": "https://maps.google.com/?q=34.1,-118.2"},
    )
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "/birthday/api/map-preview.png" in data["map_preview_url"]
    assert data["lat"] == 34.1432
    assert data["lng"] == -118.2551
