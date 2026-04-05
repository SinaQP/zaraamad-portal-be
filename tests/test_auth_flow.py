from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.enums import UserRole
from app.common.messages import INVALID_AUTH_TOKEN, INVALID_TOKEN_TYPE, MISSING_AUTH_TOKEN
from app.modules.users.schemas import User
from tests.auth_utils import access_token_for_user, build_access_token


def _create_admin(db_session: Session) -> User:
    admin = User(
        full_name="Main Admin",
        mobile="09120000000",
        role=UserRole.ADMIN,
        customer_id=None,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_auth_me_returns_verified_jwt_context(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = access_token_for_user(
        admin,
        roles=["Admin", "Operator"],
        security_stamp="stamp-123",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(admin.id)
    assert data["sub"] == str(admin.id)
    assert data["roles"] == ["Admin", "Operator"]
    assert data["security_stamp"] == "stamp-123"
    assert data["raw_claims"]["iss"] == "zaraamad-django"
    assert data["raw_claims"]["token_type"] == "access"


def test_auth_me_uses_user_id_when_sub_is_missing(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = build_access_token(
        subject=str(admin.id),
        user_id="django-user-42",
        roles=["Admin"],
        include_sub=False,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "django-user-42"
    assert response.json()["sub"] is None


def test_auth_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["message"] == MISSING_AUTH_TOKEN


def test_auth_me_rejects_malformed_token(client: TestClient) -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_AUTH_TOKEN


def test_auth_me_rejects_invalid_signature(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        signing_key="wrong-signing-key",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_AUTH_TOKEN


def test_auth_me_rejects_expired_token(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        expires_delta=timedelta(seconds=-5),
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_AUTH_TOKEN


def test_auth_me_rejects_wrong_issuer(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        issuer="unexpected-issuer",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_AUTH_TOKEN


def test_auth_me_rejects_wrong_token_type(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        token_type="refresh",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_TOKEN_TYPE


def test_auth_me_verifies_audience_when_configured(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    admin = _create_admin(db_session=db_session)
    monkeypatch.setenv("JWT_AUDIENCE", "portal-ui")
    get_settings.cache_clear()
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        audience="portal-ui",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["raw_claims"]["aud"] == "portal-ui"


def test_auth_me_rejects_wrong_audience_when_configured(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    admin = _create_admin(db_session=db_session)
    monkeypatch.setenv("JWT_AUDIENCE", "portal-ui")
    get_settings.cache_clear()
    access_token = build_access_token(
        subject=str(admin.id),
        roles=["Admin"],
        audience="different-audience",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_AUTH_TOKEN
