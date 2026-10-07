import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .identity import Identity


@dataclass
class SessionData:
    """Represents an application-level browser session."""

    session_id: str
    identity: Identity | None = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Return True if session has a verified identity."""
        return self.identity is not None

    def is_expired(self, current_time: float | None = None) -> bool:
        """Check whether the session has passed its expiration timestamp."""
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at


@runtime_checkable
class SessionStore(Protocol):
    """Protocol defining the storage contract for browser session lifecycle."""

    def create_session(
        self,
        identity: Identity | None = None,
        max_age_seconds: int = 86400,
        pre_auth_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionData:
        """Create a fresh session. If pre_auth_session_id is provided, invalidate it (Session Fixation Protection)."""
        ...

    def get_session(self, session_id: str) -> SessionData | None:
        """Retrieve a session by its identifier. Returns None if absent or expired."""
        ...

    def delete_session(self, session_id: str) -> bool:
        """Explicitly revoke a session from storage."""
        ...

    def prune_expired(self) -> int:
        """Purge all expired sessions from storage."""
        ...

    def clear(self) -> None:
        """Purge all sessions (utility for tests and lifecycle resets)."""
        ...


class InMemorySessionStore:
    """Thread-safe in-memory session store implementing SessionStore protocol."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        identity: Identity | None = None,
        max_age_seconds: int = 86400,
        pre_auth_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionData:
        """Create a brand new session, enforcing the Session Fixation Barrier."""
        with self._lock:
            # Session Fixation Barrier: invalidate existing pre-auth session
            if pre_auth_session_id:
                self._sessions.pop(pre_auth_session_id, None)

            now = time.time()
            expires_at = now + max_age_seconds

            # Generate fresh, unguessable cryptographic token
            while True:
                new_session_id = secrets.token_urlsafe(32)
                if (
                    new_session_id != pre_auth_session_id
                    and new_session_id not in self._sessions
                ):
                    break

            session = SessionData(
                session_id=new_session_id,
                identity=identity,
                created_at=now,
                expires_at=expires_at,
                metadata=metadata or {},
            )
            self._sessions[new_session_id] = session
            return session

    def get_session(self, session_id: str) -> SessionData | None:
        """Fetch session, automatically purging if expired."""
        if not session_id or not isinstance(session_id, str):
            return None

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired():
                self._sessions.pop(session_id, None)
                return None
            return session

    def delete_session(self, session_id: str) -> bool:
        """Revoke session from storage."""
        if not session_id or not isinstance(session_id, str):
            return False

        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def prune_expired(self) -> int:
        """Purge all expired sessions."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, s in self._sessions.items() if s.is_expired(now)]
            for k in expired_keys:
                self._sessions.pop(k, None)
            return len(expired_keys)

    def clear(self) -> None:
        """Reset storage."""
        with self._lock:
            self._sessions.clear()


def sign_session_cookie(session_id: str, secret_key: str) -> str:
    """Sign session_id with HMAC-SHA256 to detect any client-side tampering."""
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")
    mac = hmac.new(
        secret_key.encode("utf-8"),
        session_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{session_id}.{mac}"


def unsign_session_cookie(cookie_val: str | None, secret_key: str) -> str | None:
    """Verify HMAC-SHA256 signature and return verified session_id, or None if tampered/invalid."""
    if not cookie_val or not isinstance(cookie_val, str) or not cookie_val.strip():
        return None
    if "." not in cookie_val:
        return None
    parts = cookie_val.rsplit(".", 1)
    if len(parts) != 2:
        return None
    session_id, signature = parts
    if not session_id or not signature:
        return None

    expected_mac = hmac.new(
        secret_key.encode("utf-8"),
        session_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_mac):
        return None
    return session_id


__all__ = [
    "InMemorySessionStore",
    "SessionData",
    "SessionStore",
    "sign_session_cookie",
    "unsign_session_cookie",
]
