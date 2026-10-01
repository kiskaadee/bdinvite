def test_admin_endpoints_require_remote_user(client):
    endpoints = [
        "/birthday/api/admin/rsvps",
        "/birthday/api/admin/export",
        "/birthday/api/admin/config",
    ]
    for path in endpoints:
        res = client.get(path)
        assert res.status_code == 401, f"GET {path} should require Remote-User header"
        assert res.json() == {"detail": "Not authenticated"}


def test_admin_list_and_search_rsvps(client):
    headers = {"Remote-User": "kiskaadee"}

    # Initially 0
    res = client.get("/birthday/api/admin/rsvps", headers=headers)
    assert res.status_code == 200
    assert res.json()["count"] == 0

    # Add 3 invitees
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Carlos Gomez", "phone": "300 111 2233", "email": "carlos@test.com"},
    )
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Maria Perez", "phone": "315 222 3344", "email": "maria@test.com"},
    )
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Juan Gomez", "phone": "320 333 4455", "email": None},
    )

    # List all
    res = client.get("/birthday/api/admin/rsvps", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 3

    # Search by name
    res_search = client.get("/birthday/api/admin/rsvps?search=Gomez", headers=headers)
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["count"] == 2

    # Search by phone substring
    res_phone = client.get("/birthday/api/admin/rsvps?search=315222", headers=headers)
    assert res_phone.status_code == 200
    assert res_phone.json()["count"] == 1
    assert res_phone.json()["rsvps"][0]["name"] == "Maria Perez"


def test_admin_export_csv(client):
    headers = {"Remote-User": "kiskaadee"}

    client.post(
        "/birthday/api/rsvp",
        json={"name": "Sofia Vergara", "phone": "301 999 8877", "email": "sofia@hollywood.com"},
    )

    res = client.get("/birthday/api/admin/export", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="rsvps.csv"' in res.headers["content-disposition"]

    content = res.text
    lines = content.strip().split("\r\n") if "\r\n" in content else content.strip().split("\n")
    assert lines[0] == "name,phone,email,created_at"
    assert "Sofia Vergara,3019998877,sofia@hollywood.com" in lines[1]


def test_admin_delete_rsvp(client):
    headers = {"Remote-User": "kiskaadee"}

    # Unauthorized without header
    res_unauth = client.delete("/birthday/api/admin/rsvps/1")
    assert res_unauth.status_code == 401

    # 404 for non-existent RSVP
    res_404 = client.delete("/birthday/api/admin/rsvps/9999", headers=headers)
    assert res_404.status_code == 404

    # Create an RSVP
    client.post(
        "/birthday/api/rsvp",
        json={"name": "Lucas Silva", "phone": "300 444 5566", "email": "lucas@test.com"},
    )
    list_res = client.get("/birthday/api/admin/rsvps", headers=headers)
    assert list_res.status_code == 200
    rsvps = list_res.json()["rsvps"]
    assert len(rsvps) == 1
    rsvp_id = rsvps[0]["id"]

    # Delete successfully
    del_res = client.delete(f"/birthday/api/admin/rsvps/{rsvp_id}", headers=headers)
    assert del_res.status_code == 204

    # Confirm deletion
    list_after = client.get("/birthday/api/admin/rsvps", headers=headers)
    assert list_after.json()["count"] == 0


def test_admin_update_rsvp(client):
    headers = {"Remote-User": "kiskaadee"}

    # Unauthorized without header
    res_unauth = client.patch("/birthday/api/admin/rsvps/1", json={"name": "New Name"})
    assert res_unauth.status_code == 401

    # 404 for non-existent RSVP
    res_404 = client.patch(
        "/birthday/api/admin/rsvps/9999",
        json={"name": "New Name"},
        headers=headers,
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

    list_res = client.get("/birthday/api/admin/rsvps", headers=headers)
    rsvps = list_res.json()["rsvps"]
    id_one = next(r["id"] for r in rsvps if r["name"] == "Person One")
    id_two = next(r["id"] for r in rsvps if r["name"] == "Person Two")

    # Update Person One with valid new name and phone
    patch_res = client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"name": "Person One Updated", "phone": "+57 300 999 8888", "email": "newone@test.com"},
        headers=headers,
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
        headers=headers,
    )
    assert dup_res.status_code == 409

    # Validation error for invalid phone
    val_res = client.patch(
        f"/birthday/api/admin/rsvps/{id_one}",
        json={"phone": "12345"},
        headers=headers,
    )
    assert val_res.status_code in (400, 422)

