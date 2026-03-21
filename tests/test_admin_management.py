from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    CUSTOMER_ID_REQUIRED,
    INVALID_CREDENTIALS,
    VALIDATION_ERROR_MESSAGE,
)
from app.modules.customers.schemas import Customer
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


def _login(client: TestClient, mobile: str) -> str:
    otp_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = otp_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def test_admin_can_manage_customers_and_users(client: TestClient, db_session: Session) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    customer_response = client.post(
        "/customers",
        headers=admin_headers,
        json={
            "name": "Tehran Customer",
            "manager_name": "Ali Rezaei",
            "grade": 1,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]
    assert customer_response.json()["manager_name"] == "Ali Rezaei"

    user_response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Customer One",
            "mobile": "09121112233",
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
        },
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    filtered_users_response = client.get(
        "/users",
        headers=admin_headers,
        params={
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
            "is_active": True,
        },
    )
    assert filtered_users_response.status_code == 200
    filtered_users = filtered_users_response.json()
    assert filtered_users["total_page"] == 1
    assert len(filtered_users["items"]) == 1
    assert filtered_users["items"][0]["id"] == user_id

    patch_response = client.patch(
        f"/users/{user_id}",
        headers=admin_headers,
        json={"full_name": "Customer One Updated"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["full_name"] == "Customer One Updated"

    update_customer_response = client.patch(
        f"/customers/{customer_id}",
        headers=admin_headers,
        json={"manager_name": "Sara Ahmadi"},
    )
    assert update_customer_response.status_code == 200
    assert update_customer_response.json()["manager_name"] == "Sara Ahmadi"

    deactivate_user_response = client.delete(f"/users/{user_id}", headers=admin_headers)
    assert deactivate_user_response.status_code == 200
    assert deactivate_user_response.json()["is_active"] is False

    deactivate_customer_response = client.delete(
        f"/customers/{customer_id}",
        headers=admin_headers,
    )
    assert deactivate_customer_response.status_code == 200
    assert deactivate_customer_response.json()["is_active"] is False


def test_admin_cannot_create_customer_without_customer_id(
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
            "role": UserRole.CUSTOMER.value,
            "customer_id": None,
        },
    )
    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["detail"][0]["msg"] == CUSTOMER_ID_REQUIRED
    assert response.json()["developer_message"] == "Request validation failed."


def test_admin_can_create_admin_without_customer_id(
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
            "full_name": "Second Admin",
            "mobile": "09127778899",
            "role": UserRole.ADMIN.value,
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == UserRole.ADMIN.value
    assert response.json()["customer_id"] is None


def test_users_list_supports_search_sort_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    customer_response = client.post(
        "/customers",
        headers=admin_headers,
        json={"name": "Search Customer", "grade": 2},
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    create_payloads = [
        {
            "full_name": "Alpha Customer",
            "mobile": "09121110001",
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
        },
        {
            "full_name": "Gamma Customer",
            "mobile": "09121110002",
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
        },
        {
            "full_name": "Beta Admin",
            "mobile": "09121110003",
            "role": UserRole.ADMIN.value,
        },
    ]
    for payload in create_payloads:
        response = client.post("/users", headers=admin_headers, json=payload)
        assert response.status_code == 201

    search_response = client.get(
        "/users",
        headers=admin_headers,
        params={"search": "alpha"},
    )
    assert search_response.status_code == 200
    search_items = search_response.json()
    assert search_items["total_page"] == 1
    assert len(search_items["items"]) == 1
    assert search_items["items"][0]["full_name"] == "Alpha Customer"
    assert search_response.headers["X-Total-Count"] == "1"

    paged_response = client.get(
        "/users",
        headers=admin_headers,
        params={
            "sort_by": "full_name",
            "sort_order": "asc",
            "page": 1,
            "page_size": 2,
        },
    )
    assert paged_response.status_code == 200
    paged_items = paged_response.json()
    assert paged_items["total_page"] == 2
    assert len(paged_items["items"]) == 2
    assert paged_items["items"][0]["full_name"] == "Alpha Customer"
    assert paged_items["items"][1]["full_name"] == "Beta Admin"
    assert paged_response.headers["X-Total-Count"] == "4"
    assert paged_response.headers["X-Page"] == "1"
    assert paged_response.headers["X-Page-Size"] == "2"
    assert paged_response.headers["X-Total-Pages"] == "2"


def test_customers_list_supports_search_sort_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    for payload in [
        {"name": "Alpha Customer", "manager_name": "Manager One", "grade": 1},
        {"name": "Gamma Customer", "manager_name": "Manager Three", "grade": 3},
        {"name": "Beta Customer", "manager_name": "Manager Two", "grade": 2},
    ]:
        response = client.post("/customers", headers=admin_headers, json=payload)
        assert response.status_code == 201

    search_response = client.get(
        "/customers",
        headers=admin_headers,
        params={"search": "manager two"},
    )
    assert search_response.status_code == 200
    search_items = search_response.json()
    assert search_items["total_page"] == 1
    assert len(search_items["items"]) == 1
    assert search_items["items"][0]["name"] == "Beta Customer"
    assert search_items["items"][0]["manager_name"] == "Manager Two"
    assert search_response.headers["X-Total-Count"] == "1"

    paged_response = client.get(
        "/customers",
        headers=admin_headers,
        params={
            "sort_by": "manager_name",
            "sort_order": "asc",
            "page": 2,
            "page_size": 2,
        },
    )
    assert paged_response.status_code == 200
    paged_items = paged_response.json()
    assert paged_items["total_page"] == 2
    assert len(paged_items["items"]) == 1
    assert paged_items["items"][0]["manager_name"] == "Manager Two"
    assert paged_response.headers["X-Total-Count"] == "3"
    assert paged_response.headers["X-Page"] == "2"
    assert paged_response.headers["X-Page-Size"] == "2"
    assert paged_response.headers["X-Total-Pages"] == "2"


def test_get_all_customers_returns_all_items_without_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    for payload in [
        {"name": "Alpha Customer", "manager_name": "Alpha Manager", "grade": 1},
        {"name": "Beta Customer", "manager_name": "Beta Manager", "grade": 2},
        {"name": "Gamma Customer", "manager_name": "Gamma Manager", "grade": 3},
    ]:
        response = client.post("/customers", headers=admin_headers, json=payload)
        assert response.status_code == 201

    response = client.get("/customers/all", headers=admin_headers)
    assert response.status_code == 200

    items = response.json()
    assert len(items) == 3
    assert [item["name"] for item in items] == [
        "Alpha Customer",
        "Beta Customer",
        "Gamma Customer",
    ]
    assert [item["manager_name"] for item in items] == [
        "Alpha Manager",
        "Beta Manager",
        "Gamma Manager",
    ]


def test_customer_cannot_access_admin_endpoints(client: TestClient, db_session: Session) -> None:
    customer = Customer(
        name="Qom Customer",
        grade=2,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    customer = User(
        full_name="Customer User",
        mobile="09123334455",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    customer_token = _login(client=client, mobile=customer.mobile)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    response = client.post(
        "/customers",
        headers=customer_headers,
        json={
            "name": "Should Fail",
            "grade": 3,
        },
    )
    assert response.status_code == 403
    assert response.json()["message"] == ADMIN_ACCESS_REQUIRED
    assert response.json()["detail"] == ADMIN_ACCESS_REQUIRED
    assert response.json()["developer_message"] == "Authenticated user does not have admin role."


def test_inactive_users_and_customers_are_hidden_from_get_apis(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    customer_response = client.post(
        "/customers",
        headers=admin_headers,
        json={
            "name": "Hidden Customer",
            "grade": 4,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    user_response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Hidden User",
            "mobile": "09125556677",
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
        },
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    assert client.delete(f"/users/{user_id}", headers=admin_headers).status_code == 200
    assert client.delete(f"/customers/{customer_id}", headers=admin_headers).status_code == 200

    users_response = client.get(
        "/users",
        headers=admin_headers,
        params={
            "role": UserRole.CUSTOMER.value,
            "customer_id": customer_id,
        },
    )
    assert users_response.status_code == 200
    assert users_response.headers["X-Total-Count"] == "0"
    assert users_response.json()["items"] == []

    user_detail_response = client.get(f"/users/{user_id}", headers=admin_headers)
    assert user_detail_response.status_code == 404

    customers_response = client.get(
        "/customers",
        headers=admin_headers,
        params={"search": "Hidden Customer"},
    )
    assert customers_response.status_code == 200
    assert customers_response.headers["X-Total-Count"] == "0"
    assert customers_response.json()["items"] == []

    all_customers_response = client.get("/customers/all", headers=admin_headers)
    assert all_customers_response.status_code == 200
    assert all_customers_response.json() == []

    customer_detail_response = client.get(f"/customers/{customer_id}", headers=admin_headers)
    assert customer_detail_response.status_code == 404

    customer_bridge_response = client.get(f"/customers/{customer_id}/bridge", headers=admin_headers)
    assert customer_bridge_response.status_code == 404


def test_admin_can_update_user_password_and_user_can_login_with_new_password(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Second Admin",
            "mobile": "09128889900",
            "role": UserRole.ADMIN.value,
            "password": "initial-password",
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    initial_login = client.post(
        "/auth/login",
        json={"mobile": "09128889900", "password": "initial-password"},
    )
    assert initial_login.status_code == 200

    update_response = client.patch(
        f"/users/{user_id}",
        headers=admin_headers,
        json={"password": "new-password"},
    )
    assert update_response.status_code == 200

    old_password_response = client.post(
        "/auth/login",
        json={"mobile": "09128889900", "password": "initial-password"},
    )
    assert old_password_response.status_code == 401
    assert old_password_response.json()["message"] == INVALID_CREDENTIALS

    new_password_response = client.post(
        "/auth/login",
        json={"mobile": "09128889900", "password": "new-password"},
    )
    assert new_password_response.status_code == 200


def test_empty_password_in_patch_does_not_clear_existing_user_password(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = _create_admin(db_session=db_session)
    admin_token = _login(client=client, mobile=admin.mobile)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "full_name": "Password User",
            "mobile": "09128889901",
            "role": UserRole.ADMIN.value,
            "password": "stable-password",
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_response = client.patch(
        f"/users/{user_id}",
        headers=admin_headers,
        json={"full_name": "Password User Updated", "password": ""},
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Password User Updated"

    login_response = client.post(
        "/auth/login",
        json={"mobile": "09128889901", "password": "stable-password"},
    )
    assert login_response.status_code == 200
