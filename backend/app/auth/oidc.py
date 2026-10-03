"""Generic OpenID Connect (OIDC) client with PKCE and cryptographic token verification."""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKSet
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from .port import Identity


class OIDCError(HTTPException):
    """Base exception for OIDC protocol errors."""

    def __init__(self, status_code: int = 400, detail: str = "OIDC error") -> None:
        super().__init__(status_code=status_code, detail=detail)


class InvalidStateError(OIDCError):
    """Raised when the state parameter is missing, invalid, expired, or replayed (CSRF protection)."""

    def __init__(self, detail: str = "Invalid or expired state parameter") -> None:
        super().__init__(status_code=400, detail=detail)


class InvalidNonceError(OIDCError):
    """Raised when ID token nonce claim does not match the initiated request nonce."""

    def __init__(self, detail: str = "Invalid or mismatched nonce") -> None:
        super().__init__(status_code=401, detail=detail)


class TokenValidationError(OIDCError):
    """Raised when ID token cryptographic validation fails (signature, issuer, aud, exp)."""

    def __init__(self, detail: str = "Token validation failed") -> None:
        super().__init__(status_code=401, detail=detail)


class InvalidCodeVerifierError(OIDCError):
    """Raised when PKCE code_verifier is missing, invalid, or rejected during token exchange."""

    def __init__(self, detail: str = "Invalid or missing PKCE code_verifier") -> None:
        super().__init__(status_code=401, detail=detail)


def generate_code_verifier() -> str:
    """Generate a high-entropy cryptographic random string for PKCE (RFC 7636).

    Length is 86 URL-safe characters, well within the RFC 7636 [43, 128] range.
    """
    return secrets.token_urlsafe(64)


def generate_code_challenge(code_verifier: str) -> str:
    """Calculate S256 code_challenge from code_verifier (RFC 7636).

    code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier))) without padding.
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_state() -> str:
    """Generate a cryptographically secure random state parameter for CSRF mitigation."""
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    """Generate a cryptographically secure random nonce parameter for replay protection."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class OIDCTransaction:
    """Authentication transaction state for PKCE, CSRF, and replay mitigation."""

    state: str
    nonce: str
    code_verifier: str
    created_at: float = field(default_factory=time.time)
    expires_in: float = 600.0  # 10 minutes

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.created_at + self.expires_in)


@dataclass(frozen=True)
class OIDCDiscovery:
    """Parsed OpenID Connect discovery document."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: Optional[str] = None
    end_session_endpoint: Optional[str] = None
    raw_document: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OIDCConfig:
    """Configuration for Generic OIDC Client."""

    issuer: str
    client_id: str
    client_secret: Optional[str] = None
    redirect_uri: str = "http://localhost:8000/birthday/api/auth/callback"
    scope: str = "openid profile email"
    discovery_url: Optional[str] = None
    request_timeout: float = 10.0
    groups_claim: str = "groups"
    group_claim_path: Optional[str] = None

    def __post_init__(self) -> None:
        if self.group_claim_path and self.groups_claim == "groups":
            object.__setattr__(self, "groups_claim", self.group_claim_path)
        elif self.group_claim_path is None:
            object.__setattr__(self, "group_claim_path", self.groups_claim)



class OIDCClient:
    """Generic OpenID Connect client implementing PKCE (RFC 7636) and JWKS verification."""

    def __init__(self, config: OIDCConfig) -> None:
        self.config = config
        self._discovery: Optional[OIDCDiscovery] = None
        self._jwk_set: Optional[PyJWKSet] = None
        self._transactions: dict[str, OIDCTransaction] = {}

    @property
    def discovery_url(self) -> str:
        if self.config.discovery_url:
            return self.config.discovery_url
        return f"{self.config.issuer.rstrip('/')}/.well-known/openid-configuration"

    def fetch_discovery(self, force_refresh: bool = False) -> OIDCDiscovery:
        """Fetch and parse OIDC discovery configuration dynamically from the issuer."""
        if self._discovery is not None and not force_refresh:
            return self._discovery

        with httpx.Client(timeout=self.config.request_timeout) as client:
            resp = client.get(self.discovery_url)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=502,
                    detail=f"Failed to fetch OIDC discovery from {self.discovery_url}: {resp.status_code}",
                )
            data = resp.json()

        self._discovery = self._parse_discovery_data(data)
        return self._discovery

    async def afetch_discovery(self, force_refresh: bool = False) -> OIDCDiscovery:
        """Asynchronously fetch and parse OIDC discovery configuration."""
        if self._discovery is not None and not force_refresh:
            return self._discovery

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            resp = await client.get(self.discovery_url)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=502,
                    detail=f"Failed to fetch OIDC discovery from {self.discovery_url}: {resp.status_code}",
                )
            data = resp.json()

        self._discovery = self._parse_discovery_data(data)
        return self._discovery

    def _parse_discovery_data(self, data: dict[str, Any]) -> OIDCDiscovery:
        issuer = data.get("issuer")
        if not issuer:
            raise OIDCError(status_code=502, detail="OIDC discovery missing 'issuer'")

        auth_endpoint = data.get("authorization_endpoint")
        token_endpoint = data.get("token_endpoint")
        jwks_uri = data.get("jwks_uri")

        if not auth_endpoint or not token_endpoint or not jwks_uri:
            raise OIDCError(
                status_code=502,
                detail="OIDC discovery document missing required endpoints (auth, token, or jwks)",
            )

        return OIDCDiscovery(
            issuer=issuer,
            authorization_endpoint=auth_endpoint,
            token_endpoint=token_endpoint,
            jwks_uri=jwks_uri,
            userinfo_endpoint=data.get("userinfo_endpoint"),
            end_session_endpoint=data.get("end_session_endpoint"),
            raw_document=data,
        )

    @property
    def discovery(self) -> OIDCDiscovery:
        if self._discovery is None:
            return self.fetch_discovery()
        return self._discovery

    @property
    def authorization_endpoint(self) -> str:
        return self.discovery.authorization_endpoint

    @property
    def token_endpoint(self) -> str:
        return self.discovery.token_endpoint

    @property
    def jwks_uri(self) -> str:
        return self.discovery.jwks_uri

    @property
    def end_session_endpoint(self) -> Optional[str]:
        return self.discovery.end_session_endpoint

    def get_jwks(self, force_refresh: bool = False) -> PyJWKSet:
        """Fetch and cache JWK Set from jwks_uri."""
        if self._jwk_set is not None and not force_refresh:
            return self._jwk_set

        with httpx.Client(timeout=self.config.request_timeout) as client:
            resp = client.get(self.jwks_uri)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=502,
                    detail=f"Failed to fetch JWKS from {self.jwks_uri}: {resp.status_code}",
                )
            jwks_data = resp.json()

        self._jwk_set = PyJWKSet.from_dict(jwks_data)
        return self._jwk_set

    async def aget_jwks(self, force_refresh: bool = False) -> PyJWKSet:
        """Asynchronously fetch and cache JWK Set from jwks_uri."""
        if self._jwk_set is not None and not force_refresh:
            return self._jwk_set

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            resp = await client.get(self.jwks_uri)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=502,
                    detail=f"Failed to fetch JWKS from {self.jwks_uri}: {resp.status_code}",
                )
            jwks_data = resp.json()

        self._jwk_set = PyJWKSet.from_dict(jwks_data)
        return self._jwk_set

    def create_authorization_url(
        self,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        code_verifier: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> tuple[str, OIDCTransaction]:
        """Generate authorization URL with PKCE (S256), state, and nonce.

        Persists the transaction state in the client's internal transaction store.
        """
        state = state or generate_state()
        nonce = nonce or generate_nonce()
        code_verifier = code_verifier or generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        transaction = OIDCTransaction(
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )
        self._transactions[state] = transaction

        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "scope": scope or self.config.scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{self.authorization_endpoint}?{urlencode(params)}"
        return auth_url, transaction

    def validate_state(self, state: Optional[str]) -> OIDCTransaction:
        """Validate and consume the state parameter (CSRF protection & replay prevention).

        Raises InvalidStateError (HTTP 400) if state is missing, unknown, replayed, or expired.
        """
        if not state or not isinstance(state, str):
            raise InvalidStateError("Missing or empty state parameter")

        transaction = self._transactions.pop(state, None)
        if transaction is None:
            raise InvalidStateError("Unrecognized or already consumed state parameter")

        if transaction.is_expired:
            raise InvalidStateError("Authentication transaction has expired")

        return transaction

    def exchange_code(
        self,
        code: str,
        transaction_or_verifier: Union[OIDCTransaction, str],
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Exchange authorization code for tokens using PKCE code_verifier."""
        if isinstance(transaction_or_verifier, OIDCTransaction):
            code_verifier = transaction_or_verifier.code_verifier
        else:
            code_verifier = transaction_or_verifier

        if not code_verifier or not isinstance(code_verifier, str) or not code_verifier.strip():
            raise InvalidCodeVerifierError("Missing or invalid PKCE code_verifier")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.config.redirect_uri,
            "code_verifier": code_verifier,
        }
        if extra_params:
            data.update(extra_params)

        with httpx.Client(timeout=self.config.request_timeout) as client:
            if self.config.client_secret:
                resp = client.post(
                    self.token_endpoint,
                    data=data,
                    auth=(self.config.client_id, self.config.client_secret),
                )
            else:
                data["client_id"] = self.config.client_id
                resp = client.post(self.token_endpoint, data=data)
            if resp.status_code != 200:
                err_text = resp.text.lower()
                if "pkce" in err_text or "code verifier" in err_text or "code_verifier" in err_text:
                    raise InvalidCodeVerifierError(
                        f"PKCE code_verifier verification failed: {resp.text}"
                    )
                raise OIDCError(
                    status_code=resp.status_code,
                    detail=f"Token exchange failed with HTTP {resp.status_code}: {resp.text}",
                )
            return resp.json()

    async def aexchange_code(
        self,
        code: str,
        transaction_or_verifier: Union[OIDCTransaction, str],
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Asynchronously exchange authorization code for tokens using PKCE code_verifier."""
        if isinstance(transaction_or_verifier, OIDCTransaction):
            code_verifier = transaction_or_verifier.code_verifier
        else:
            code_verifier = transaction_or_verifier

        if not code_verifier or not isinstance(code_verifier, str) or not code_verifier.strip():
            raise InvalidCodeVerifierError("Missing or invalid PKCE code_verifier")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.config.redirect_uri,
            "code_verifier": code_verifier,
        }
        if extra_params:
            data.update(extra_params)

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            if self.config.client_secret:
                resp = await client.post(
                    self.token_endpoint,
                    data=data,
                    auth=(self.config.client_id, self.config.client_secret),
                )
            else:
                data["client_id"] = self.config.client_id
                resp = await client.post(self.token_endpoint, data=data)
            if resp.status_code != 200:
                err_text = resp.text.lower()
                if "pkce" in err_text or "code verifier" in err_text or "code_verifier" in err_text:
                    raise InvalidCodeVerifierError(
                        f"PKCE code_verifier verification failed: {resp.text}"
                    )
                raise OIDCError(
                    status_code=resp.status_code,
                    detail=f"Token exchange failed with HTTP {resp.status_code}: {resp.text}",
                )
            return resp.json()

    def validate_id_token(
        self,
        id_token: str,
        nonce: Optional[str] = None,
        jwk_set: Optional[PyJWKSet] = None,
    ) -> dict[str, Any]:
        """Cryptographically validate ID token against provider JWKS.

        Validates:
        1. Signature verification against JWKS public key.
        2. Issuer matches config.issuer.
        3. Audience matches config.client_id.
        4. Expiration timestamp (exp > current_time).
        5. Nonce matches transaction nonce (rejects mismatch with HTTP 401).
        """
        try:
            unverified_header = jwt.get_unverified_header(id_token)
        except Exception as exc:
            raise TokenValidationError(f"Invalid ID token header: {exc}") from exc

        alg = unverified_header.get("alg")
        if not alg or alg.lower() == "none":
            raise TokenValidationError("ID token must specify a cryptographic algorithm")

        kid = unverified_header.get("kid")
        keys = jwk_set or self.get_jwks()

        key: Any = None
        if kid:
            try:
                key = keys[kid].key
            except KeyError:
                # Key might have been rotated; attempt refresh once
                keys = self.get_jwks(force_refresh=True)
                try:
                    key = keys[kid].key
                except KeyError:
                    raise TokenValidationError(f"Signing key '{kid}' not found in provider JWKS")
        elif len(keys.keys) == 1:
            key = keys.keys[0].key
        else:
            raise TokenValidationError("Unable to determine signing key: missing 'kid' in token header")

        try:
            claims = jwt.decode(
                id_token,
                key=key,
                algorithms=[alg],
                audience=self.config.client_id,
                issuer=self.config.issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenValidationError(f"ID token has expired: {exc}") from exc
        except jwt.InvalidSignatureError as exc:
            raise TokenValidationError(f"ID token signature verification failed: {exc}") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenValidationError(f"ID token issuer mismatch: {exc}") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenValidationError(f"ID token audience mismatch: {exc}") from exc
        except jwt.PyJWTError as exc:
            raise TokenValidationError(f"ID token validation failed: {exc}") from exc

        if nonce is not None:
            token_nonce = claims.get("nonce")
            if not token_nonce or token_nonce != nonce:
                raise InvalidNonceError(
                    f"ID token nonce '{token_nonce}' does not match initiated request nonce '{nonce}'"
                )

        return claims

    async def avalidate_id_token(
        self,
        id_token: str,
        nonce: Optional[str] = None,
    ) -> dict[str, Any]:
        """Asynchronously cryptographically validate ID token against provider JWKS."""
        jwk_set = await self.aget_jwks()
        return self.validate_id_token(id_token=id_token, nonce=nonce, jwk_set=jwk_set)

    def claims_to_identity(self, claims: dict[str, Any]) -> Identity:
        """Convert validated ID token claims into domain Identity model using configured groups_claim."""
        return extract_identity_from_claims(claims, groups_claim=self.config.groups_claim)

    def process_callback(
        self,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> tuple[Identity, dict[str, Any]]:
        """Complete callback processing: state validation, code exchange, ID token validation."""
        transaction = self.validate_state(state)
        tokens = self.exchange_code(
            code=code,
            transaction_or_verifier=transaction,
            redirect_uri=redirect_uri,
            extra_params=extra_params,
        )
        id_token = tokens.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenValidationError("Token response missing 'id_token'")

        claims = self.validate_id_token(id_token=id_token, nonce=transaction.nonce)
        identity = self.claims_to_identity(claims)
        return identity, tokens

    async def aprocess_callback(
        self,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> tuple[Identity, dict[str, Any]]:
        """Asynchronously complete callback processing."""
        transaction = self.validate_state(state)
        tokens = await self.aexchange_code(
            code=code,
            transaction_or_verifier=transaction,
            redirect_uri=redirect_uri,
            extra_params=extra_params,
        )
        id_token = tokens.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenValidationError("Token response missing 'id_token'")

        claims = await self.avalidate_id_token(id_token=id_token, nonce=transaction.nonce)
        identity = self.claims_to_identity(claims)
        return identity, tokens

    def authenticate_user(
        self,
        username: str,
        password: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> tuple[Identity, dict[str, Any]]:
        """Authenticate user using Resource Owner Password Credentials grant.

        Fetches tokens, cryptographically validates the ID token, and extracts the domain Identity.
        """
        data = {
            "grant_type": "password",
            "client_id": self.config.client_id,
            "username": username,
            "scope": scope or self.config.scope,
        }
        if password:
            data["password"] = password

        with httpx.Client(timeout=self.config.request_timeout) as client:
            if self.config.client_secret:
                resp = client.post(
                    self.token_endpoint,
                    data=data,
                    auth=(self.config.client_id, self.config.client_secret),
                )
            else:
                resp = client.post(self.token_endpoint, data=data)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=resp.status_code,
                    detail=f"User authentication failed with HTTP {resp.status_code}: {resp.text}",
                )
            tokens = resp.json()

        id_token = tokens.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenValidationError("Token response missing 'id_token'")

        claims = self.validate_id_token(id_token=id_token)
        identity = self.claims_to_identity(claims)
        return identity, tokens

    async def aauthenticate_user(
        self,
        username: str,
        password: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> tuple[Identity, dict[str, Any]]:
        """Asynchronously authenticate user using Resource Owner Password Credentials grant."""
        data = {
            "grant_type": "password",
            "client_id": self.config.client_id,
            "username": username,
            "scope": scope or self.config.scope,
        }
        if password:
            data["password"] = password

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            if self.config.client_secret:
                resp = await client.post(
                    self.token_endpoint,
                    data=data,
                    auth=(self.config.client_id, self.config.client_secret),
                )
            else:
                resp = await client.post(self.token_endpoint, data=data)
            if resp.status_code != 200:
                raise OIDCError(
                    status_code=resp.status_code,
                    detail=f"User authentication failed with HTTP {resp.status_code}: {resp.text}",
                )
            tokens = resp.json()

        id_token = tokens.get("id_token")
        if not id_token or not isinstance(id_token, str):
            raise TokenValidationError("Token response missing 'id_token'")

        claims = await self.avalidate_id_token(id_token=id_token)
        identity = self.claims_to_identity(claims)
        return identity, tokens


def resolve_claim_path(claims: dict[str, Any], path: str) -> Any:
    """Extract a claim value from a nested or flat claim path.

    Supports flat keys (e.g. 'groups') and dotted paths (e.g. 'realm_access.roles').
    """
    if path in claims:
        return claims[path]
    parts = path.split(".")
    curr: Any = claims
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


def extract_identity_from_claims(
    claims: dict[str, Any],
    groups_claim: str = "groups",
) -> Identity:
    """Convert validated ID token claims into typed domain Identity model.

    Identity Origin Integrity Invariant:
    This function expects cryptographically verified token claims or authenticated IdP payloads.
    It extracts standard identity claims (sub, email, name) and resolves group memberships
    from the configured group claim path (defaulting cleanly to an empty list when absent).
    """
    subject = claims.get("sub")
    if not subject or not str(subject).strip():
        raise TokenValidationError("ID token claims missing required 'sub' claim")
    subject = str(subject)

    email = claims.get("email")
    if not email or not str(email).strip():
        email = claims.get("preferred_username") or f"{subject}@local"
    email = str(email)

    name = claims.get("name")
    if name is not None:
        name = str(name)

    raw_groups = resolve_claim_path(claims, groups_claim)
    if raw_groups is None and groups_claim == "groups":
        raw_groups = claims.get("roles")

    if raw_groups is None:
        groups: list[str] = []
    elif isinstance(raw_groups, list):
        groups = [str(g) for g in raw_groups if g is not None]
    elif isinstance(raw_groups, (tuple, set)):
        groups = [str(g) for g in raw_groups if g is not None]
    elif isinstance(raw_groups, str):
        if not raw_groups.strip():
            groups = []
        elif "," in raw_groups:
            groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
        else:
            groups = [raw_groups.strip()]
    else:
        groups = []

    return Identity(subject=subject, email=email, name=name, groups=groups)


def claims_to_identity(
    claims: dict[str, Any],
    groups_claim: str = "groups",
) -> Identity:
    """Convenience alias for extract_identity_from_claims."""
    return extract_identity_from_claims(claims, groups_claim=groups_claim)


@dataclass
class SessionRecord:
    """Server-side session record holding authenticated identity and lifetime metadata."""

    session_id: str
    identity: Identity
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    last_accessed: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired past its TTL."""
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at


class OIDCAuthAdapter:
    """Hexagonal AuthPort adapter using OIDCClient with robust browser session management."""

    client: OIDCClient
    session_cookie_name: str
    cookie_secure: bool
    cookie_samesite: Literal["lax", "strict", "none"]
    cookie_path: str
    cookie_domain: Optional[str]
    session_lifetime: float
    sessions: dict[str, Any]

    def __init__(
        self,
        client: OIDCClient,
        session_cookie_name: str = "bdinvite_session",
        cookie_secure: bool = False,
        cookie_samesite: Literal["lax", "strict", "none"] = "lax",
        cookie_path: str = "/",
        cookie_domain: Optional[str] = None,
        session_lifetime: float = 86400.0,
        sessions: Optional[dict[str, Any]] = None,
    ) -> None:
        self.client = client
        self.session_cookie_name = session_cookie_name
        self.cookie_secure = cookie_secure
        self.cookie_samesite = cookie_samesite
        self.cookie_path = cookie_path
        self.cookie_domain = cookie_domain
        self.session_lifetime = session_lifetime
        self.sessions: dict[str, Any] = sessions if sessions is not None else {}

    def extract_session_id(self, request: Request) -> Optional[str]:
        """Safely extract and sanitize session identifier from cookies or headers.

        Rejects malformed, tampered, or overly long inputs without throwing exceptions.
        """
        raw_id = (
            request.cookies.get(self.session_cookie_name)
            or request.cookies.get("session_id")
            or request.headers.get("X-Session-ID")
        )
        if not raw_id or not isinstance(raw_id, str):
            return None
        raw_id = raw_id.strip()
        if not raw_id or len(raw_id) > 256:
            return None

        # Disallow control characters, newlines, null bytes, quotes, semicolons
        import string

        allowed = set(string.ascii_letters + string.digits + "-_.~+")
        if not set(raw_id).issubset(allowed):
            return None

        return raw_id

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve and validate session from storage. Returns None if absent or expired."""
        if not session_id or session_id not in self.sessions:
            return None

        entry = self.sessions[session_id]
        if isinstance(entry, Identity):
            # Compatibility with direct Identity assignments
            now = time.time()
            return SessionRecord(
                session_id=session_id,
                identity=entry,
                created_at=now,
                expires_at=now + self.session_lifetime,
                last_accessed=now,
            )

        if isinstance(entry, SessionRecord):
            if entry.is_expired:
                self.revoke_session(session_id)
                return None
            return entry

        return None

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session from storage."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def create_anonymous_session(self) -> str:
        """Create a pre-authentication session identifier (for tracking or CSRF)."""
        return secrets.token_urlsafe(32)

    def establish_session(
        self,
        identity: Identity,
        pre_auth_session_id: Optional[str] = None,
        ttl: Optional[float] = None,
    ) -> str:
        """Register a verified Identity and return a fresh new session ID.

        Session Fixation Barrier:
        Always generates a fresh, cryptographically secure session identifier.
        If a pre-authentication session identifier is provided or existed, it is
        explicitly invalidated and NEVER reused or promoted into an authenticated session.
        """
        if pre_auth_session_id:
            self.revoke_session(pre_auth_session_id)

        new_session_id = secrets.token_urlsafe(32)
        while new_session_id == pre_auth_session_id or new_session_id in self.sessions:
            new_session_id = secrets.token_urlsafe(32)

        lifetime = ttl if ttl is not None else self.session_lifetime
        now = time.time()
        record = SessionRecord(
            session_id=new_session_id,
            identity=identity,
            created_at=now,
            expires_at=now + lifetime if lifetime > 0 else 0.0,
            last_accessed=now,
        )
        self.sessions[new_session_id] = record
        return new_session_id

    def set_session_cookie(
        self,
        response: Response,
        session_id: str,
        max_age: Optional[int] = None,
    ) -> None:
        """Set session cookie with HttpOnly=True and configured security attributes."""
        lifetime = max_age if max_age is not None else int(self.session_lifetime)
        response.set_cookie(
            key=self.session_cookie_name,
            value=session_id,
            max_age=lifetime,
            expires=lifetime,
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,  # Mandatory Security Invariant: JS cannot access session identifier
            samesite=self.cookie_samesite,
        )
        if self.session_cookie_name != "session_id":
            response.delete_cookie(
                key="session_id",
                path=self.cookie_path,
                domain=self.cookie_domain,
                secure=self.cookie_secure,
                httponly=True,
                samesite=self.cookie_samesite,
            )

    def clear_session_cookie(self, response: Response) -> None:
        """Clear browser session cookies by setting Max-Age=0."""
        response.delete_cookie(
            key=self.session_cookie_name,
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite=self.cookie_samesite,
        )
        if self.session_cookie_name != "session_id":
            response.delete_cookie(
                key="session_id",
                path=self.cookie_path,
                domain=self.cookie_domain,
                secure=self.cookie_secure,
                httponly=True,
                samesite=self.cookie_samesite,
            )

    def current_identity(self, request: Request) -> Optional[Identity]:
        """Extract and return verified Identity.

        Identity Origin Integrity Invariant:
        Identities are NEVER derived from unvalidated request-controlled headers
        (such as X-User, X-Email, etc.). Identities are ONLY returned from
        cryptographically validated sessions or verified Bearer ID tokens.
        """
        session_id = self.extract_session_id(request)
        if session_id:
            record = self.get_session(session_id)
            if record is not None:
                record.last_accessed = time.time()
                return record.identity

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                claims = self.client.validate_id_token(token)
                return self.client.claims_to_identity(claims)
            except Exception:
                return None

        return None

    def login(self, request: Request) -> Response:
        """Handle or initiate the authentication flow (redirecting to IdP)."""
        auth_url, _ = self.client.create_authorization_url()
        return RedirectResponse(url=auth_url, status_code=302)

    def logout(
        self,
        request: Request,
        response: Optional[Response] = None,
        redirect_target: Optional[str] = None,
    ) -> Response:
        """Terminate the active session and clear client cookies."""
        session_id = self.extract_session_id(request)
        if session_id:
            self.revoke_session(session_id)

        target = redirect_target or self.client.end_session_endpoint or "/"
        resp = response if response is not None else RedirectResponse(url=target, status_code=302)
        self.clear_session_cookie(resp)
        return resp

    def handle_callback(
        self,
        code: str,
        state: str,
        response: Optional[Response] = None,
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
        request: Optional[Request] = None,
        pre_auth_session_id: Optional[str] = None,
    ) -> tuple[Identity, str]:
        """Authenticate user from callback, establish session with fixation barrier, and return Identity and session_id."""
        identity, _ = self.client.process_callback(
            code=code,
            state=state,
            redirect_uri=redirect_uri,
            extra_params=extra_params,
        )
        if pre_auth_session_id is None and request is not None:
            pre_auth_session_id = self.extract_session_id(request)

        session_id = self.establish_session(
            identity=identity,
            pre_auth_session_id=pre_auth_session_id,
        )
        if response is not None:
            self.set_session_cookie(response, session_id)
        return identity, session_id

    async def ahandle_callback(
        self,
        code: str,
        state: str,
        response: Optional[Response] = None,
        redirect_uri: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
        request: Optional[Request] = None,
        pre_auth_session_id: Optional[str] = None,
    ) -> tuple[Identity, str]:
        """Asynchronously authenticate user from callback, establish session with fixation barrier, and return Identity and session_id."""
        identity, _ = await self.client.aprocess_callback(
            code=code,
            state=state,
            redirect_uri=redirect_uri,
            extra_params=extra_params,
        )
        if pre_auth_session_id is None and request is not None:
            pre_auth_session_id = self.extract_session_id(request)

        session_id = self.establish_session(
            identity=identity,
            pre_auth_session_id=pre_auth_session_id,
        )
        if response is not None:
            self.set_session_cookie(response, session_id)
        return identity, session_id

    def authenticate_and_establish_session(
        self,
        username: str,
        password: Optional[str] = None,
        scope: Optional[str] = None,
        pre_auth_session_id: Optional[str] = None,
        response: Optional[Response] = None,
    ) -> tuple[Identity, str]:
        """Authenticate user with password grant and establish session with fixation barrier."""
        identity, _ = self.client.authenticate_user(username=username, password=password, scope=scope)
        session_id = self.establish_session(identity, pre_auth_session_id=pre_auth_session_id)
        if response is not None:
            self.set_session_cookie(response, session_id)
        return identity, session_id

    async def aauthenticate_and_establish_session(
        self,
        username: str,
        password: Optional[str] = None,
        scope: Optional[str] = None,
        pre_auth_session_id: Optional[str] = None,
        response: Optional[Response] = None,
    ) -> tuple[Identity, str]:
        """Asynchronously authenticate user with password grant and establish session with fixation barrier."""
        identity, _ = await self.client.aauthenticate_user(username=username, password=password, scope=scope)
        session_id = self.establish_session(identity, pre_auth_session_id=pre_auth_session_id)
        if response is not None:
            self.set_session_cookie(response, session_id)
        return identity, session_id
