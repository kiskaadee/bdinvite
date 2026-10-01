import pytest
from app.services.rsvp import normalize_phone


def test_normalize_phone_valid_cases():
    cases = [
        ("+57 300 123 4567", "3001234567"),
        ("300-123-4567", "3001234567"),
        ("3001234567", "3001234567"),
        ("(300) 123 4567", "3001234567"),
        ("57300123 4567", "3001234567"),
        ("+573159998877", "3159998877"),
        ("320 000 0000", "3200000000"),
    ]
    for raw, expected in cases:
        assert normalize_phone(raw) == expected


def test_normalize_phone_invalid_cases():
    invalid_cases = [
        "123456",            # Too short
        "1234567890",        # Doesn't start with 3
        "+1 555 123 4567",   # US format
        "30012345678",       # Too long
        "",                  # Empty
        "abcdefghij",        # Non-digits
    ]
    for raw in invalid_cases:
        with pytest.raises(ValueError, match="Formato de teléfono inválido"):
            normalize_phone(raw)


def test_submit_rsvp_success(client):
    payload = {
        "name": "Andrés García",
        "phone": "+57 300 123 4567",
        "email": "andres@example.com",
    }
    response = client.post("/birthday/api/rsvp", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["result"] == "SUCCESS"
    assert data["name"] == "Andrés García"


def test_submit_rsvp_duplicate(client):
    payload = {
        "name": "Andrés García",
        "phone": "300 123 4567",
        "email": "andres@example.com",
    }
    # First submission
    res1 = client.post("/birthday/api/rsvp", json=payload)
    assert res1.status_code == 201

    # Second submission with same phone in different format
    payload2 = {
        "name": "Andrés Felipe García",
        "phone": "+57 300-123-4567",
        "email": "other@example.com",
    }
    res2 = client.post("/birthday/api/rsvp", json=payload2)
    assert res2.status_code == 409
    data = res2.json()
    assert data["result"] == "DUPLICATE"


def test_submit_rsvp_validation_error_phone(client):
    payload = {
        "name": "Camila",
        "phone": "999 123 4567",  # doesn't start with 3
    }
    response = client.post("/birthday/api/rsvp", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["result"] == "VALIDATION_ERROR"
    assert "phone" in data["errors"]


def test_submit_rsvp_validation_error_name(client):
    payload = {
        "name": "   ",
        "phone": "300 123 4567",
    }
    response = client.post("/birthday/api/rsvp", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["result"] == "VALIDATION_ERROR"
    assert "name" in data["errors"]


def test_submit_rsvp_validation_error_email(client):
    payload = {
        "name": "Camila",
        "phone": "300 123 4567",
        "email": "invalid-email-string",
    }
    response = client.post("/birthday/api/rsvp", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["result"] == "VALIDATION_ERROR"
    assert "email" in data["errors"]
