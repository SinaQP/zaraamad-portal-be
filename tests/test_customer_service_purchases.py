from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    CUSTOMER_ACCESS_DENIED,
    CUSTOMER_SERVICE_CONFIG_NOT_PURCHASABLE,
    DUPLICATE_CUSTOMER_SERVICE_PURCHASE_SELECTION,
)
from app.modules.customers.schemas import Customer
from app.modules.users.schemas import User
from tests.auth_utils import token_for_mobile


def _create_customer_entity(
    db_session: Session,
    *,
    name: str,
    grade: int = 1,
) -> Customer:
    customer = Customer(
        name=name,
        grade=grade,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _create_user(
    db_session: Session,
    *,
    full_name: str,
    mobile: str,
    role: UserRole,
    customer_id: int | None,
) -> User:
    user = User(
        full_name=full_name,
        mobile=mobile,
        role=role,
        customer_id=customer_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_admin(db_session: Session) -> User:
    return _create_user(
        db_session=db_session,
        full_name="Main Admin",
        mobile="09120000000",
        role=UserRole.ADMIN,
        customer_id=None,
    )


def _login(client: TestClient, mobile: str) -> str:
    del client
    return token_for_mobile(mobile)


def _headers_for_mobile(client: TestClient, mobile: str) -> dict[str, str]:
    token = _login(client=client, mobile=mobile)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    return _headers_for_mobile(client=client, mobile=admin.mobile)


def _create_service_project(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    sort_order: int,
) -> int:
    response = client.post(
        "/service-projects",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} project",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_service_group(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    sort_order: int,
) -> int:
    response = client.post(
        "/service-groups",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} group",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_service(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_id: int,
    group_id: int,
    name: str,
    sort_order: int,
) -> int:
    response = client.post(
        "/services",
        headers=headers,
        json={
            "project_id": project_id,
            "group_id": group_id,
            "name": name,
            "description": f"{name} service",
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_customer_service_configs(
    client: TestClient,
    headers: dict[str, str],
    *,
    customer_id: int,
    service_rows: list[dict[str, int | bool | str | None]],
) -> list[dict]:
    response = client.put(
        f"/customers/{customer_id}/services",
        headers=headers,
        json={"items": service_rows},
    )
    assert response.status_code == 200
    return response.json()


def test_customer_user_can_select_customer_service_configs_and_store_purchase(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(
        db_session=db_session,
        name="Tehran Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Customer User",
        mobile="09121112233",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    project_id = _create_service_project(
        client=client,
        headers=admin_headers,
        name="Security Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=admin_headers,
        name="Security Group",
        sort_order=1,
    )
    camera_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Camera Monitoring",
        sort_order=1,
    )
    guard_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Guard Patrol",
        sort_order=2,
    )

    config_rows = _create_customer_service_configs(
        client=client,
        headers=admin_headers,
        customer_id=customer.id,
        service_rows=[
            {
                "service_id": camera_service_id,
                "is_enabled": True,
                "sale_price": 500,
                "support_price": 50,
                "notes": "Camera package",
            },
            {
                "service_id": guard_service_id,
                "is_enabled": True,
                "sale_price": 700,
                "support_price": 0,
                "notes": "Guard package",
            },
        ],
    )

    config_list_response = client.get(
        f"/customers/{customer.id}/services",
        headers=customer_headers,
    )
    assert config_list_response.status_code == 200
    assert config_list_response.headers["X-Total-Count"] == "2"

    purchase_response = client.post(
        f"/customers/{customer.id}/service-purchases",
        headers=customer_headers,
        json={
            "notes": "Initial customer purchase",
            "items": [
                {"customer_service_config_id": config_rows[0]["id"]},
                {"customer_service_config_id": config_rows[1]["id"]},
            ],
        },
    )
    assert purchase_response.status_code == 201
    purchase_data = purchase_response.json()
    assert purchase_data["customer_id"] == customer.id
    assert purchase_data["created_by_user_id"] == customer_user.id
    assert purchase_data["selected_count"] == 2
    assert purchase_data["sale_total"] == 1200
    assert purchase_data["support_total"] == 50
    assert purchase_data["grand_total"] == 1250
    assert [item["service_name"] for item in purchase_data["items"]] == [
        "Camera Monitoring",
        "Guard Patrol",
    ]

    purchase_id = purchase_data["id"]
    detail_response = client.get(
        f"/customer-service-purchases/{purchase_id}",
        headers=customer_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["grand_total"] == 1250


def test_customer_scope_is_enforced_for_purchase_and_customer_service_list(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer_one = _create_customer_entity(
        db_session=db_session,
        name="Customer One",
    )
    customer_two = _create_customer_entity(
        db_session=db_session,
        name="Customer Two",
    )
    customer_one_user = _create_user(
        db_session=db_session,
        full_name="Customer One User",
        mobile="09123334455",
        role=UserRole.CUSTOMER,
        customer_id=customer_one.id,
    )
    customer_two_user = _create_user(
        db_session=db_session,
        full_name="Customer Two User",
        mobile="09124445566",
        role=UserRole.CUSTOMER,
        customer_id=customer_two.id,
    )
    customer_one_headers = _headers_for_mobile(client=client, mobile=customer_one_user.mobile)
    customer_two_headers = _headers_for_mobile(client=client, mobile=customer_two_user.mobile)

    project_id = _create_service_project(
        client=client,
        headers=admin_headers,
        name="Infra Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=admin_headers,
        name="Infra Group",
        sort_order=1,
    )
    service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Fiber Upgrade",
        sort_order=1,
    )
    config_rows = _create_customer_service_configs(
        client=client,
        headers=admin_headers,
        customer_id=customer_one.id,
        service_rows=[
            {
                "service_id": service_id,
                "is_enabled": True,
                "sale_price": 1000,
                "support_price": 100,
                "notes": "Fiber",
            }
        ],
    )
    purchase_response = client.post(
        f"/customers/{customer_one.id}/service-purchases",
        headers=customer_one_headers,
        json={
            "notes": "Customer one purchase",
            "items": [
                {"customer_service_config_id": config_rows[0]["id"]},
            ],
        },
    )
    assert purchase_response.status_code == 201
    purchase_id = purchase_response.json()["id"]

    foreign_list_response = client.get(
        f"/customers/{customer_one.id}/services",
        headers=customer_two_headers,
    )
    assert foreign_list_response.status_code == 403
    assert foreign_list_response.json()["message"] == CUSTOMER_ACCESS_DENIED

    foreign_purchase_response = client.get(
        f"/customer-service-purchases/{purchase_id}",
        headers=customer_two_headers,
    )
    assert foreign_purchase_response.status_code == 403
    assert foreign_purchase_response.json()["message"] == CUSTOMER_ACCESS_DENIED


def test_admin_can_update_and_deactivate_customer_service_purchase(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(
        db_session=db_session,
        name="Mashhad Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Mashhad User",
        mobile="09125556677",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    project_id = _create_service_project(
        client=client,
        headers=admin_headers,
        name="Ops Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=admin_headers,
        name="Ops Group",
        sort_order=1,
    )
    first_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Access Control",
        sort_order=1,
    )
    second_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Alarm",
        sort_order=2,
    )
    third_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Monitoring",
        sort_order=3,
    )
    config_rows = _create_customer_service_configs(
        client=client,
        headers=admin_headers,
        customer_id=customer.id,
        service_rows=[
            {
                "service_id": first_service_id,
                "is_enabled": True,
                "sale_price": 400,
                "support_price": 40,
                "notes": "A",
            },
            {
                "service_id": second_service_id,
                "is_enabled": True,
                "sale_price": 500,
                "support_price": 50,
                "notes": "B",
            },
                {
                    "service_id": third_service_id,
                    "is_enabled": True,
                    "sale_price": 600,
                    "support_price": 0,
                    "notes": "C",
                },
            ],
        )
    create_response = client.post(
        f"/customers/{customer.id}/service-purchases",
        headers=customer_headers,
        json={
            "notes": "Draft",
            "items": [
                {"customer_service_config_id": config_rows[0]["id"]},
                {"customer_service_config_id": config_rows[1]["id"]},
            ],
        },
    )
    assert create_response.status_code == 201
    purchase_id = create_response.json()["id"]

    update_response = client.patch(
        f"/customer-service-purchases/{purchase_id}",
        headers=admin_headers,
        json={
            "notes": "Updated draft",
            "items": [
                {"customer_service_config_id": config_rows[1]["id"]},
                {"customer_service_config_id": config_rows[2]["id"]},
            ],
        },
    )
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["notes"] == "Updated draft"
    assert update_data["selected_count"] == 2
    assert update_data["sale_total"] == 1100
    assert update_data["support_total"] == 50
    assert update_data["grand_total"] == 1150

    delete_response = client.delete(
        f"/customer-service-purchases/{purchase_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False

    missing_active_detail = client.get(
        f"/customer-service-purchases/{purchase_id}",
        headers=admin_headers,
    )
    assert missing_active_detail.status_code == 404

    inactive_list_response = client.get(
        f"/customers/{customer.id}/service-purchases",
        headers=admin_headers,
        params={"is_active": "false"},
    )
    assert inactive_list_response.status_code == 200
    assert inactive_list_response.headers["X-Total-Count"] == "1"
    assert inactive_list_response.json()["items"][0]["is_active"] is False


def test_purchase_payload_rejects_duplicate_and_disabled_customer_service_configs(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(
        db_session=db_session,
        name="Qom Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Qom User",
        mobile="09126667788",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    project_id = _create_service_project(
        client=client,
        headers=admin_headers,
        name="Support Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=admin_headers,
        name="Support Group",
        sort_order=1,
    )
    enabled_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Hotline",
        sort_order=1,
    )
    disabled_service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="On-site Support",
        sort_order=2,
    )
    config_rows = _create_customer_service_configs(
        client=client,
        headers=admin_headers,
        customer_id=customer.id,
        service_rows=[
            {
                "service_id": enabled_service_id,
                "is_enabled": True,
                "sale_price": 300,
                "support_price": 30,
                "notes": "Enabled",
            },
            {
                "service_id": disabled_service_id,
                "is_enabled": False,
                "sale_price": 600,
                "support_price": 60,
                "notes": "Disabled",
            },
        ],
    )

    duplicate_response = client.post(
        f"/customers/{customer.id}/service-purchases",
        headers=customer_headers,
        json={
            "items": [
                {"customer_service_config_id": config_rows[0]["id"]},
                {"customer_service_config_id": config_rows[0]["id"]},
            ]
        },
    )
    assert duplicate_response.status_code == 422
    assert duplicate_response.json()["message"] == DUPLICATE_CUSTOMER_SERVICE_PURCHASE_SELECTION

    disabled_response = client.post(
        f"/customers/{customer.id}/service-purchases",
        headers=customer_headers,
        json={
            "items": [
                {"customer_service_config_id": config_rows[1]["id"]},
            ]
        },
    )
    assert disabled_response.status_code == 422
    assert disabled_response.json()["message"] == CUSTOMER_SERVICE_CONFIG_NOT_PURCHASABLE
