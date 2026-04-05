from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.formatters.jalali_datetime import gregorian_datetime_to_jalali_datetime_string
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    FEEDBACK_CONTENT_REQUIRED,
    MISSING_AUTH_TOKEN,
    VALIDATION_ERROR_MESSAGE,
)
from app.modules.customers.schemas import Customer
from app.modules.feedback.schemas import Feedback
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


def test_customer_user_can_create_feedback_and_admin_can_list_it(
    client: TestClient,
    db_session: Session,
) -> None:
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
    admin = _create_admin(db_session=db_session)
    customer_headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)
    admin_headers = _headers_for_mobile(client=client, mobile=admin.mobile)

    create_response = client.post(
        "/feedback",
        headers=customer_headers,
        json={
            "message": "Need faster onboarding guides.",
            "selected_options": ["Fast support", "Analytics"],
        },
    )

    assert create_response.status_code == 201
    create_data = create_response.json()
    assert create_data["user_id"] == customer_user.id
    assert create_data["user_full_name"] == customer_user.full_name
    assert create_data["user_mobile"] == customer_user.mobile
    assert create_data["message"] == "Need faster onboarding guides."
    assert create_data["selected_options"] == ["Fast support", "Analytics"]
    stored_feedback = db_session.get(Feedback, create_data["id"])
    assert stored_feedback is not None
    assert create_data["created_at"] == gregorian_datetime_to_jalali_datetime_string(stored_feedback.created_at)

    list_response = client.get(
        "/feedback",
        headers=admin_headers,
    )

    assert list_response.status_code == 200
    assert list_response.headers["X-Total-Count"] == "1"
    list_data = list_response.json()
    assert list_data["items"][0]["user_id"] == customer_user.id
    assert list_data["items"][0]["selected_options"] == ["Fast support", "Analytics"]
    assert list_data["items"][0]["created_at"] == gregorian_datetime_to_jalali_datetime_string(
        stored_feedback.created_at
    )

    forbidden_response = client.get(
        "/feedback",
        headers=customer_headers,
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["message"] == ADMIN_ACCESS_REQUIRED


def test_feedback_payload_normalizes_whitespace_and_duplicate_options(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer_entity(
        db_session=db_session,
        name="Mashhad Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Mashhad User",
        mobile="09123334455",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    response = client.post(
        "/feedback",
        headers=headers,
        json={
            "message": "   ",
            "selected_options": [
                " Fast support ",
                "Fast support",
                "   ",
                " Daily reports  ",
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] is None
    assert data["selected_options"] == ["Fast support", "Daily reports"]


def test_feedback_requires_message_or_selected_options(
    client: TestClient,
    db_session: Session,
) -> None:
    customer = _create_customer_entity(
        db_session=db_session,
        name="Qom Customer",
    )
    customer_user = _create_user(
        db_session=db_session,
        full_name="Qom User",
        mobile="09124445566",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
    )
    headers = _headers_for_mobile(client=client, mobile=customer_user.mobile)

    response = client.post(
        "/feedback",
        headers=headers,
        json={
            "message": "   ",
            "selected_options": ["   ", ""],
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == VALIDATION_ERROR_MESSAGE
    assert response.json()["detail"][0]["msg"] == FEEDBACK_CONTENT_REQUIRED


def test_feedback_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/feedback",
        json={
            "message": "Need better exports.",
            "selected_options": ["Exports"],
        },
    )

    assert response.status_code == 401
    assert response.json()["message"] == MISSING_AUTH_TOKEN
