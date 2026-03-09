from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.modules.users.schemas import User


def _create_admin(db_session: Session) -> User:
    admin = User(
        full_name="Main Admin",
        mobile="09120000000",
        role=UserRole.ADMIN,
        municipality_id=None,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_request_otp_for_unknown_user_returns_404(client: TestClient) -> None:
    response = client.post(
        "/auth/request-otp",
        json={"mobile": "09125554433"},
    )
    assert response.status_code == 404


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
