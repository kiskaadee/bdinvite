"""Authentication package providing domain models, hexagonal ports, and OIDC client."""

from .oidc import (
    InvalidNonceError,
    InvalidStateError,
    OIDCAuthAdapter,
    OIDCClient,
    OIDCConfig,
    OIDCDiscovery,
    OIDCError,
    OIDCTransaction,
    TokenValidationError,
    claims_to_identity,
    extract_identity_from_claims,
    generate_code_challenge,
    generate_code_verifier,
    generate_nonce,
    generate_state,
    resolve_claim_path,
)
from .port import AuthPort, Identity

__all__ = [
    "AuthPort",
    "Identity",
    "InvalidNonceError",
    "InvalidStateError",
    "OIDCAuthAdapter",
    "OIDCClient",
    "OIDCConfig",
    "OIDCDiscovery",
    "OIDCError",
    "OIDCTransaction",
    "TokenValidationError",
    "claims_to_identity",
    "extract_identity_from_claims",
    "generate_code_challenge",
    "generate_code_verifier",
    "generate_nonce",
    "generate_state",
    "resolve_claim_path",
]
