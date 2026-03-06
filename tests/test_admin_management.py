from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.modules.municipalities.schemas import Municipality
from app.modules.users.schemas import User


def _create_admin(db_session: Session) -> User:
    admin = User(
        full_name="Main Admin",
        mobile="09120000000",
        email="admin@example.com",
        role=UserRole.ADMIN,
        municipality_id=None,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _login(client: TestClient, mobile: str) -> str:
    otp_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = otp_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def test_admin_can_manage_municipalities_and_users(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    municipality_response = client.post(
        "/municipalities",
        headers=admin_headers,
        json={
            "name": "Tehran Municipality",
            "code": "THR-001",
            "province": "Tehran",
            "city": "Tehran",
        },
    )
    assert municipality_response.status_code == 201
    municipality_id = municipality_response.json()["id"]

    user_response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Customer One",
            "mobile": "09121112233",
            "email": "customer1@example.com",
            "role": UserRole.CUSTOMER.value,
            "municipality_id": municipality_id,
        },
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    filtered_users_response = client.get(
        "/users",
        headers=admin_headers,
        params={
            "role": UserRole.CUSTOMER.value,
            "municipality_id": municipality_id,
            "is_active": True,
        },
    )
    assert filtered_users_response.status_code == 200
    filtered_users = filtered_users_response.json()
    assert len(filtered_users) == 1
    assert filtered_users[0]["id"] == user_id

    patch_response = client.patch(
        f"/users/{user_id}",
        headers=admin_headers,
        json={"full_name": "Customer One Updated"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["full_name"] == "Customer One Updated"

    deactivate_user_response = client.delete(f"/users/{user_id}", headers=admin_headers)
    assert deactivate_user_response.status_code == 200
    assert deactivate_user_response.json()["is_active"] is False

    deactivate_municipality_response = client.delete(
        f"/municipalities/{municipality_id}",
        headers=admin_headers,
    )
    assert deactivate_municipality_response.status_code == 200
    assert deactivate_municipality_response.json()["is_active"] is False


def test_admin_cannot_create_customer_without_municipality(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Invalid Customer",
            "mobile": "09126667788",
            "email": "invalid@example.com",
            "role": UserRole.CUSTOMER.value,
            "municipality_id": None,
        },
    )
    assert response.status_code == 422


def test_customer_cannot_access_admin_endpoints(client: TestClient, db_session: Session) -> None:
    municipality = Municipality(
        name="Qom Municipality",
        code="QOM-001",
        province="Qom",
        city="Qom",
        is_active=True,
    )
    db_session.add(municipality)
    db_session.commit()
    db_session.refresh(municipality)

    customer = User(
        full_name="Customer User",
        mobile="09123334455",
        email="customer@example.com",
        role=UserRole.CUSTOMER,
        municipality_id=municipality.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    customer_token = _login(client=client, mobile=customer.mobile)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    response = client.post(
        "/municipalities",
        headers=customer_headers,
        json={
            "name": "Should Fail",
            "code": "FAIL-001",
            "province": "Tehran",
            "city": "Tehran",
        },
    )
    assert response.status_code == 403
