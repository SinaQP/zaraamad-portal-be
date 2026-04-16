from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    MISSING_AUTH_TOKEN,
    TICKET_ACCESS_DENIED,
    TICKET_INVALID_STATUS_TRANSITION,
    TICKET_NOT_FOUND,
)
from app.modules.customers.schemas import Customer
from app.modules.users.schemas import User
from tests.auth_utils import token_for_mobile


def _create_customer(
    db_session: Session,
    *,
    name: str,
    grade: int = 1,
) -> Customer:
    customer = Customer(name=name, grade=grade, is_active=True)
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


def _headers_for_mobile(client: TestClient, mobile: str) -> dict[str, str]:
    del client
    token = token_for_mobile(mobile)
    return {"Authorization": f"Bearer {token}"}


def test_ticket_create_get_list_and_update_success(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer(db_session, name="Ticket Customer")
    creator = _create_user(
        db_session,
        full_name="Ticket Creator",
        mobile="09129990001",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    headers = _headers_for_mobile(client, creator.mobile)

    create_response = client.post(
        "/tickets",
        headers=headers,
        json={
            "title": "اختلال در گزارش‌گیری",
            "description": "گزارش ماهانه دانلود نمی‌شود.",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201
    created_ticket = create_response.json()
    ticket_id = created_ticket["id"]
    assert created_ticket["created_by_user_id"] == creator.id
    assert created_ticket["status"] == "open"
    assert created_ticket["priority"] == "high"

    get_response = client.get(f"/tickets/{ticket_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == ticket_id

    list_response = client.get(
        "/tickets",
        headers=headers,
        params={"status": "open", "priority": "high"},
    )
    assert list_response.status_code == 200
    assert list_response.headers["X-Total-Count"] == "1"
    assert len(list_response.json()["items"]) == 1

    update_response = client.patch(
        f"/tickets/{ticket_id}",
        headers=headers,
        json={"title": "اختلال در گزارش‌گیری (به‌روزرسانی)", "priority": "urgent"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "اختلال در گزارش‌گیری (به‌روزرسانی)"
    assert update_response.json()["priority"] == "urgent"


def test_admin_can_change_status_assign_and_deactivate_ticket(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer(db_session, name="Admin Ticket Customer")
    creator = _create_user(
        db_session,
        full_name="Normal User",
        mobile="09129990002",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    assignee = _create_user(
        db_session,
        full_name="Support Agent",
        mobile="09129990003",
        role=UserRole.ADMIN,
        customer_id=None,
    )
    admin = _create_user(
        db_session,
        full_name="Main Admin",
        mobile="09129990004",
        role=UserRole.ADMIN,
        customer_id=None,
    )

    creator_headers = _headers_for_mobile(client, creator.mobile)
    admin_headers = _headers_for_mobile(client, admin.mobile)

    create_response = client.post(
        "/tickets",
        headers=creator_headers,
        json={"title": "ارجاع تیکت", "description": "نیاز به ارجاع", "priority": "medium"},
    )
    assert create_response.status_code == 201
    ticket_id = create_response.json()["id"]

    assign_response = client.patch(
        f"/tickets/{ticket_id}/assign",
        headers=admin_headers,
        json={"assigned_to_user_id": assignee.id},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assigned_to_user_id"] == assignee.id

    status_response = client.patch(
        f"/tickets/{ticket_id}/status",
        headers=admin_headers,
        json={"status": "in_progress"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "in_progress"
    assert status_response.json()["status_changed_by_user_id"] == admin.id

    deactivate_response = client.delete(
        f"/tickets/{ticket_id}",
        headers=admin_headers,
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    get_after_deactivate = client.get(f"/tickets/{ticket_id}", headers=admin_headers)
    assert get_after_deactivate.status_code == 404
    assert get_after_deactivate.json()["message"] == TICKET_NOT_FOUND


def test_ticket_forbidden_and_unauthorized_paths(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer(db_session, name="Forbidden Ticket Customer")
    owner = _create_user(
        db_session,
        full_name="Owner User",
        mobile="09129990005",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    other_user = _create_user(
        db_session,
        full_name="Other User",
        mobile="09129990006",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    admin = _create_user(
        db_session,
        full_name="Admin User",
        mobile="09129990007",
        role=UserRole.ADMIN,
        customer_id=None,
    )
    owner_headers = _headers_for_mobile(client, owner.mobile)
    other_headers = _headers_for_mobile(client, other_user.mobile)
    admin_headers = _headers_for_mobile(client, admin.mobile)

    unauthorized_create = client.post("/tickets", json={"title": "بدون احراز هویت", "priority": "low"})
    assert unauthorized_create.status_code == 401
    assert unauthorized_create.json()["message"] == MISSING_AUTH_TOKEN

    create_response = client.post(
        "/tickets",
        headers=owner_headers,
        json={"title": "تیکت محرمانه", "description": "فقط مالک", "priority": "low"},
    )
    assert create_response.status_code == 201
    ticket_id = create_response.json()["id"]

    forbidden_get = client.get(f"/tickets/{ticket_id}", headers=other_headers)
    assert forbidden_get.status_code == 403
    assert forbidden_get.json()["message"] == TICKET_ACCESS_DENIED

    forbidden_assign = client.patch(
        f"/tickets/{ticket_id}/assign",
        headers=other_headers,
        json={"assigned_to_user_id": owner.id},
    )
    assert forbidden_assign.status_code == 403
    assert forbidden_assign.json()["message"] == ADMIN_ACCESS_REQUIRED

    not_found = client.get("/tickets/99999", headers=admin_headers)
    assert not_found.status_code == 404
    assert not_found.json()["message"] == TICKET_NOT_FOUND


def test_ticket_invalid_status_transition_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer(db_session, name="Status Transition Customer")
    creator = _create_user(
        db_session,
        full_name="Status Creator",
        mobile="09129990008",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    admin = _create_user(
        db_session,
        full_name="Status Admin",
        mobile="09129990009",
        role=UserRole.ADMIN,
        customer_id=None,
    )
    creator_headers = _headers_for_mobile(client, creator.mobile)
    admin_headers = _headers_for_mobile(client, admin.mobile)

    create_response = client.post(
        "/tickets",
        headers=creator_headers,
        json={"title": "تغییر وضعیت", "priority": "medium"},
    )
    assert create_response.status_code == 201
    ticket_id = create_response.json()["id"]

    close_response = client.patch(
        f"/tickets/{ticket_id}/status",
        headers=admin_headers,
        json={"status": "closed"},
    )
    assert close_response.status_code == 200

    invalid_transition_response = client.patch(
        f"/tickets/{ticket_id}/status",
        headers=admin_headers,
        json={"status": "open"},
    )
    assert invalid_transition_response.status_code == 422
    assert invalid_transition_response.json()["message"] == TICKET_INVALID_STATUS_TRANSITION


def test_admin_ticket_list_supports_status_and_priority_filters(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer(db_session, name="Filter Ticket Customer")
    creator = _create_user(
        db_session,
        full_name="Filter Creator",
        mobile="09129990010",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    admin = _create_user(
        db_session,
        full_name="Filter Admin",
        mobile="09129990011",
        role=UserRole.ADMIN,
        customer_id=None,
    )
    creator_headers = _headers_for_mobile(client, creator.mobile)
    admin_headers = _headers_for_mobile(client, admin.mobile)

    first_ticket = client.post(
        "/tickets",
        headers=creator_headers,
        json={"title": "اولویت بالا", "priority": "high"},
    )
    assert first_ticket.status_code == 201
    first_ticket_id = first_ticket.json()["id"]

    second_ticket = client.post(
        "/tickets",
        headers=creator_headers,
        json={"title": "اولویت پایین", "priority": "low"},
    )
    assert second_ticket.status_code == 201

    status_change = client.patch(
        f"/tickets/{first_ticket_id}/status",
        headers=admin_headers,
        json={"status": "in_progress"},
    )
    assert status_change.status_code == 200

    filtered = client.get(
        "/tickets",
        headers=admin_headers,
        params={"status": "in_progress", "priority": "high"},
    )
    assert filtered.status_code == 200
    assert filtered.headers["X-Total-Count"] == "1"
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["items"][0]["title"] == "اولویت بالا"

