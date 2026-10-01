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
