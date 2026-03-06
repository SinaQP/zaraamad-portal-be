from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.modules.municipalities.schemas import Municipality
from app.modules.users.schemas import User


def _create_municipality(db_session: Session) -> Municipality:
    municipality = Municipality(
        name="Tehran Municipality",
        code="THR-001",
        province="Tehran",
        city="Tehran",
        is_active=True,
    )
    db_session.add(municipality)
    db_session.commit()
    db_session.refresh(municipality)
    return municipality


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


def _create_customer(db_session: Session, municipality_id: int) -> User:
    customer = User(
        full_name="Customer One",
        mobile="09123334455",
        email="customer@example.com",
        role=UserRole.CUSTOMER,
        municipality_id=municipality_id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _login(client: TestClient, mobile: str) -> str:
    request_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = request_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    token = _login(client=client, mobile=admin.mobile)
    return {"Authorization": f"Bearer {token}"}


def _create_service(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.post(
        "/services",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} description",
            "sort_order": 10,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_service(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    response = client.post(
        "/services",
        headers=headers,
        json={
            "name": "Security Services",
            "description": "On-site security.",
            "sort_order": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Security Services"
    assert data["is_active"] is True


def test_update_service(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Support")

    response = client.patch(
        f"/services/{service_id}",
        headers=headers,
        json={"name": "Support Updated", "sort_order": 99},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Support Updated"
    assert data["sort_order"] == 99


def test_deactivate_service(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Renovation")

    response = client.delete(f"/services/{service_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_create_and_list_municipality_service_config(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Miscellaneous")

    upsert_response = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "unit_price": 4000000,
                    "notes": "Initial setup",
                }
            ]
        },
    )
    assert upsert_response.status_code == 200
    upsert_data = upsert_response.json()
    assert len(upsert_data) == 1
    assert upsert_data[0]["municipality_id"] == municipality.id
    assert upsert_data[0]["service_id"] == service_id

    list_response = client.get(f"/municipalities/{municipality.id}/services", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_bulk_upsert_municipality_service_configs_omitted_items_remain_unchanged(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)

    service_a = _create_service(client=client, headers=headers, name="Security")
    service_b = _create_service(client=client, headers=headers, name="Support")
    service_c = _create_service(client=client, headers=headers, name="Other")

    first_upsert = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_a,
                    "is_enabled": True,
                    "unit_price": 1000000,
                    "notes": "A1",
                },
                {
                    "service_id": service_b,
                    "is_enabled": True,
                    "unit_price": 2000000,
                    "notes": "B1",
                },
            ]
        },
    )
    assert first_upsert.status_code == 200

    second_upsert = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_a,
                    "is_enabled": True,
                    "unit_price": 1100000,
                    "notes": "A2",
                },
                {
                    "service_id": service_c,
                    "is_enabled": True,
                    "unit_price": 3000000,
                    "notes": "C1",
                },
            ]
        },
    )
    assert second_upsert.status_code == 200

    list_response = client.get(f"/municipalities/{municipality.id}/services", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 3

    item_map = {item["service_id"]: item for item in items}
    assert item_map[service_a]["unit_price"] == 1100000
    assert item_map[service_b]["unit_price"] == 2000000
    assert item_map[service_c]["unit_price"] == 3000000


def test_duplicate_service_id_in_bulk_payload_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Duplicate")

    response = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "unit_price": 1000,
                    "notes": None,
                },
                {
                    "service_id": service_id,
                    "is_enabled": False,
                    "unit_price": 1000,
                    "notes": None,
                },
            ]
        },
    )
    assert response.status_code == 422


def test_price_cannot_be_negative(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Negative Price")

    response = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "unit_price": -1,
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 422


def test_patch_single_municipality_service_config(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)
    service_id = _create_service(client=client, headers=headers, name="Patchable")

    create_response = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_id,
                    "is_enabled": True,
                    "unit_price": 1000,
                    "notes": "v1",
                }
            ]
        },
    )
    assert create_response.status_code == 200
    config_id = create_response.json()[0]["id"]

    patch_response = client.patch(
        f"/municipality-service-configs/{config_id}",
        headers=headers,
        json={
            "is_enabled": False,
            "unit_price": 2500,
            "notes": "v2",
        },
    )
    assert patch_response.status_code == 200
    patch_data = patch_response.json()
    assert patch_data["is_enabled"] is False
    assert patch_data["unit_price"] == 2500
    assert patch_data["notes"] == "v2"


def test_pricing_summary_returns_correct_totals_and_ignores_disabled(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    municipality = _create_municipality(db_session=db_session)

    service_monthly = _create_service(client=client, headers=headers, name="Monthly")
    service_yearly = _create_service(client=client, headers=headers, name="Yearly")
    service_one_time = _create_service(client=client, headers=headers, name="One Time")
    service_disabled = _create_service(client=client, headers=headers, name="Disabled")

    upsert_response = client.put(
        f"/municipalities/{municipality.id}/services",
        headers=headers,
        json={
            "items": [
                {
                    "service_id": service_monthly,
                    "is_enabled": True,
                    "unit_price": 1000,
                    "notes": None,
                },
                {
                    "service_id": service_yearly,
                    "is_enabled": True,
                    "unit_price": 2000,
                    "notes": None,
                },
                {
                    "service_id": service_one_time,
                    "is_enabled": True,
                    "unit_price": 3000,
                    "notes": None,
                },
                {
                    "service_id": service_disabled,
                    "is_enabled": False,
                    "unit_price": 999999,
                    "notes": None,
                },
            ]
        },
    )
    assert upsert_response.status_code == 200

    summary_response = client.get(
        f"/municipalities/{municipality.id}/pricing-summary",
        headers=headers,
    )
    assert summary_response.status_code == 200
    summary_data = summary_response.json()
    assert summary_data["totals"]["enabled_total"] == 6000
    assert summary_data["totals"]["configured_total"] == 1005999

    disabled_items = [item for item in summary_data["items"] if item["service_name"] == "Disabled"]
    assert len(disabled_items) == 1
    assert disabled_items[0]["is_enabled"] is False
    assert disabled_items[0]["line_total"] == 0


def test_admin_only_access_enforced_and_customer_denied(
    client: TestClient,
    db_session: Session,
) -> None:
    municipality = _create_municipality(db_session=db_session)
    customer = _create_customer(db_session=db_session, municipality_id=municipality.id)
    customer_token = _login(client=client, mobile=customer.mobile)

    unauthorized_response = client.post(
        "/services",
        json={
            "name": "Unauthorized",
            "description": None,
            "sort_order": 1,
        },
    )
    assert unauthorized_response.status_code == 401

    customer_response = client.post(
        "/services",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "name": "Denied",
            "description": None,
            "sort_order": 1,
        },
    )
    assert customer_response.status_code == 403
