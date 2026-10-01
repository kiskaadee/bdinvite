def test_get_config_public(client):
    response = client.get("/birthday/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Birthday Party"
    assert data["honoree_name"] == "Isabelle Snow"
    assert data["event_date"] == "2026-10-28"
    assert data["event_time"] == "19:00"
    assert data["event_timezone"] == "America/Bogota"
    assert data["countdown_label"] == "NOS VEMOS EN"


def test_get_config_admin(client):
    res_unauth = client.get("/birthday/api/admin/config")
    assert res_unauth.status_code == 401

    res_auth = client.get(
        "/birthday/api/admin/config",
        headers={"Remote-User": "admin_user"},
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["honoree_name"] == "Isabelle Snow"


def test_update_config_requires_admin(client):
    update_payload = {
        "title": "Fiesta de Cumpleaños",
        "invitation_text": "Estás invitado a la fiesta de",
        "honoree_name": "Isabelle",
        "event_date": "2026-11-15",
        "event_time": "20:00",
        "event_timezone": "America/Bogota",
        "address_name": "Restaurante Central",
        "address_lines": "Cra 7 # 12-34\nBogotá",
        "map_preview_url": "https://example.com/map.png",
        "map_url": "https://maps.google.com/?q=Bogota",
        "rsvp_heading": "¿Nos vemos?",
        "rsvp_cta": "CONFIRMAR",
        "submit_label": "AHÍ ESTARÉ",
        "msg_success": "¡Perfecto!",
        "msg_success_greeting": "Gracias, {name}.",
        "msg_duplicate": "Ya estás registrado.",
        "msg_error": "Error.",
        "msg_config_error": "Error al cargar.",
        "countdown_label": "FALTAN",
        "countdown_in_progress": "EN VIVO",
        "countdown_finished": "TERMINADO",
    }
    # Without Remote-User header -> 401
    res = client.put("/birthday/api/admin/config", json=update_payload)
    assert res.status_code == 401

    # With Remote-User header -> 200
    res_auth = client.put(
        "/birthday/api/admin/config",
        json=update_payload,
        headers={"Remote-User": "admin_user"},
    )
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert data["title"] == "Fiesta de Cumpleaños"
    assert data["honoree_name"] == "Isabelle"
    assert data["event_date"] == "2026-11-15"

    # Public endpoint reflects updated config immediately
    res_pub = client.get("/birthday/api/config")
    assert res_pub.status_code == 200
    assert res_pub.json()["title"] == "Fiesta de Cumpleaños"


def test_update_config_invalid_timezone(client):
    invalid_payload = {
        "title": "Party",
        "invitation_text": "Invited",
        "honoree_name": "Name",
        "event_date": "2026-11-15",
        "event_time": "20:00",
        "event_timezone": "NonExistent/Invalid_Timezone",
        "address_name": "Place",
        "address_lines": "Line 1",
        "map_preview_url": "https://example.com/map.png",
        "map_url": "https://maps.google.com",
        "rsvp_heading": "¿Nos vemos?",
        "rsvp_cta": "CONFIRMA",
        "submit_label": "ENVIAR",
        "msg_success": "OK",
        "msg_success_greeting": "Hola {name}",
        "msg_duplicate": "Dup",
        "msg_error": "Err",
        "msg_config_error": "CfgErr",
        "countdown_label": "FALTAN",
        "countdown_in_progress": "CURSO",
        "countdown_finished": "FIN",
    }
    res = client.put(
        "/birthday/api/admin/config",
        json=invalid_payload,
        headers={"Remote-User": "admin_user"},
    )
    assert res.status_code == 422


def test_spa_catch_all(client):
    res = client.get("/birthday")
    assert res.status_code == 200

    res_subpath = client.get("/birthday/admin")
    assert res_subpath.status_code == 200

    res_font = client.get("/birthday/fonts/display.woff2")
    assert res_font.status_code == 200
