import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.modules.customers.portal_bridge_pilot_service as pilot_service_module
from app.common.config import get_settings
from app.common.enums import UserRole
from app.common.messages import CUSTOMER_ACCESS_DENIED
from app.modules.customers.schemas import Customer, CustomerBridgeConfig
from app.modules.users.schemas import User
from tests.auth_utils import auth_headers_for_user


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status = 200

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _create_customer(db_session: Session, *, name: str) -> Customer:
    customer = Customer(
        name=name,
        grade=1,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _create_bridge_config(
    db_session: Session,
    *,
    customer_id: int,
    base_url: str,
    is_enabled: bool = True,
    api_key: str | None = None,
) -> CustomerBridgeConfig:
    bridge_config = CustomerBridgeConfig(
        customer_id=customer_id,
        bridge_base_url=base_url,
        bridge_is_enabled=is_enabled,
        bridge_api_key=api_key,
    )
    db_session.add(bridge_config)
    db_session.commit()
    db_session.refresh(bridge_config)
    return bridge_config


def _create_customer_user(db_session: Session, *, customer_id: int, mobile: str) -> User:
    user = User(
        full_name="Customer User",
        mobile=mobile,
        role=UserRole.CUSTOMER,
        customer_id=customer_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_customer_bridge_pilot_proxy_uses_bridge_base_url_and_minimal_portal_claims(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PORTAL_BRIDGE_JWT_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nmock-key\\n-----END PRIVATE KEY-----",
    )
    monkeypatch.setenv("PORTAL_BRIDGE_JWT_ISSUER", "zaravand-portal")
    monkeypatch.setenv("PORTAL_BRIDGE_JWT_TTL_SECONDS", "120")
    get_settings.cache_clear()

    customer = _create_customer(db_session=db_session, name="Pilot Customer")
    _create_bridge_config(
        db_session=db_session,
        customer_id=customer.id,
        base_url="https://customer-one.internal/",
        api_key=None,
    )
    user = _create_customer_user(
        db_session=db_session,
        customer_id=customer.id,
        mobile="09126667788",
    )

    captured_signing: dict[str, Any] = {}
    captured_upstream: dict[str, Any] = {}

    def fake_encode(payload: dict[str, Any], key: str, algorithm: str) -> str:
        captured_signing["payload"] = payload
        captured_signing["key"] = key
        captured_signing["algorithm"] = algorithm
        return "signed-portal-token"

    def fake_urlopen(request, timeout):  # noqa: ANN001
        captured_upstream["url"] = request.full_url
        captured_upstream["headers"] = {
            key.lower(): value for key, value in request.header_items()
        }
        captured_upstream["timeout"] = timeout
        return FakeHTTPResponse(
            {
                "ok": True,
                "service": "zaraamad-be",
                "source": "portal-jwt",
            }
        )

    monkeypatch.setattr(pilot_service_module.jwt, "encode", fake_encode)
    monkeypatch.setattr(pilot_service_module, "urlopen", fake_urlopen)

    response = client.get(
        f"/customers/{customer.id}/bridge/pilot/ping",
        headers={
            **auth_headers_for_user(user),
            "X-Correlation-ID": "pilot-corr-001",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "zaraamad-be",
        "source": "portal-jwt",
    }
    assert captured_upstream["url"] == "https://customer-one.internal/internal/portal/pilot/ping"
    assert captured_upstream["timeout"] == 10
    assert captured_upstream["headers"]["accept"] == "application/json"
    assert captured_upstream["headers"]["authorization"] == "Bearer signed-portal-token"
    assert captured_upstream["headers"]["x-correlation-id"] == "pilot-corr-001"

    claims = captured_signing["payload"]
    assert captured_signing["algorithm"] == "RS256"
    assert "\n" in captured_signing["key"]
    assert claims["iss"] == "zaravand-portal"
    assert claims["sub"] == f"user:{user.id}"
    assert claims["bridge_id"] == str(customer.id)
    assert claims["customer_id"] == str(customer.id)
    assert isinstance(claims["jti"], str) and claims["jti"]
    assert claims["exp"] > claims["iat"]
    get_settings.cache_clear()


def test_customer_bridge_pilot_proxy_enforces_customer_scope(
    client: TestClient,
    db_session: Session,
) -> None:
    customer_one = _create_customer(db_session=db_session, name="Customer One")
    customer_two = _create_customer(db_session=db_session, name="Customer Two")
    _create_bridge_config(
        db_session=db_session,
        customer_id=customer_two.id,
        base_url="https://customer-two.internal",
    )
    user = _create_customer_user(
        db_session=db_session,
        customer_id=customer_one.id,
        mobile="09126667789",
    )

    response = client.get(
        f"/customers/{customer_two.id}/bridge/pilot/ping",
        headers=auth_headers_for_user(user),
    )

    assert response.status_code == 403
    assert response.json()["message"] == CUSTOMER_ACCESS_DENIED
