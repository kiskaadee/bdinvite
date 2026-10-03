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


@pytest.fixture(scope="function")
def admin_identity():
    from app.auth import Identity

    return Identity(
        subject="admin-001",
        email="admin@example.com",
        name="Admin User",
        groups=["bdinvite_admins"],
    )


@pytest.fixture(scope="function")
def guest_identity():
    from app.auth import Identity

    return Identity(
        subject="guest-001",
        email="guest@example.com",
        name="Guest User",
        groups=["guests"],
    )


@pytest.fixture(scope="function")
def admin_session_cookie(admin_identity):
    from app.auth import get_auth_adapter

    adapter = get_auth_adapter()
    session_id = adapter.establish_session(admin_identity)
    return {adapter.session_cookie_name: session_id}


@pytest.fixture(scope="function")
def guest_session_cookie(guest_identity):
    from app.auth import get_auth_adapter

    adapter = get_auth_adapter()
    session_id = adapter.establish_session(guest_identity)
    return {adapter.session_cookie_name: session_id}


@pytest.fixture(scope="function")
def admin_client(db_session, admin_session_cookie):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        for k, v in admin_session_cookie.items():
            test_client.cookies.set(k, v)
        yield test_client
    app.dependency_overrides.clear()

