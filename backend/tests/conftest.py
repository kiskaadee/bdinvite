import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.config import seed_default_config

# Shared in-memory SQLite for testing via StaticPool
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_default_config(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_test_session(
    subject: str = "admin-001",
    email: str = "admin@example.com",
    groups: list[str] | None = None,
) -> tuple[str, str]:
    """Helper to create a valid signed session cookie for testing."""
    from app.auth import Identity, get_auth_adapter, sign_session_cookie

    if groups is None:
        groups = ["bdinvite_admins"]
    adapter = get_auth_adapter()
    identity = Identity(
        subject=subject,
        email=email,
        groups=groups,
    )
    session = adapter.session_store.create_session(identity=identity)
    signed_cookie = sign_session_cookie(session.session_id, adapter.secret_key)
    return adapter.session_cookie_name, signed_cookie


def login_client(
    client: TestClient,
    subject: str = "admin-001",
    email: str = "admin@example.com",
    groups: list[str] | None = None,
) -> TestClient:
    """Sets a valid session cookie on client for an identity with the given groups."""
    cookie_name, cookie_value = create_test_session(
        subject=subject,
        email=email,
        groups=groups,
    )
    client.cookies.set(cookie_name, cookie_value)
    return client


@pytest.fixture(scope="function")
def admin_client(client: TestClient) -> TestClient:
    login_client(client, groups=["bdinvite_admins"])
    return client


@pytest.fixture(scope="function")
def guest_client(client: TestClient) -> TestClient:
    login_client(client, subject="guest-001", email="guest@example.com", groups=["guests"])
    return client

