from unittest.mock import ANY, patch

import pytest
from app.config import settings
from app.services.map_preview import (
    deg2num,
    extract_coordinates_from_text,
    is_google_maps_host,
    validate_google_maps_url_format,
)

from tests.conftest import login_client


def test_is_google_maps_host():
    assert is_google_maps_host("maps.app.goo.gl")
    assert is_google_maps_host("share.google")
    assert is_google_maps_host("goo.gl")
    assert is_google_maps_host("maps.google.com")
    assert is_google_maps_host("google.com")
    assert is_google_maps_host("www.google.com")
    assert is_google_maps_host("google.es")
    assert is_google_maps_host("maps.google.co.uk")

    assert not is_google_maps_host("example.com")
    assert not is_google_maps_host("bing.com")
    assert not is_google_maps_host("evilgoogle.com")


def test_validate_google_maps_url_format():
    validate_google_maps_url_format("https://maps.app.goo.gl/354784424357732")
    validate_google_maps_url_format("https://www.google.com/maps/place/Fresco/@34.1,-118.2,17z")
    validate_google_maps_url_format("https://maps.google.com/?q=34.1,-118.2")

    with pytest.raises(ValueError, match="no puede estar vacía"):
        validate_google_maps_url_format("")

    with pytest.raises(ValueError, match="comenzar con http"):
        validate_google_maps_url_format("ftp://maps.google.com")

    with pytest.raises(ValueError, match="enlace de Google Maps válido"):
        validate_google_maps_url_format("https://apple.com/maps")


def test_extract_coordinates_from_text():
    # 1. @lat,lng
    coords = extract_coordinates_from_text("https://google.com/maps/place/Venue/@34.143245,-118.255132,17z")
    assert coords == (34.143245, -118.255132)

    # 2. !3dlat!4dlng
    coords = extract_coordinates_from_text("https://google.com/maps/data=!4m6!3m5!1s0x0!8m2!3d4.6534!4d-74.0564")
    assert coords == (4.6534, -74.0564)

    # 3. Query params: q=lat,lng
    coords = extract_coordinates_from_text("https://maps.google.com/?q=34.1432,-118.2551")
    assert coords == (34.1432, -118.2551)

    # 4. Query params: ll=lat,lng
    coords = extract_coordinates_from_text("https://maps.google.com/maps?ll=34.1432,-118.2551&z=16")
    assert coords == (34.1432, -118.2551)

    # 5. Non-coordinate text
    assert extract_coordinates_from_text("https://maps.google.com/?q=Eiffel+Tower") is None


def test_deg2num():
    xtile, ytile = deg2num(34.1432, -118.2551, 16)
    assert int(xtile) == 11240
    assert int(ytile) == 26148


@patch("app.routes.admin.resolve_google_maps_coordinates")
@patch("app.routes.admin.generate_map_preview_image")
def test_admin_generate_map_preview_endpoint(mock_generate, mock_resolve, client, tmp_path):
    mock_resolve.return_value = (34.1432, -118.2551, "https://resolved.url")
    mock_generate.return_value = tmp_path / "map_preview.png"

    # Test without auth -> 401
    resp = client.post("/birthday/api/admin/map-preview/generate", json={"map_url": "https://maps.google.com/?q=34.1,-118.2"})
    assert resp.status_code == 401

    # Test with auth -> 200
    login_client(client)
    resp = client.post(
        "/birthday/api/admin/map-preview/generate",
        json={"map_url": "https://maps.google.com/?q=34.1,-118.2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "/birthday/api/map-preview.png" in data["map_preview_url"]
    assert data["lat"] == 34.1432
    assert data["lng"] == -118.2551
    mock_resolve.assert_called_once_with("https://maps.google.com/?q=34.1,-118.2", fallback_query=ANY)
    mock_generate.assert_called_once_with(34.1432, -118.2551)


@patch("app.routes.admin.resolve_google_maps_coordinates")
@patch("app.routes.admin.generate_map_preview_image")
def test_config_update_triggers_generator_only_when_map_url_changes(mock_generate, mock_resolve, admin_client, tmp_path):
    mock_resolve.return_value = (34.1432, -118.2551, "https://resolved.url")
    mock_generate.return_value = tmp_path / "map_preview.png"

    # Get current config
    current = admin_client.get("/birthday/api/admin/config").json()
    orig_map_url = current["map_url"]
    assert orig_map_url == "https://maps.google.com/?q=Fresco+Ristorante+Glendale+CA"

    # 1. Update config WITHOUT changing map_url -> generator NOT called
    update_payload = {**current}
    update_payload["honoree_name"] = "Updated Honoree"
    resp = admin_client.put("/birthday/api/admin/config", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["honoree_name"] == "Updated Honoree"
    mock_resolve.assert_not_called()
    mock_generate.assert_not_called()

    # 2. Update config WITH new map_url -> generator CALLED
    update_payload["map_url"] = "https://maps.google.com/?q=34.1432,-118.2551"
    resp = admin_client.put("/birthday/api/admin/config", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["map_url"] == "https://maps.google.com/?q=34.1432,-118.2551"
    assert resp.json()["map_preview_url"] == "/birthday/api/map-preview.png"
    mock_resolve.assert_called_once_with("https://maps.google.com/?q=34.1432,-118.2551", fallback_query=ANY)
    mock_generate.assert_called_once_with(34.1432, -118.2551)


def test_config_update_rejects_invalid_map_url(admin_client):
    current = admin_client.get("/birthday/api/admin/config").json()
    bad_payload = {**current, "map_url": "https://invalid-non-google-url.com/something"}

    resp = admin_client.put("/birthday/api/admin/config", json=bad_payload)
    assert resp.status_code == 422


def test_get_map_preview_serving(client, tmp_path, monkeypatch):
    # Case 1: file exists
    test_img = tmp_path / "map_preview.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    resp = client.get("/birthday/api/map-preview.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == b"\x89PNG\r\n\x1a\nfakeimagebytes"

    # Case 2: file does not exist -> redirects to fallback
    test_img.unlink()
    resp_fallback = client.get("/birthday/api/map-preview.png", follow_redirects=False)
    assert resp_fallback.status_code == 307
    assert "tile.openstreetmap.org" in resp_fallback.headers["location"]
