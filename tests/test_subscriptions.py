from datetime import date

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.common.enums import SubscriptionMessageStatus, UserRole
from app.common.messages import (
    ACTIVE_SUBSCRIPTION_END_DATE_REQUIRED,
    ACTIVE_SUBSCRIPTION_NOT_FOUND,
    DUPLICATE_SUBSCRIPTION_MESSAGE_STATUS,
    INVALID_BRIDGE_KEY,
    ITEMS_MUST_NOT_BE_EMPTY,
    VALIDATION_ERROR_MESSAGE,
)
from app.main import app
from app.modules.subscriptions.schemas import Subscription, SubscriptionMessage
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


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    token = _login(client=client, mobile=admin.mobile)
    return {"Authorization": f"Bearer {token}"}


def _bridge_headers(correlation_id: str | None = None) -> dict[str, str]:
    headers = {"X-Bridge-Key": get_settings().bridge_api_key}
    if correlation_id is not None:
        headers["X-Correlation-ID"] = correlation_id
    return headers


def test_create_replace_subscription_with_normal_auth(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    first_response = client.post(
        "/sub/subscription/",
        headers=headers,
        json={"end_date": "2026-04-12"},
    )
    assert first_response.status_code == 201
    first_data = first_response.json()
    assert first_data["start_date"] == date.today().isoformat()
    assert first_data["end_date"] == "2026-04-12"
    assert first_data["grace_period_end_date"] is None
    assert first_data["is_active"] is True

    second_response = client.post(
        "/sub/subscription/",
        headers=headers,
        json={"end_date": "2026-05-12"},
    )
    assert second_response.status_code == 201
    second_data = second_response.json()
    assert second_data["id"] != first_data["id"]
    assert second_data["end_date"] == "2026-05-12"
    assert second_data["is_active"] is True

    subscriptions = list(
        db_session.scalars(select(Subscription).order_by(Subscription.id.asc())).all()
    )
    assert len(subscriptions) == 2
    assert subscriptions[0].is_active is False
    assert subscriptions[1].is_active is True


def test_get_active_subscription_with_normal_auth(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    create_response = client.post(
        "/sub/subscription/",
        headers=headers,
        json={"end_date": "2026-04-12"},
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    response = client.get("/sub/subscriptions/active/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_id
    assert data["end_date"] == "2026-04-12"
    assert data["is_active"] is True


def test_patch_active_subscription_with_normal_auth(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    create_response = client.post(
        "/sub/subscription/",
        headers=headers,
        json={"end_date": "2026-04-12"},
    )
    assert create_response.status_code == 201

    patch_response = client.patch(
        "/sub/subscriptions/active/",
        headers=headers,
        json={
            "end_date": "2026-04-20",
            "grace_period_end_date": "2026-04-25",
            "is_active": True,
        },
    )
    assert patch_response.status_code == 200
    patch_data = patch_response.json()
    assert patch_data["end_date"] == "2026-04-20"
    assert patch_data["grace_period_end_date"] == "2026-04-25"
    assert patch_data["is_active"] is True


def test_get_and_patch_subscription_messages_with_normal_auth(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    empty_response = client.get("/sub/subscriptions/messages/", headers=headers)
    assert empty_response.status_code == 200
    assert empty_response.json() == []

    patch_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=headers,
        json=[
            {
                "status": SubscriptionMessageStatus.EXPIRED.value,
                "message_template": "اشتراک شما {days} روز پیش منقضی شده است.",
            },
            {
                "status": SubscriptionMessageStatus.GRACE.value,
                "message_template": "اشتراک شما در دوره تنفس است.",
            },
        ],
    )
    assert patch_response.status_code == 200
    patch_data = patch_response.json()
    assert [item["status"] for item in patch_data] == [
        SubscriptionMessageStatus.EXPIRED.value,
        SubscriptionMessageStatus.GRACE.value,
    ]

    second_patch_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=headers,
        json=[
            {
                "status": SubscriptionMessageStatus.EXPIRED.value,
                "message_template": "اشتراک شما {days} روز است منقضی شده است.",
            },
            {
                "status": SubscriptionMessageStatus.NEAR_EXPIRY.value,
                "message_template": "اشتراک شما تا {days} روز دیگر منقضی می‌شود.",
            },
        ],
    )
    assert second_patch_response.status_code == 200

    list_response = client.get("/sub/subscriptions/messages/", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert [item["status"] for item in items] == [
        SubscriptionMessageStatus.EXPIRED.value,
        SubscriptionMessageStatus.GRACE.value,
        SubscriptionMessageStatus.NEAR_EXPIRY.value,
    ]
    assert items[0]["message_template"] == "اشتراک شما {days} روز است منقضی شده است."

    stored_messages = list(
        db_session.scalars(
            select(SubscriptionMessage).order_by(SubscriptionMessage.id.asc())
        ).all()
    )
    assert len(stored_messages) == 3


def test_same_subscription_urls_work_with_bridge_auth(
    client: TestClient,
    db_session: Session,
) -> None:
    del db_session
    create_response = client.post(
        "/sub/subscription/",
        headers=_bridge_headers(correlation_id="bridge-corr-create"),
        json={"end_date": "2026-06-01"},
    )
    assert create_response.status_code == 201
    assert create_response.headers["X-Correlation-ID"] == "bridge-corr-create"

    get_response = client.get(
        "/sub/subscriptions/active/",
        headers=_bridge_headers(correlation_id="bridge-corr-get"),
    )
    assert get_response.status_code == 200
    assert get_response.headers["X-Correlation-ID"] == "bridge-corr-get"
    assert get_response.json()["end_date"] == "2026-06-01"

    patch_messages_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=_bridge_headers(correlation_id="bridge-corr-messages"),
        json=[
            {
                "status": SubscriptionMessageStatus.EXPIRED.value,
                "message_template": "اشتراک شما منقضی شده است.",
            }
        ],
    )
    assert patch_messages_response.status_code == 200
    assert patch_messages_response.headers["X-Correlation-ID"] == "bridge-corr-messages"

    get_messages_response = client.get(
        "/sub/subscriptions/messages/",
        headers=_bridge_headers(),
    )
    assert get_messages_response.status_code == 200
    assert get_messages_response.json()[0]["status"] == SubscriptionMessageStatus.EXPIRED.value


def test_subscription_validation_failures(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)

    missing_active_response = client.get(
        "/sub/subscriptions/active/",
        headers=headers,
    )
    assert missing_active_response.status_code == 404
    assert missing_active_response.json()["message"] == ACTIVE_SUBSCRIPTION_NOT_FOUND

    create_on_patch_response = client.patch(
        "/sub/subscriptions/active/",
        headers=headers,
        json={"grace_period_end_date": "2026-04-25"},
    )
    assert create_on_patch_response.status_code == 422
    assert create_on_patch_response.json()["message"] == ACTIVE_SUBSCRIPTION_END_DATE_REQUIRED

    empty_messages_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=headers,
        json=[],
    )
    assert empty_messages_response.status_code == 422
    assert empty_messages_response.json()["message"] == ITEMS_MUST_NOT_BE_EMPTY

    duplicate_messages_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=headers,
        json=[
            {
                "status": SubscriptionMessageStatus.EXPIRED.value,
                "message_template": "A",
            },
            {
                "status": SubscriptionMessageStatus.EXPIRED.value,
                "message_template": "B",
            },
        ],
    )
    assert duplicate_messages_response.status_code == 422
    assert duplicate_messages_response.json()["message"] == DUPLICATE_SUBSCRIPTION_MESSAGE_STATUS

    invalid_status_response = client.patch(
        "/sub/subscriptions/messages/",
        headers=headers,
        json=[
            {
                "status": "invalid",
                "message_template": "A",
            }
        ],
    )
    assert invalid_status_response.status_code == 422
    assert invalid_status_response.json()["message"] == VALIDATION_ERROR_MESSAGE


def test_invalid_bridge_key_is_rejected_for_subscription_routes(
    client: TestClient,
) -> None:
    response = client.get(
        "/sub/subscriptions/messages/",
        headers={"X-Bridge-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["message"] == INVALID_BRIDGE_KEY


def test_subscription_routes_do_not_expose_duplicate_bridge_or_admin_paths() -> None:
    route_paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert "/sub/subscription/" in route_paths
    assert "/sub/subscriptions/active/" in route_paths
    assert "/sub/subscriptions/messages/" in route_paths
    assert "/bridge/subscription/" not in route_paths
    assert "/bridge/subscriptions/active/" not in route_paths
    assert "/bridge/subscriptions/messages/" not in route_paths
    assert "/admin/config/subscription/" not in route_paths
