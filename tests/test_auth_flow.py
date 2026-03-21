from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    INVALID_CREDENTIALS,
    INVALID_IRANIAN_MOBILE,
    OTP_DELIVERY_FAILED,
    OTP_INVALID,
    USER_NOT_FOUND_OR_INACTIVE,
    VALIDATION_ERROR_MESSAGE,
)
from app.common.services.otp_provider import OTPProvider, OTPProviderDeliveryError, get_otp_provider
from app.main import app
from app.modules.auth.schemas import OTPCode
from app.modules.users.schemas import User


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


def _create_customer(db_session: Session) -> User:
    customer = User(
        full_name="Password User",
        mobile="09123334455",
        role=UserRole.ADMIN,
        customer_id=None,
        is_active=True,
        password="legacy-password",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


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
    assert response.json()["detail"] == USER_NOT_FOUND_OR_INACTIVE
    assert response.json()["developer_message"] == "Active user record for the provided identifier was not found."


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
    assert verify_data["user"]["role"] == UserRole.ADMIN.value

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {verify_data['access_token']}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["id"] == admin.id
    assert me_data["mobile"] == admin.mobile


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
    assert second_verify.json()["detail"] == OTP_INVALID
    assert second_verify.json()["developer_message"] == "Provided OTP code is invalid or already consumed."


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
    assert response.json()["detail"] == OTP_DELIVERY_FAILED
    assert response.json()["developer_message"] == "OTP delivery provider failed."
    assert db_session.query(OTPCode).count() == 0


def test_invalid_mobile_returns_persian_validation_message(client: TestClient) -> None:
    response = client.post(
        "/auth/request-otp",
        json={"mobile": "0912"},
    )

    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["developer_message"] == "Request validation failed."
    assert response.json()["detail"][0]["msg"] == INVALID_IRANIAN_MOBILE
    assert "body.mobile" in response.json()["detail"][0]["developer_message"]


def test_password_login_upgrades_legacy_plaintext_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_customer(db_session=db_session)

    response = client.post(
        "/auth/login",
        json={"mobile": user.mobile, "password": "legacy-password"},
    )

    assert response.status_code == 200
    db_session.refresh(user)
    assert user.password is not None
    assert user.password != "legacy-password"
    assert user.password.startswith("pbkdf2_sha256$")


def test_password_login_rejects_invalid_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_customer(db_session=db_session)

    response = client.post(
        "/auth/login",
        json={"mobile": user.mobile, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_CREDENTIALS
    assert response.json()["detail"] == INVALID_CREDENTIALS

