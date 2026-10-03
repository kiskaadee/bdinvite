import base64
import hashlib
import secrets
import string
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException, status
import httpx
import jwt

from .identity import Identity

PKCE_CHARSET = string.ascii_letters + string.digits + "-._~"
DEFAULT_SCOPES = ["openid", "profile", "email"]
DEFAULT_SIGNING_ALGS = [
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
    "PS256",
    "PS384",
    "PS512",
]


class OIDCError(HTTPException):
    """Base exception for all OIDC protocol and authentication errors."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


class InvalidStateError(OIDCError):
    """Raised when the state parameter is missing, invalid, or expired (CSRF protection)."""

    def __init__(self, detail: str = "Invalid, missing, or expired state parameter") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class MismatchedNonceError(OIDCError):
    """Raised when the nonce in the ID token does not match the request nonce (Replay protection)."""

    def __init__(self, detail: str = "Mismatched or missing nonce claim in ID token") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class InvalidTokenError(OIDCError):
    """Raised when the ID token signature, issuer, audience, or expiration is invalid."""

    def __init__(self, detail: str = "Invalid or expired ID token") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class DiscoveryError(OIDCError):
    """Raised when dynamic OIDC discovery configuration cannot be retrieved or parsed."""

    def __init__(self, detail: str = "Failed to fetch or parse OIDC discovery document") -> None:
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


class TokenExchangeError(OIDCError):
    """Raised when the token endpoint returns an error during authorization code exchange."""

    def __init__(self, detail: str = "Failed to exchange authorization code for tokens") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@dataclass
class OIDCConfig:
    """Configuration for generic OIDC client."""

    issuer: str
    client_id: str
    client_secret: Optional[str] = None
    redirect_uri: str = "http://localhost:8000/birthday/api/auth/callback"
    scopes: list[str] = field(default_factory=lambda: list(DEFAULT_SCOPES))
    groups_claim: str = "groups"

    def __post_init__(self) -> None:
        if not isinstance(self.issuer, str) or not self.issuer.strip():
            raise ValueError("OIDC issuer must be a non-empty string")
        if not isinstance(self.client_id, str) or not self.client_id.strip():
            raise ValueError("OIDC client_id must be a non-empty string")
        if not isinstance(self.redirect_uri, str) or not self.redirect_uri.strip():
            raise ValueError("OIDC redirect_uri must be a non-empty string")
        if not isinstance(self.groups_claim, str) or not self.groups_claim.strip():
            raise ValueError("OIDC groups_claim must be a non-empty string")
        self.issuer = self.issuer.rstrip("/")


def _extract_claim_path(claims: dict[str, Any], path: str) -> Any:
    """Extract claim value from dictionary supporting dot-separated paths (e.g. 'realm_access.roles')."""
    current: Any = claims
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


@dataclass
class OIDCTransaction:
    """In-flight authentication transaction state."""

    state: str
    nonce: str
    code_verifier: str
    created_at: float = field(default_factory=time.time)


@dataclass
class AuthorizationRequest:
    """Initiated authorization request containing URL and security secrets."""

    url: str
    state: str
    nonce: str
    code_verifier: str


@dataclass
class TokenResponse:
    """Result of token endpoint exchange and cryptographic validation."""

    id_token: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)
    claims: dict[str, Any] = field(default_factory=dict)


def generate_code_verifier(length: int = 64) -> str:
    """Generate cryptographically secure PKCE code_verifier (RFC 7636 Section 4.1)."""
    if not (43 <= length <= 128):
        raise ValueError("PKCE code_verifier length must be between 43 and 128 characters")
    return "".join(secrets.choice(PKCE_CHARSET) for _ in range(length))


def compute_code_challenge(code_verifier: str) -> str:
    """Derive PKCE code_challenge using SHA-256 (RFC 7636 Section 4.2)."""
    if not (43 <= len(code_verifier) <= 128):
        raise ValueError("PKCE code_verifier length must be between 43 and 128 characters")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_state(nbytes: int = 32) -> str:
    """Generate cryptographic state token for CSRF protection."""
    return secrets.token_urlsafe(nbytes)


def generate_nonce(nbytes: int = 32) -> str:
    """Generate cryptographic nonce for replay protection."""
    return secrets.token_urlsafe(nbytes)


class OIDCClient:
    """Generic OpenID Connect (OIDC) client supporting Dynamic Discovery, PKCE, and JWT Verification."""

    def __init__(
        self,
        config: Optional[OIDCConfig] = None,
        *,
        issuer: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        groups_claim: Optional[str] = None,
        discovery_doc: Optional[dict[str, Any]] = None,
        timeout: float = 10.0,
        max_state_age_seconds: float = 600.0,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            if not issuer or not client_id:
                raise ValueError("Both 'issuer' and 'client_id' are required if 'config' is not supplied")
            self.config = OIDCConfig(
                issuer=issuer,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri or "http://localhost:8000/birthday/api/auth/callback",
                scopes=scopes if scopes is not None else list(DEFAULT_SCOPES),
                groups_claim=groups_claim or "groups",
            )

        self.timeout = timeout
        self.max_state_age_seconds = max_state_age_seconds
        self._discovery_doc: Optional[dict[str, Any]] = discovery_doc
        self._jwks_client: Optional[jwt.PyJWKClient] = None
        self._transactions: dict[str, OIDCTransaction] = {}

    def get_discovery_document(self, refresh: bool = False) -> dict[str, Any]:
        """Fetch and parse OIDC discovery configuration dynamically from the issuer."""
        if self._discovery_doc is not None and not refresh:
            return self._discovery_doc

        discovery_url = f"{self.config.issuer}/.well-known/openid-configuration"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(discovery_url)
                if response.status_code != 200:
                    raise DiscoveryError(
                        f"Discovery endpoint returned HTTP {response.status_code}: {response.text}"
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise DiscoveryError("Discovery document root must be a JSON object")
                self._discovery_doc = data
                return data
        except DiscoveryError:
            raise
        except Exception as e:
            raise DiscoveryError(f"Failed to fetch discovery document from {discovery_url}: {e}") from e

    def _get_discovery_field(self, field_name: str) -> str:
        doc = self.get_discovery_document()
        val = doc.get(field_name)
        if not val or not isinstance(val, str):
            raise DiscoveryError(f"Discovery document missing required field: {field_name}")
        return val

    @property
    def authorization_endpoint(self) -> str:
        return self._get_discovery_field("authorization_endpoint")

    @property
    def token_endpoint(self) -> str:
        return self._get_discovery_field("token_endpoint")

    @property
    def jwks_uri(self) -> str:
        return self._get_discovery_field("jwks_uri")

    @property
    def userinfo_endpoint(self) -> Optional[str]:
        doc = self.get_discovery_document()
        val = doc.get("userinfo_endpoint")
        return str(val) if val else None

    @property
    def end_session_endpoint(self) -> Optional[str]:
        doc = self.get_discovery_document()
        val = doc.get("end_session_endpoint")
        return str(val) if val else None

    @property
    def supported_signing_algorithms(self) -> list[str]:
        doc = self.get_discovery_document()
        discovered = doc.get("id_token_signing_alg_values_supported")
        if isinstance(discovered, list) and discovered:
            # Union discovered with default algorithms while preserving order
            algs = [str(a) for a in discovered if isinstance(a, str)]
            for alg in DEFAULT_SIGNING_ALGS:
                if alg not in algs:
                    algs.append(alg)
            return algs
        return list(DEFAULT_SIGNING_ALGS)

    def get_jwks_client(self, refresh: bool = False) -> jwt.PyJWKClient:
        """Obtain or cache PyJWKClient for signing key resolution."""
        if self._jwks_client is None or refresh:
            self._jwks_client = jwt.PyJWKClient(self.jwks_uri, cache_jwk_set=True, lifespan=3600)
        return self._jwks_client

    def save_transaction(self, transaction: OIDCTransaction) -> None:
        """Store an in-flight authentication transaction."""
        self._prune_expired_transactions()
        self._transactions[transaction.state] = transaction

    def _prune_expired_transactions(self) -> None:
        now = time.time()
        expired = [
            s for s, tx in self._transactions.items()
            if now - tx.created_at > self.max_state_age_seconds
        ]
        for s in expired:
            self._transactions.pop(s, None)

    def validate_state(self, state: Optional[str]) -> OIDCTransaction:
        """Validate state parameter against pending transactions, rejecting CSRF attacks with HTTP 400."""
        self._prune_expired_transactions()
        if not state or not isinstance(state, str) or not state.strip():
            raise InvalidStateError("State parameter is missing or empty")

        transaction = self._transactions.pop(state, None)
        if transaction is None:
            raise InvalidStateError("Invalid or expired state parameter")

        return transaction

    def create_authorization_url(
        self,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        code_verifier: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        extra_params: Optional[dict[str, str]] = None,
    ) -> AuthorizationRequest:
        """Generate authorization URL with PKCE (S256), cryptographic state, and nonce."""
        actual_state = state if state is not None else generate_state()
        actual_nonce = nonce if nonce is not None else generate_nonce()
        actual_verifier = code_verifier if code_verifier is not None else generate_code_verifier()

        code_challenge = compute_code_challenge(actual_verifier)

        # Persist transaction for authorization code exchange
        self.save_transaction(
            OIDCTransaction(
                state=actual_state,
                nonce=actual_nonce,
                code_verifier=actual_verifier,
            )
        )

        query_scopes = scopes if scopes is not None else self.config.scopes
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(query_scopes),
            "state": actual_state,
            "nonce": actual_nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if extra_params:
            params.update(extra_params)

        auth_url = f"{self.authorization_endpoint}?{urllib.parse.urlencode(params)}"
        return AuthorizationRequest(
            url=auth_url,
            state=actual_state,
            nonce=actual_nonce,
            code_verifier=actual_verifier,
        )

    def get_signing_key(self, token: str) -> Any:
        """Resolve cryptographic signing key from JWKS."""
        jwks_client = self.get_jwks_client()
        try:
            return jwks_client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError as e:
            try:
                jwk_set = jwks_client.get_jwk_set()
                if jwk_set and len(jwk_set.keys) == 1:
                    return jwk_set.keys[0]
            except Exception:
                pass
            raise InvalidTokenError(f"Signing key not found in JWKS: {e}") from e
        except jwt.DecodeError as e:
            raise InvalidTokenError(f"ID token signature is invalid or tampered: {e}") from e
        except Exception as e:
            raise InvalidTokenError(f"Error resolving signing key from JWKS: {e}") from e

    def verify_id_token(
        self,
        id_token: str,
        nonce: Optional[str] = None,
        leeway: float = 60.0,
    ) -> dict[str, Any]:
        """Cryptographically validate returned ID token.

        Validations:
        - Signature verification against keys from JWKS.
        - Issuer validation (iss == issuer).
        - Audience validation (aud == client_id).
        - Expiration validation (exp > current_time).
        - Nonce validation (nonce == expected_nonce).
        - Rejection of tampered signatures or claims (HTTP 401).
        """
        if not id_token or not isinstance(id_token, str) or not id_token.strip():
            raise InvalidTokenError("ID token must be a non-empty string")

        signing_key = self.get_signing_key(id_token)

        try:
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=self.supported_signing_algorithms,
                issuer=self.config.issuer,
                audience=self.config.client_id,
                leeway=leeway,
                options={
                    "verify_signature": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
        except jwt.ExpiredSignatureError as e:
            raise InvalidTokenError(f"ID token has expired: {e}") from e
        except (jwt.InvalidSignatureError, jwt.DecodeError) as e:
            raise InvalidTokenError(f"ID token signature is invalid or tampered: {e}") from e
        except (jwt.InvalidAudienceError, jwt.InvalidIssuerError) as e:
            raise InvalidTokenError(f"ID token claims validation failed: {e}") from e
        except jwt.PyJWTError as e:
            raise InvalidTokenError(f"ID token verification failed: {e}") from e

        # Validate nonce claim for replay protection
        if nonce is not None:
            token_nonce = claims.get("nonce")
            if not token_nonce or token_nonce != nonce:
                raise MismatchedNonceError(
                    f"ID token nonce '{token_nonce}' does not match expected nonce '{nonce}'"
                )

        return claims

    def exchange_code(
        self,
        code: str,
        state: Optional[str] = None,
        code_verifier: Optional[str] = None,
        nonce: Optional[str] = None,
        extra_token_params: Optional[dict[str, str]] = None,
    ) -> TokenResponse:
        """Exchange authorization code for tokens using PKCE code_verifier and cryptographically verify ID token."""
        if not code or not isinstance(code, str) or not code.strip():
            raise TokenExchangeError("Authorization code must be a non-empty string")

        # Resolve state and secrets
        resolved_verifier = code_verifier
        resolved_nonce = nonce

        if state is not None:
            if resolved_verifier is None or resolved_nonce is None:
                # State lookup is required to recover transaction secrets
                tx = self.validate_state(state)
                resolved_verifier = tx.code_verifier
                resolved_nonce = tx.nonce
            else:
                # State was provided alongside explicit secrets; validate if tracked
                if state in self._transactions:
                    self._transactions.pop(state)
                elif not state.strip():
                    raise InvalidStateError("State parameter cannot be empty")
        elif resolved_verifier is None:
            raise InvalidStateError("Either valid state or explicit code_verifier must be provided")

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "code_verifier": resolved_verifier,
        }
        if extra_token_params:
            data.update(extra_token_params)

        auth: Optional[httpx.BasicAuth] = None
        if self.config.client_secret:
            auth = httpx.BasicAuth(self.config.client_id, self.config.client_secret)
            data["client_id"] = self.config.client_id
            data["client_secret"] = self.config.client_secret
        else:
            data["client_id"] = self.config.client_id

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if auth is not None:
                    response = client.post(
                        self.token_endpoint,
                        data=data,
                        auth=auth,
                        headers={"Accept": "application/json"},
                    )
                else:
                    response = client.post(
                        self.token_endpoint,
                        data=data,
                        headers={"Accept": "application/json"},
                    )
        except Exception as e:
            raise TokenExchangeError(f"Failed to communicate with token endpoint: {e}") from e

        if response.status_code != 200:
            raise TokenExchangeError(
                f"Token endpoint returned HTTP {response.status_code}: {response.text}"
            )

        try:
            token_data = response.json()
        except Exception as e:
            raise TokenExchangeError(f"Failed to parse token response JSON: {e}") from e

        if not isinstance(token_data, dict):
            raise TokenExchangeError("Token response JSON root must be an object")

        id_token = token_data.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenExchangeError("Token response missing 'id_token'")

        # Cryptographically verify returned ID token
        claims = self.verify_id_token(id_token, nonce=resolved_nonce)

        return TokenResponse(
            id_token=id_token,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type"),
            expires_in=token_data.get("expires_in"),
            raw=token_data,
            claims=claims,
        )

    def extract_identity(self, claims: dict[str, Any]) -> Identity:
        """Map validated ID token claims into typed Identity domain model.

        Extracts:
        - sub -> Identity.subject (non-empty string required)
        - email -> Identity.email (falls back to {sub}@{client_id}.local if not present)
        - name -> Identity.name (optional string or None)
        - groups_claim path -> Identity.groups (list of unique strings, defaults to [])
        """
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise InvalidTokenError("ID token missing required 'sub' claim")

        email_val = claims.get("email")
        if email_val and isinstance(email_val, str) and email_val.strip():
            email = email_val.strip()
        else:
            email = f"{subject}@{self.config.client_id}.local"

        name_val = claims.get("name")
        name = str(name_val).strip() if name_val and isinstance(name_val, str) and name_val.strip() else None

        raw_groups = _extract_claim_path(claims, self.config.groups_claim)
        if isinstance(raw_groups, str):
            groups = [raw_groups.strip()] if raw_groups.strip() else []
        elif isinstance(raw_groups, (list, tuple, set)):
            groups = [str(g).strip() for g in raw_groups if isinstance(g, str) and str(g).strip()]
        else:
            groups = []

        # Deduplicate while preserving order
        unique_groups = list(dict.fromkeys(groups))

        return Identity(
            subject=subject,
            email=email,
            name=name,
            groups=unique_groups,
        )

    def extract_identity_from_token(
        self,
        id_token: str,
        nonce: Optional[str] = None,
        leeway: float = 60.0,
    ) -> Identity:
        """Cryptographically verify ID token and extract domain Identity with origin integrity."""
        claims = self.verify_id_token(id_token=id_token, nonce=nonce, leeway=leeway)
        return self.extract_identity(claims)

    def authenticate_with_password(
        self,
        username: str,
        password: str,
        scopes: Optional[list[str]] = None,
    ) -> tuple[TokenResponse, Identity]:
        """Authenticate using resource owner password credentials against IdP and extract Identity.

        Validates returned ID token cryptographically and maps claims to domain Identity.
        """
        if not username or not isinstance(username, str) or not username.strip():
            raise TokenExchangeError("Username must be a non-empty string")
        if not password or not isinstance(password, str):
            raise TokenExchangeError("Password must be a non-empty string")

        query_scopes = scopes if scopes is not None else self.config.scopes
        data: dict[str, str] = {
            "grant_type": "password",
            "client_id": self.config.client_id,
            "username": username,
            "password": password,
            "scope": " ".join(query_scopes),
        }

        auth: Optional[httpx.BasicAuth] = None
        if self.config.client_secret:
            auth = httpx.BasicAuth(self.config.client_id, self.config.client_secret)
            data["client_secret"] = self.config.client_secret

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if auth is not None:
                    response = client.post(
                        self.token_endpoint,
                        data=data,
                        auth=auth,
                        headers={"Accept": "application/json"},
                    )
                else:
                    response = client.post(
                        self.token_endpoint,
                        data=data,
                        headers={"Accept": "application/json"},
                    )
        except Exception as e:
            raise TokenExchangeError(f"Failed to communicate with token endpoint: {e}") from e

        if response.status_code != 200:
            raise TokenExchangeError(
                f"Token endpoint returned HTTP {response.status_code}: {response.text}"
            )

        try:
            token_data = response.json()
        except Exception as e:
            raise TokenExchangeError(f"Failed to parse token response JSON: {e}") from e

        if not isinstance(token_data, dict):
            raise TokenExchangeError("Token response JSON root must be an object")

        id_token = token_data.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenExchangeError("Token response missing 'id_token'")

        claims = self.verify_id_token(id_token)
        token_response = TokenResponse(
            id_token=id_token,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type"),
            expires_in=token_data.get("expires_in"),
            raw=token_data,
            claims=claims,
        )
        identity = self.extract_identity(claims)
        return token_response, identity
