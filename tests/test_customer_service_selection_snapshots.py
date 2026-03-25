from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.formatters.jalali_datetime import gregorian_datetime_to_time_string
from app.common.messages import ADMIN_ACCESS_REQUIRED, CUSTOMER_ACCESS_DENIED
from app.modules.service_catalog import service as service_catalog_service_module
from app.modules.customers.schemas import Customer
from app.modules.service_catalog.schemas import CustomerServiceSelectionSnapshot
from app.modules.users.schemas import User


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
    request_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = request_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def _headers_for_mobile(client: TestClient, mobile: str) -> dict[str, str]:
    token = _login(client=client, mobile=mobile)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    return _headers_for_mobile(client=client, mobile=admin.mobile)


def _freeze_snapshot_date(
    monkeypatch,
    *,
    selected_at: date,
) -> None:
    monkeypatch.setattr(
        service_catalog_service_module,
        "get_current_snapshot_date",
        lambda: selected_at,
    )


def _set_snapshot_selected_at(
    db_session: Session,
    *,
    snapshot_id: int,
    selected_at: date,
) -> CustomerServiceSelectionSnapshot:
    snapshot = db_session.get(CustomerServiceSelectionSnapshot, snapshot_id)
    assert snapshot is not None
    snapshot.selected_at = selected_at
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


def _set_snapshot_created_at(
    db_session: Session,
    *,
    snapshot_id: int,
    created_at: datetime,
) -> CustomerServiceSelectionSnapshot:
    snapshot = db_session.get(CustomerServiceSelectionSnapshot, snapshot_id)
    assert snapshot is not None
    snapshot.created_at = created_at
    snapshot.updated_at = created_at
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


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


def test_customer_service_selection_snapshot_create_detail_and_payload_string_are_preserved(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _freeze_snapshot_date(monkeypatch, selected_at=date(2026, 3, 25))
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(
        db_session=db_session,
        name="Snapshot Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Snapshot User",
        mobile="09121110001",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    project_id = _create_service_project(
        client=client,
        headers=admin_headers,
        name="Snapshot Project",
        sort_order=1,
    )
    group_id = _create_service_group(
        client=client,
        headers=admin_headers,
        name="Snapshot Group",
        sort_order=1,
    )
    service_id = _create_service(
        client=client,
        headers=admin_headers,
        project_id=project_id,
        group_id=group_id,
        name="Snapshot Service",
        sort_order=1,
    )
    config_rows = _create_customer_service_configs(
        client=client,
        headers=admin_headers,
        customer_id=customer.id,
        service_rows=[
            {
                "service_id": service_id,
                "is_enabled": True,
                "sale_price": 500,
                "support_price": 50,
                "notes": "Original config",
            }
        ],
    )

    original_payload = (
        '{  "selected_config_ids" : ['
        f'{config_rows[0]["id"]}'
        '], "lines" : [ { "service_id" : '
        f"{service_id}"
        ', "service_name" : "Snapshot Service", "sale_price" : 500, "support_price" : 50 } ], '
        '"totals" : { "sale_total" : 500, "support_total" : 50, "grand_total" : 550 } }'
    )
    create_response = client.post(
        f"/customers/{customer.id}/service-selection-snapshots",
        headers=customer_headers,
        json={
            "customer_id": customer.id,
            "user_id": customer_user.id,
            "payload": original_payload,
        },
    )
    assert create_response.status_code == 201
    create_data = create_response.json()
    assert create_data["customer_id"] == customer.id
    assert create_data["user_id"] == customer_user.id
    assert create_data["date"] == "1405-01-05"
    assert create_data["payload"] == original_payload

    stored_snapshot = db_session.get(CustomerServiceSelectionSnapshot, create_data["id"])
    assert stored_snapshot is not None
    assert stored_snapshot.selected_at == date(2026, 3, 25)
    assert create_data["time"] == gregorian_datetime_to_time_string(stored_snapshot.created_at)
    assert stored_snapshot.payload == original_payload

    update_config_response = client.patch(
        f"/customer-service-configs/{config_rows[0]['id']}",
        headers=admin_headers,
        json={
            "sale_price": 700,
            "support_price": 70,
            "notes": "Updated config",
        },
    )
    assert update_config_response.status_code == 200

    detail_response = client.get(
        f"/customer-service-selection-snapshots/{create_data['id']}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["customer_id"] == customer.id
    assert detail_data["customer_name"] == customer.name
    assert detail_data["user_id"] == customer_user.id
    assert detail_data["user_name"] == customer_user.full_name
    assert detail_data["date"] == "1405-01-05"
    assert detail_data["time"] == gregorian_datetime_to_time_string(stored_snapshot.created_at)
    assert detail_data["payload"] == original_payload


def test_customer_service_selection_snapshot_accepts_unparsed_payload_strings(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _freeze_snapshot_date(monkeypatch, selected_at=date(2026, 3, 26))
    customer = _create_customer_entity(
        db_session=db_session,
        name="Unparsed Payload Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Unparsed Payload User",
        mobile="09121110006",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    raw_payload = "{selected_ids:[10,11],step:final}"
    response = client.post(
        f"/customers/{customer.id}/service-selection-snapshots",
        headers=customer_headers,
        json={
            "customer_id": customer.id,
            "user_id": customer_user.id,
            "payload": raw_payload,
        },
    )

    assert response.status_code == 201
    assert response.json()["payload"] == raw_payload


def test_admin_can_list_customer_service_selection_snapshots_with_filters_and_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = _admin_headers(client=client, db_session=db_session)
    customer = _create_customer_entity(
        db_session=db_session,
        name="List Customer",
    )
    first_user = _create_user(
        db_session=db_session,
        full_name="First Customer User",
        mobile="09121110002",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    second_user = _create_user(
        db_session=db_session,
        full_name="Second Customer User",
        mobile="09121110003",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )

    snapshot_payloads = [
        (
            first_user.id,
            date(2026, 3, 21),
            datetime(2026, 3, 21, 8, 15, 0),
            '{"step":"draft","selected_ids":[1]}',
            "1405-01-01",
            "08:15:00",
        ),
        (
            second_user.id,
            date(2026, 3, 22),
            datetime(2026, 3, 22, 9, 30, 45),
            '{"step":"review","selected_ids":[2]}',
            "1405-01-02",
            "09:30:45",
        ),
        (
            first_user.id,
            date(2026, 3, 23),
            datetime(2026, 3, 23, 10, 45, 12),
            '{"step":"final","selected_ids":[3]}',
            "1405-01-03",
            "10:45:12",
        ),
    ]
    for user_id, selected_at, created_at, payload, _jalali_date, _time in snapshot_payloads:
        response = client.post(
            f"/customers/{customer.id}/service-selection-snapshots",
            headers=admin_headers,
            json={
                "customer_id": customer.id,
                "user_id": user_id,
                "payload": payload,
            },
        )
        assert response.status_code == 201
        _set_snapshot_selected_at(
            db_session=db_session,
            snapshot_id=response.json()["id"],
            selected_at=selected_at,
        )
        _set_snapshot_created_at(
            db_session=db_session,
            snapshot_id=response.json()["id"],
            created_at=created_at,
        )

    first_page_response = client.get(
        f"/customers/{customer.id}/service-selection-snapshots",
        headers=admin_headers,
        params={"page": 1, "page_size": 1},
    )
    assert first_page_response.status_code == 200
    assert first_page_response.headers["X-Total-Count"] == "3"
    assert first_page_response.headers["X-Total-Pages"] == "3"
    first_page_data = first_page_response.json()
    assert first_page_data["total_page"] == 3
    assert len(first_page_data["items"]) == 1
    assert first_page_data["items"][0]["customer_id"] == customer.id
    assert first_page_data["items"][0]["customer_name"] == customer.name
    assert first_page_data["items"][0]["user_id"] == first_user.id
    assert first_page_data["items"][0]["user_name"] == first_user.full_name
    assert first_page_data["items"][0]["date"] == "1405-01-03"
    assert first_page_data["items"][0]["time"] == "10:45:12"
    assert first_page_data["items"][0]["payload"] == '{"step":"final","selected_ids":[3]}'

    filtered_response = client.get(
        f"/customers/{customer.id}/service-selection-snapshots",
        headers=admin_headers,
        params={
            "user_id": first_user.id,
            "from_date": "1405-01-02",
            "to_date": "1405-01-03",
        },
    )
    assert filtered_response.status_code == 200
    filtered_data = filtered_response.json()
    assert filtered_response.headers["X-Total-Count"] == "1"
    assert len(filtered_data["items"]) == 1
    assert filtered_data["items"][0]["user_id"] == first_user.id
    assert filtered_data["items"][0]["user_name"] == first_user.full_name
    assert filtered_data["items"][0]["customer_name"] == customer.name
    assert filtered_data["items"][0]["date"] == "1405-01-03"
    assert filtered_data["items"][0]["time"] == "10:45:12"


def test_customer_service_selection_snapshot_requires_all_post_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer_entity(
        db_session=db_session,
        name="Required Fields Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Required Fields User",
        mobile="09121110008",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    response = client.post(
        f"/customers/{customer.id}/service-selection-snapshots",
        headers=customer_headers,
        json={},
    )

    assert response.status_code == 422
    assert {item["field"] for item in response.json()["detail"]} == {
        "customer_id",
        "user_id",
        "payload",
    }


def test_customer_can_post_snapshot_but_get_endpoints_are_admin_only(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _freeze_snapshot_date(monkeypatch, selected_at=date(2026, 3, 27))
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
        mobile="09121110004",
        role=UserRole.CUSTOMER,
        customer_id=customer_one.id,
    )
    customer_two_user = _create_user(
        db_session=db_session,
        full_name="Customer Two User",
        mobile="09121110005",
        role=UserRole.CUSTOMER,
        customer_id=customer_two.id,
    )
    customer_one_headers = _headers_for_mobile(client=client, mobile=customer_one_user.mobile)
    customer_two_headers = _headers_for_mobile(client=client, mobile=customer_two_user.mobile)

    create_response = client.post(
        f"/customers/{customer_one.id}/service-selection-snapshots",
        headers=customer_one_headers,
        json={
            "customer_id": customer_one.id,
            "user_id": customer_one_user.id,
            "payload": '{"selected_ids":[10,11],"step":"final"}',
        },
    )
    assert create_response.status_code == 201
    snapshot_id = create_response.json()["id"]

    own_list_response = client.get(
        f"/customers/{customer_one.id}/service-selection-snapshots",
        headers=customer_one_headers,
    )
    assert own_list_response.status_code == 403
    assert own_list_response.json()["message"] == ADMIN_ACCESS_REQUIRED

    own_detail_response = client.get(
        f"/customer-service-selection-snapshots/{snapshot_id}",
        headers=customer_one_headers,
    )
    assert own_detail_response.status_code == 403
    assert own_detail_response.json()["message"] == ADMIN_ACCESS_REQUIRED

    foreign_post_response = client.post(
        f"/customers/{customer_one.id}/service-selection-snapshots",
        headers=customer_two_headers,
        json={
            "customer_id": customer_one.id,
            "user_id": customer_one_user.id,
            "payload": '{"selected_ids":[99],"step":"final"}',
        },
    )
    assert foreign_post_response.status_code == 403
    assert foreign_post_response.json()["message"] == CUSTOMER_ACCESS_DENIED

    admin_list_response = client.get(
        f"/customers/{customer_one.id}/service-selection-snapshots",
        headers=admin_headers,
    )
    assert admin_list_response.status_code == 200
    assert admin_list_response.json()["items"][0]["customer_name"] == customer_one.name
    assert admin_list_response.json()["items"][0]["user_name"] == customer_one_user.full_name

    admin_detail_response = client.get(
        f"/customer-service-selection-snapshots/{snapshot_id}",
        headers=admin_headers,
    )
    assert admin_detail_response.status_code == 200
    assert admin_detail_response.json()["customer_name"] == customer_one.name
    assert admin_detail_response.json()["user_name"] == customer_one_user.full_name
