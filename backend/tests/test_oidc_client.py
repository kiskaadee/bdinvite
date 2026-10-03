"""Comprehensive unit and integration tests for Generic OIDC Client, PKCE & Cryptographic Verification."""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from app.auth import (
    AuthPort,
    Identity,
    InvalidNonceError,
    InvalidStateError,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    OIDCTransaction,
    TokenValidationError,
    generate_code_challenge,
    generate_code_verifier,
    generate_nonce,
    generate_state,
)

FIXTURE_ISSUER = "http://localhost:8088/default"
FIXTURE_CLIENT_ID = "bdinvite-client"
FIXTURE_CLIENT_SECRET = "bdinvite-secret"
FIXTURE_REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


@pytest.fixture
def oidc_config() -> OIDCConfig:
    return OIDCConfig(
        issuer=FIXTURE_ISSUER,
        client_id=FIXTURE_CLIENT_ID,
        client_secret=FIXTURE_CLIENT_SECRET,
        redirect_uri=FIXTURE_REDIRECT_URI,
    )


@pytest.fixture
def oidc_client(oidc_config: OIDCConfig) -> OIDCClient:
    return OIDCClient(oidc_config)


def obtain_auth_code_from_fixture(
    authorization_url: str,
    username: str = "testuser",
    claims: dict | None = None,
) -> tuple[str, str]:
    """Helper to simulate user authentication against the Navikt mock-oauth2-server fixture."""
    parsed_url = urlparse(authorization_url)
    auth_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    query_params = parse_qs(parsed_url.query)

    flat_params = {k: v[0] for k, v in query_params.items()}
    post_data: dict[str, str] = {"username": username}
    if claims:
        post_data["claims"] = json.dumps(claims)

    with httpx.Client() as client:
        resp = client.post(
            auth_endpoint,
            params=flat_params,
            data=post_data,
            follow_redirects=False,
        )
        assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}: {resp.text}"
        location = resp.headers["location"]

    redirect_parsed = urlparse(location)
    callback_params = parse_qs(redirect_parsed.query)
    assert "code" in callback_params, f"No code in callback redirect: {location}"
    assert "state" in callback_params, f"No state in callback redirect: {location}"

    return callback_params["code"][0], callback_params["state"][0]


def test_pkce_rfc7636_test_vector():
    """Verify that SHA-256 PKCE code_challenge derivation matches RFC 7636 Appendix B."""
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    derived_challenge = generate_code_challenge(rfc_verifier)
    assert derived_challenge == expected_challenge


def test_pkce_verifier_generation_entropy():
    """Verify generated code_verifier conforms to RFC 7636 unreserved character requirements and length."""
    verifier = generate_code_verifier()
    assert 43 <= len(verifier) <= 128
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    assert all(c in allowed_chars for c in verifier)


def test_oidc_discovery_fetching(oidc_client: OIDCClient):
    """Verify dynamic discovery parsing from the live OIDC issuer."""
    discovery = oidc_client.fetch_discovery()
    assert discovery.issuer == FIXTURE_ISSUER
    assert discovery.authorization_endpoint == f"{FIXTURE_ISSUER}/authorize"
    assert discovery.token_endpoint == f"{FIXTURE_ISSUER}/token"
    assert discovery.jwks_uri == f"{FIXTURE_ISSUER}/jwks"
    assert discovery.end_session_endpoint == f"{FIXTURE_ISSUER}/endsession"


def test_authorization_request_contains_pkce_state_and_nonce(oidc_client: OIDCClient):
    """Verify authorization URL properly includes PKCE S256 challenge, state, and nonce."""
    auth_url, transaction = oidc_client.create_authorization_url()

    parsed = urlparse(auth_url)
    assert parsed.scheme == "http"
    assert parsed.path == "/default/authorize"

    params = parse_qs(parsed.query)
    assert params["client_id"] == [FIXTURE_CLIENT_ID]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == [FIXTURE_REDIRECT_URI]
    assert params["scope"] == ["openid profile email"]

    # Verify state, nonce, and PKCE parameters
    assert params["state"] == [transaction.state]
    assert params["nonce"] == [transaction.nonce]
    assert params["code_challenge_method"] == ["S256"]

    expected_challenge = generate_code_challenge(transaction.code_verifier)
    assert params["code_challenge"] == [expected_challenge]

    # Verify transaction is stored internally
    assert transaction.state in oidc_client._transactions


def test_successful_code_exchange_and_id_token_validation(oidc_client: OIDCClient):
    """Verify complete end-to-end authorization code exchange, cryptographic verification, and Identity extraction."""
    auth_url, transaction = oidc_client.create_authorization_url()

    expected_claims = {
        "email": "alex@roadtotech.me",
        "name": "Alex Organizer",
        "groups": ["organizers", "vip"],
    }
    code, returned_state = obtain_auth_code_from_fixture(
        auth_url,
        username="alex_sub_101",
        claims=expected_claims,
    )
    assert returned_state == transaction.state

    # Process callback
    identity, tokens = oidc_client.process_callback(code=code, state=returned_state)

    # Validate tokens payload
    assert "access_token" in tokens
    assert "id_token" in tokens
    assert tokens["token_type"].lower() == "bearer"

    # Validate Identity model creation
    assert isinstance(identity, Identity)
    assert identity.subject == "alex_sub_101"
    assert identity.email == "alex@roadtotech.me"
    assert identity.name == "Alex Organizer"
    assert identity.groups == ["organizers", "vip"]


def test_rejection_of_invalid_state(oidc_client: OIDCClient):
    """Verify invalid, missing, and replayed states are rejected with HTTP 400 (CSRF protection)."""
    # 1. Unrecognized state
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state("non_existent_state_value")
    assert exc_info.value.status_code == 400

    # 2. None or empty state
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state("")
    assert exc_info.value.status_code == 400

    # 3. Replay attack rejection: state must only be valid once
    _, transaction = oidc_client.create_authorization_url()
    first_validation = oidc_client.validate_state(transaction.state)
    assert first_validation.state == transaction.state

    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state(transaction.state)
    assert exc_info.value.status_code == 400

    # 4. Expired state rejection
    _, exp_transaction = oidc_client.create_authorization_url()
    # Artificially expire the transaction
    expired_tx = OIDCTransaction(
        state=exp_transaction.state,
        nonce=exp_transaction.nonce,
        code_verifier=exp_transaction.code_verifier,
        created_at=time.time() - 700.0,
        expires_in=600.0,
    )
    oidc_client._transactions[expired_tx.state] = expired_tx

    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state(expired_tx.state)
    assert exc_info.value.status_code == 400


def test_rejection_of_mismatched_nonce(oidc_client: OIDCClient):
    """Verify mismatched or missing nonce causes rejection with HTTP 401."""
    auth_url, transaction = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="nonce_user")

    validated_tx = oidc_client.validate_state(returned_state)
    tokens = oidc_client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    id_token = tokens["id_token"]

    # Validate with mismatched nonce
    with pytest.raises(InvalidNonceError) as exc_info:
        oidc_client.validate_id_token(id_token=id_token, nonce="completely_different_nonce")
    assert exc_info.value.status_code == 401

    # Validating with correct nonce succeeds
    claims = oidc_client.validate_id_token(id_token=id_token, nonce=validated_tx.nonce)
    assert claims["nonce"] == validated_tx.nonce


def test_rejection_of_tampered_id_token_signature(oidc_client: OIDCClient):
    """Verify tampered ID token signature or payload causes cryptographic rejection with HTTP 401."""
    auth_url, transaction = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="tamper_user")

    validated_tx = oidc_client.validate_state(returned_state)
    tokens = oidc_client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    valid_id_token = tokens["id_token"]

    # Valid token passes verification
    oidc_client.validate_id_token(id_token=valid_id_token, nonce=validated_tx.nonce)

    # 1. Tamper signature segment: change the last few characters of the signature
    parts = valid_id_token.split(".")
    assert len(parts) == 3
    header_b64, payload_b64, sig_b64 = parts

    tampered_sig = ("A" if sig_b64[-1] != "A" else "B") + sig_b64[1:]
    tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"

    with pytest.raises(TokenValidationError) as exc_info:
        oidc_client.validate_id_token(id_token=tampered_token, nonce=validated_tx.nonce)
    assert exc_info.value.status_code == 401

    # 2. Tamper payload segment: elevate permissions or change subject
    payload_json = json.loads(base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8"))
    payload_json["sub"] = "hacked_admin_user"
    new_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload_json).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    tampered_payload_token = f"{header_b64}.{new_payload_b64}.{sig_b64}"

    with pytest.raises(TokenValidationError) as exc_info:
        oidc_client.validate_id_token(id_token=tampered_payload_token, nonce=validated_tx.nonce)
    assert exc_info.value.status_code == 401


def test_rejection_of_issuer_or_audience_mismatch(oidc_client: OIDCClient):
    """Verify tokens with unexpected issuer or audience are rejected with HTTP 401."""
    auth_url, transaction = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="mismatch_user")

    validated_tx = oidc_client.validate_state(returned_state)
    tokens = oidc_client.exchange_code(code=code, transaction_or_verifier=validated_tx)
    id_token = tokens["id_token"]

    # Wrong client_id / audience expected
    client_wrong_aud = OIDCClient(
        OIDCConfig(
            issuer=FIXTURE_ISSUER,
            client_id="attacker-client",
            client_secret=FIXTURE_CLIENT_SECRET,
            redirect_uri=FIXTURE_REDIRECT_URI,
        )
    )
    with pytest.raises(TokenValidationError) as exc_info:
        client_wrong_aud.validate_id_token(id_token=id_token, nonce=validated_tx.nonce)
    assert exc_info.value.status_code == 401

    # Wrong issuer expected
    client_wrong_iss = OIDCClient(
        OIDCConfig(
            issuer="http://rogue-idp.example.com",
            client_id=FIXTURE_CLIENT_ID,
            client_secret=FIXTURE_CLIENT_SECRET,
            redirect_uri=FIXTURE_REDIRECT_URI,
        )
    )
    # Pre-populate JWKS from fixture so key is available, but issuer check will fail
    client_wrong_iss._jwk_set = oidc_client.get_jwks()
    with pytest.raises(TokenValidationError) as exc_info:
        client_wrong_iss.validate_id_token(id_token=id_token, nonce=validated_tx.nonce)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_async_oidc_flow(oidc_client: OIDCClient):
    """Verify asynchronous discovery, code exchange, and token validation."""
    discovery = await oidc_client.afetch_discovery()
    assert discovery.issuer == FIXTURE_ISSUER

    auth_url, transaction = oidc_client.create_authorization_url()
    code, returned_state = obtain_auth_code_from_fixture(auth_url, username="async_user")

    identity, tokens = await oidc_client.aprocess_callback(code=code, state=returned_state)
    assert identity.subject == "async_user"
    assert "access_token" in tokens
    assert "id_token" in tokens


def test_auth_adapter_protocol_conformance(oidc_client: OIDCClient):
    """Verify OIDCAuthAdapter adheres to the hexagonal AuthPort Protocol."""
    adapter = OIDCAuthAdapter(client=oidc_client)
    assert isinstance(adapter, AuthPort)

    from fastapi import Request

    mock_req = Request({"type": "http", "method": "GET", "path": "/test", "headers": []})
    login_resp = adapter.login(mock_req)
    assert login_resp.status_code == 302
    assert "/default/authorize?" in login_resp.headers["location"]
