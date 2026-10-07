from fastapi.testclient import TestClient

from tests.conftest import login_client


def test_admin_endpoints_require_authentication(client: TestClient):
    """Anonymous requests to all admin endpoints must receive HTTP 401 Unauthorized."""
    endpoints = [
        ("GET", "/birthday/api/admin/rsvps"),
        ("DELETE", "/birthday/api/admin/rsvps/1"),
        ("PATCH", "/birthday/api/admin/rsvps/1"),
        ("GET", "/birthday/api/admin/export"),
        ("GET", "/birthday/api/admin/config"),
        ("PUT", "/birthday/api/admin/config"),
        ("PATCH", "/birthday/api/admin/config"),
        ("POST", "/birthday/api/admin/map-preview/generate"),
    ]
    for method, path in endpoints:
        res = client.request(method, path)
        assert res.status_code == 401, f"{method} {path} should require authentication"
        assert res.json() == {"detail": "Not authenticated"}


def test_remote_user_header_strictly_ignored(client: TestClient):
    """Legacy Remote-User header without valid authenticated session must be strictly rejected with HTTP 401."""
    res = client.get("/birthday/api/admin/rsvps", headers={"Remote-User": "kiskaadee"})
    assert res.status_code == 401
    assert res.json() == {"detail": "Not authenticated"}

    # Also verify across other admin routes
    assert (
        client.get(
            "/birthday/api/admin/export", headers={"Remote-User": "kiskaadee"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/birthday/api/admin/config", headers={"Remote-User": "kiskaadee"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/birthday/api/admin/map-preview/generate",
            headers={"Remote-User": "kiskaadee"},
            json={"map_url": "https://maps.google.com/?q=34.1,-118.2"},
        ).status_code
        == 401
    )


def test_admin_endpoints_authenticated_non_admin_forbidden(guest_client: TestClient):
    """Authenticated non-admin users (e.g. guest@example.com with groups: ['guests']) must receive HTTP 403 Forbidden."""
    endpoints = [
        ("GET", "/birthday/api/admin/rsvps"),
        ("DELETE", "/birthday/api/admin/rsvps/1"),
        ("PATCH", "/birthday/api/admin/rsvps/1"),
        ("GET", "/birthday/api/admin/export"),
        ("GET", "/birthday/api/admin/config"),
        ("PUT", "/birthday/api/admin/config"),
        ("PATCH", "/birthday/api/admin/config"),
        ("POST", "/birthday/api/admin/map-preview/generate"),
    ]
    for method, path in endpoints:
        res = guest_client.request(method, path)
        assert res.status_code == 403, (
            f"{method} {path} should reject non-admin with 403"
        )
        assert "Forbidden" in res.json()["detail"]


def test_remote_user_header_with_non_admin_session_cannot_elevate_privileges(
    guest_client: TestClient,
):
    """An attacker passing Remote-User: admin with a non-admin session cookie must still receive HTTP 403."""
    res = guest_client.get(
        "/birthday/api/admin/rsvps",
        headers={"Remote-User": "admin@example.com", "X-Remote-User": "admin"},
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_admin_endpoints_authenticated_admin_allowed(admin_client: TestClient):
    """Authenticated admin user (admin@example.com with groups: ['bdinvite_admins']) succeeds."""
    res_rsvps = admin_client.get("/birthday/api/admin/rsvps")
    assert res_rsvps.status_code == 200

    res_export = admin_client.get("/birthday/api/admin/export")
    assert res_export.status_code == 200

    res_config = admin_client.get("/birthday/api/admin/config")
    assert res_config.status_code == 200


def test_admin_list_and_search_rsvps(admin_client: TestClient):
    # Initially 0
    res = admin_client.get("/birthday/api/admin/rsvps")
    assert res.status_code == 200
    assert res.json()["count"] == 0

    # Add 3 invitees
    admin_client.post(
        "/birthday/api/rsvp",
        json={
            "name": "Carlos Gomez",
            "phone": "300 111 2233",
            "email": "carlos@test.com",
        },
    )
    admin_client.post(
        "/birthday/api/rsvp",
        json={
            "name": "Maria Perez",
            "phone": "315 222 3344",
            "email": "maria@test.com",
        },
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
    admin_client.post(
        "/birthday/api/rsvp",
        json={
            "name": "Sofia Vergara",
            "phone": "301 999 8877",
            "email": "sofia@hollywood.com",
        },
    )

    res = admin_client.get("/birthday/api/admin/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="rsvps.csv"' in res.headers["content-disposition"]

    content = res.text
    lines = (
        content.strip().split("\r\n")
        if "\r\n" in content
        else content.strip().split("\n")
    )
    assert lines[0] == "name,phone,email,created_at"
    assert "Sofia Vergara,3019998877,sofia@hollywood.com" in lines[1]


def test_admin_delete_rsvp(client: TestClient):
    # Unauthorized without session
    res_unauth = client.delete("/birthday/api/admin/rsvps/1")
    assert res_unauth.status_code == 401

    # Login as admin
    login_client(client)

    # 404 for non-existent RSVP
    res_404 = client.delete("/birthday/api/admin/rsvps/9999")
    assert res_404.status_code == 404

    # Create an RSVP
    client.post(
        "/birthday/api/rsvp",
        json={
            "name": "Lucas Silva",
            "phone": "300 444 5566",
            "email": "lucas@test.com",
        },
    )
    list_res = client.get("/birthday/api/admin/rsvps")
    assert list_res.status_code == 200
    rsvps = list_res.json()["rsvps"]
    assert len(rsvps) == 1
    rsvp_id = rsvps[0]["id"]

    # Delete successfully
    del_res = client.delete(f"/birthday/api/admin/rsvps/{rsvp_id}")
    assert del_res.status_code == 204

    # Confirm deletion
    list_after = client.get("/birthday/api/admin/rsvps")
    assert list_after.json()["count"] == 0


def test_admin_update_rsvp(client: TestClient):
    # Unauthorized without session
    res_unauth = client.patch("/birthday/api/admin/rsvps/1", json={"name": "New Name"})
    assert res_unauth.status_code == 401

    # Login as admin
    login_client(client)

    # 404 for non-existent RSVP
    res_404 = client.patch(
        "/birthday/api/admin/rsvps/9999",
        json={"name": "New Name"},
    )
    assert res_404.status_code == 404

    # Create two RSVPs
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Person One", "phone": "300 111 2222", "email": "one@test.com"},
    )
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Person Two", "phone": "300 333 4444", "email": "two@test.com"},
    )

    list_res = client.get("/birthday/api/admin/rsvps")
    rsvps = list_res.json()["rsvps"]
    id_one = next(r["id"] for r in rsvps if r["name"] == "Person One")
    id_two = next(r["id"] for r in rsvps if r["name"] == "Person Two")
    assert id_two is not None

    # Update Person One with valid new name and phone
    patch_res = client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={
            "name": "Person One Updated",
            "phone": "+57 300 999 8888",
            "email": "newone@test.com",
        },
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["name"] == "Person One Updated"
    assert updated_data["phone"] == "3009998888"
    assert updated_data["email"] == "newone@test.com"

    # Attempt to update Person One's phone to Person Two's phone -> 409
    dup_res = client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"phone": "300 333 4444"},
    )
    assert dup_res.status_code == 409

    # Validation error for invalid phone
    val_res = client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"phone": "12345"},
    )
    assert val_res.status_code in (400, 422)


def test_admin_config_endpoints_put_and_patch(admin_client: TestClient):
    """Both PUT and PATCH /birthday/api/admin/config succeed for authorized admins."""
    current = admin_client.get("/birthday/api/admin/config").json()
    assert current["honoree_name"] == "Isabelle Snow"

    # Test PUT
    payload_put = {**current, "honoree_name": "Isabelle PUT"}
    res_put = admin_client.put("/birthday/api/admin/config", json=payload_put)
    assert res_put.status_code == 200
    assert res_put.json()["honoree_name"] == "Isabelle PUT"

    # Test PATCH
    payload_patch = {**current, "honoree_name": "Isabelle PATCH"}
    res_patch = admin_client.patch("/birthday/api/admin/config", json=payload_patch)
    assert res_patch.status_code == 200
    assert res_patch.json()["honoree_name"] == "Isabelle PATCH"
