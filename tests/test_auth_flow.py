from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.enums import UserRole
from app.common.messages import (
    INVALID_AUTH_TOKEN,
    INVALID_CREDENTIALS,
    INVALID_IRANIAN_MOBILE,
    INVALID_TOKEN_TYPE,
    MISSING_AUTH_TOKEN,
    OTP_DELIVERY_FAILED,
    OTP_INVALID,
    USER_NOT_FOUND_OR_INACTIVE,
    VALIDATION_ERROR_MESSAGE,
)
from app.common.services.otp_provider import (
    OTPProvider,
    OTPProviderDeliveryError,
    get_otp_provider,
)
from app.main import app
from app.modules.auth.schemas import OTPCode
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


def _create_password_user(db_session: Session) -> User:
    user = User(
        full_name="Password User",
        mobile="09123334455",
        role=UserRole.ADMIN,
        customer_id=None,
        is_active=True,
        password="legacy-password",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class FailingOTPProvider(OTPProvider):
    def send_login_otp(self, mobile: str, otp_code: str):
        del mobile, otp_code
        raise OTPProviderDeliveryError()


def test_request_otp_for_unknown_user_returns_404(client: TestClient) -> None:
    response = client.post(
        "/auth/request-otp",
        json={"mobile": "09125554433"},
    )

    assert response.status_code == 404
    assert response.json()["message"] == USER_NOT_FOUND_OR_INACTIVE


def test_admin_can_login_with_otp_and_get_me(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)

    request_otp_response = client.post(
        "/auth/request-otp",
        json={"mobile": admin.mobile},
    )
    assert request_otp_response.status_code == 200
    request_data = request_otp_response.json()
    assert request_data["dev_otp"] is not None

    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": admin.mobile, "otp_code": request_data["dev_otp"]},
    )

    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert verify_data["token_type"] == "bearer"
    assert verify_data["user"]["id"] == admin.id
    assert verify_data["user"]["role"] == UserRole.ADMIN.value

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {verify_data['access_token']}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["user_id"] == str(admin.id)
    assert me_data["roles"] == ["Admin"]


def test_otp_is_single_use(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)

    request_otp_response = client.post(
        "/auth/request-otp",
        json={"mobile": admin.mobile},
    )
    otp_code = request_otp_response.json()["dev_otp"]

    first_verify = client.post(
        "/auth/verify-otp",
        json={"mobile": admin.mobile, "otp_code": otp_code},
    )
    assert first_verify.status_code == 200

    second_verify = client.post(
        "/auth/verify-otp",
        json={"mobile": admin.mobile, "otp_code": otp_code},
    )
    assert second_verify.status_code == 400
    assert second_verify.json()["message"] == OTP_INVALID


def test_failed_otp_delivery_rolls_back_persisted_code(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    app.dependency_overrides[get_otp_provider] = lambda: FailingOTPProvider()

    response = client.post(
        "/auth/request-otp",
        json={"mobile": admin.mobile},
    )

    assert response.status_code == 503
    assert response.json()["message"] == OTP_DELIVERY_FAILED
    assert db_session.query(OTPCode).count() == 0


def test_invalid_mobile_returns_validation_message(client: TestClient) -> None:
    response = client.post(
        "/auth/request-otp",
        json={"mobile": "0912"},
    )

    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["detail"][0]["msg"] == INVALID_IRANIAN_MOBILE


def test_password_login_upgrades_legacy_plaintext_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_password_user(db_session=db_session)

    response = client.post(
        "/auth/login",
        json={"mobile": user.mobile, "password": "legacy-password"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    db_session.refresh(user)
    assert user.password is not None
    assert user.password != "legacy-password"
    assert user.password.startswith("pbkdf2_sha256$")


def test_password_login_rejects_invalid_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_password_user(db_session=db_session)

    response = client.post(
        "/auth/login",
        json={"mobile": user.mobile, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_CREDENTIALS


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
