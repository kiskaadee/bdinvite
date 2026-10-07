import base64
import json
import urllib.parse

import httpx
import pytest

from app.auth import (
    Identity,
    InvalidStateError,
    InvalidTokenError,
    MismatchedNonceError,
    OIDCClient,
    compute_code_challenge,
    generate_code_verifier,
    generate_nonce,
    generate_state,
)

LIVE_ISSUER = "http://localhost:8088/default"
CLIENT_ID = "bdinvite-client"
CLIENT_SECRET = "bdinvite-secret"
REDIRECT_URI = "http://localhost:8000/birthday/api/auth/callback"


@pytest.fixture
def oidc_client() -> OIDCClient:
    return OIDCClient(
        issuer=LIVE_ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
    )


def test_pkce_generation_and_challenge():
    """Verify PKCE code_verifier generation and S256 derivation per RFC 7636."""
    verifier = generate_code_verifier(64)
    assert len(verifier) == 64
    # RFC 7636 Section 4.1 unreserved characters
    unreserved = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
    )
    assert all(c in unreserved for c in verifier)

    # Length bounds validation
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(42)
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(129)

    # RFC 7636 Appendix B test vector verification
    appendix_b_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    derived_challenge = compute_code_challenge(appendix_b_verifier)
    assert derived_challenge == expected_challenge


def test_state_and_nonce_generation():
    """Verify cryptographic randomness and uniqueness for state and nonce."""
    s1 = generate_state()
    s2 = generate_state()
    assert len(s1) >= 32
    assert s1 != s2

    n1 = generate_nonce()
    n2 = generate_nonce()
    assert len(n1) >= 32
    assert n1 != n2


def test_dynamic_discovery_parsing(oidc_client: OIDCClient):
    """Dynamic discovery configuration is fetched and parsed correctly from the issuer."""
    doc = oidc_client.get_discovery_document()
    assert doc["issuer"] == LIVE_ISSUER
    assert oidc_client.authorization_endpoint == f"{LIVE_ISSUER}/authorize"
    assert oidc_client.token_endpoint == f"{LIVE_ISSUER}/token"
    assert oidc_client.jwks_uri == f"{LIVE_ISSUER}/jwks"

    # Cached discovery returns identical object without additional fetch
    doc_cached = oidc_client.get_discovery_document()
    assert doc_cached is doc


def test_dynamic_discovery_failure():
    """Unreachable or invalid discovery URL raises DiscoveryError with HTTP 502."""
    from app.auth.oidc import DiscoveryError

    broken_client = OIDCClient(
        issuer="http://localhost:59999/nonexistent",
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        timeout=1.0,
    )
    with pytest.raises(DiscoveryError) as exc_info:
        broken_client.get_discovery_document()
    assert exc_info.value.status_code == 502


def test_authorization_request_contains_pkce_state_and_nonce(oidc_client: OIDCClient):
    """Authorization request contains required PKCE challenge, state, and nonce parameters."""
    auth_req = oidc_client.create_authorization_url()

    parsed = urllib.parse.urlparse(auth_req.url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "localhost:8088"
    assert parsed.path == "/default/authorize"

    qs = urllib.parse.parse_qs(parsed.query)
    assert qs["response_type"] == ["code"]
    assert qs["client_id"] == [CLIENT_ID]
    assert qs["redirect_uri"] == [REDIRECT_URI]
    assert qs["state"] == [auth_req.state]
    assert qs["nonce"] == [auth_req.nonce]
    assert qs["code_challenge_method"] == ["S256"]

    # Verify code_challenge matches SHA256 of code_verifier
    expected_challenge = compute_code_challenge(auth_req.code_verifier)
    assert qs["code_challenge"] == [expected_challenge]


def test_rejection_of_invalid_state_400(oidc_client: OIDCClient):
    """Rejection of missing or unregistered state with HTTP 400."""
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state("unregistered_state_token")
    assert exc_info.value.status_code == 400

    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state("")
    assert exc_info.value.status_code == 400

    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.validate_state(None)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    # In exchange_code, untracked state must also be rejected with HTTP 400
    with pytest.raises(InvalidStateError) as exc_info:
        oidc_client.exchange_code(code="dummy_code", state="unregistered_state")
    assert exc_info.value.status_code == 400


def test_live_oidc_successful_code_exchange_and_id_token_validation(
    oidc_client: OIDCClient,
):
    """End-to-end integration test: code exchange, ID token validation, and Identity extraction."""
    # 1. Create authorization request with PKCE and transaction secrets
    auth_req = oidc_client.create_authorization_url()

    # 2. Simulate authorization sign-in against mock OIDC provider
    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={
                "username": "alice",
                "claims": json.dumps(
                    {
                        "email": "alice@example.com",
                        "name": "Alice In Chains",
                        "groups": ["family", "vip"],
                    }
                ),
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, (
            f"Expected 302 redirect from mock IdP, got {resp.status_code}"
        )
        redirect_url = resp.headers["location"]

    qs = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)
    assert "code" in qs
    assert qs["state"] == [auth_req.state]
    code = qs["code"][0]

    # 3. Exchange authorization code with token endpoint
    token_resp = oidc_client.exchange_code(code=code, state=auth_req.state)

    # 4. Verify cryptographic validation and claim assertions
    assert token_resp.id_token
    assert token_resp.token_type == "Bearer"
    assert token_resp.claims["iss"] == LIVE_ISSUER
    assert token_resp.claims["aud"] == CLIENT_ID
    assert token_resp.claims["nonce"] == auth_req.nonce
    assert token_resp.claims["sub"] in ["alice", "admin-001"]
    assert token_resp.claims["email"] == "alice@example.com"
    assert token_resp.claims["name"] == "Alice In Chains"
    assert token_resp.claims["groups"] == ["family", "vip"]

    # 5. Verify mapping to Identity domain model
    identity = oidc_client.extract_identity(token_resp.claims)
    assert isinstance(identity, Identity)
    assert identity.subject in ["alice", "admin-001"]
    assert identity.email == "alice@example.com"
    assert identity.name == "Alice In Chains"
    assert identity.groups == ["family", "vip"]
    assert identity.has_group("vip") is True


def test_rejection_of_mismatched_nonce_401(oidc_client: OIDCClient):
    """Rejection of mismatched nonce claim in returned ID token with HTTP 401."""
    auth_req = oidc_client.create_authorization_url()

    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={"username": "bob"},
            follow_redirects=False,
        )
        redirect_url = resp.headers["location"]

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)["code"][0]
    token_resp = oidc_client.exchange_code(code=code, state=auth_req.state)

    # Verifying valid token against wrong nonce MUST raise MismatchedNonceError (HTTP 401)
    with pytest.raises(MismatchedNonceError) as exc_info:
        oidc_client.verify_id_token(
            token_resp.id_token, nonce="completely_different_nonce"
        )
    assert exc_info.value.status_code == 401
    assert "does not match expected nonce" in str(exc_info.value.detail)

    # Verifying with the correct nonce succeeds
    verified = oidc_client.verify_id_token(token_resp.id_token, nonce=auth_req.nonce)
    assert verified["sub"] in ["bob", "admin-001"]


def test_rejection_of_tampered_id_token_signature_401(oidc_client: OIDCClient):
    """Rejection of tampered ID token signature with HTTP 401."""
    auth_req = oidc_client.create_authorization_url()

    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={"username": "charlie"},
            follow_redirects=False,
        )
        redirect_url = resp.headers["location"]

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)["code"][0]
    token_resp = oidc_client.exchange_code(code=code, state=auth_req.state)
    original_id_token = token_resp.id_token

    # Case 1: Tamper the cryptographic signature portion
    tampered_sig_token = original_id_token[:-12] + "TAMPERED_SIG"
    with pytest.raises(InvalidTokenError) as exc_info:
        oidc_client.verify_id_token(tampered_sig_token, nonce=auth_req.nonce)
    assert exc_info.value.status_code == 401
    assert "signature is invalid or tampered" in str(exc_info.value.detail)

    # Case 2: Tamper the payload while preserving original signature
    parts = original_id_token.split(".")
    assert len(parts) == 3
    # Decode and tamper payload
    payload_raw = parts[1] + "=="
    payload = json.loads(base64.urlsafe_b64decode(payload_raw))
    payload["sub"] = "mallory_attacker"
    tampered_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    tampered_payload_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

    with pytest.raises(InvalidTokenError) as exc_info:
        oidc_client.verify_id_token(tampered_payload_token, nonce=auth_req.nonce)
    assert exc_info.value.status_code == 401


def test_rejection_of_wrong_issuer_and_audience_401(oidc_client: OIDCClient):
    """Rejection of ID token when issuer or audience does not match client configuration."""
    auth_req = oidc_client.create_authorization_url()

    with httpx.Client() as http:
        resp = http.post(
            auth_req.url,
            data={"username": "david"},
            follow_redirects=False,
        )
        redirect_url = resp.headers["location"]

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)["code"][0]
    token_resp = oidc_client.exchange_code(code=code, state=auth_req.state)

    # Client configured with mismatched audience
    wrong_aud_client = OIDCClient(
        issuer=LIVE_ISSUER,
        client_id="other-audience-client",
        redirect_uri=REDIRECT_URI,
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        wrong_aud_client.verify_id_token(token_resp.id_token, nonce=auth_req.nonce)
    assert exc_info.value.status_code == 401
    assert "claims validation failed" in str(exc_info.value.detail)

    # Client configured with mismatched issuer
    wrong_iss_client = OIDCClient(
        issuer="http://localhost:8088/wrong_issuer",
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        discovery_doc=oidc_client.get_discovery_document(),
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        wrong_iss_client.verify_id_token(token_resp.id_token, nonce=auth_req.nonce)
    assert exc_info.value.status_code == 401


def test_architectural_isolation_no_domain_route_crypto_imports():
    """Verify architectural isolation: zero application domain routes import OIDC/crypto directly."""
    import pathlib

    routes_dir = pathlib.Path(__file__).parent.parent / "app" / "routes"
    disallowed_terms = ["jwt", "cryptography", "PyJWKClient", "OIDCClient"]

    for route_file in routes_dir.glob("*.py"):
        content = route_file.read_text(encoding="utf-8")
        for term in disallowed_terms:
            assert f"import {term}" not in content, (
                f"{route_file.name} violates isolation by importing {term}"
            )
            assert f"from {term}" not in content, (
                f"{route_file.name} violates isolation by importing from {term}"
            )
