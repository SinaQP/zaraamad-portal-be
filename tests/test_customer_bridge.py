from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    CUSTOMER_BRIDGE_AUTH_FAILED,
    CUSTOMER_BRIDGE_NOT_CONFIGURED,
    CUSTOMER_BRIDGE_UNAVAILABLE,
)
from app.common.services.bridge_client import (
    BridgeClient,
    BridgeCapabilitiesResult,
    BridgeCapability,
    BridgeConnectionError,
    BridgeHealthResult,
    BridgeRequest,
    BridgeSubscriptionConfigResult,
    BridgeSubscriptionMessageResult,
    BridgeSubscriptionResult,
    BridgeUnauthorizedError,
    BridgeUnexpectedStatusError,
    get_bridge_client,
)
from app.main import app
from app.modules.users.schemas import User
from tests.auth_utils import token_for_mobile


class RecordingBridgeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[object, ...]] = []

    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        self.requests.append(("health", request))
        return BridgeHealthResult(
            status="ok",
            bridge_name="Tehran Support Bridge",
            bridge_version="1.0.0",
        )

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        self.requests.append(("capabilities", request))
        return BridgeCapabilitiesResult(
            bridge_name="Tehran Support Bridge",
            bridge_version="1.0.0",
            capabilities=[
                BridgeCapability(
                    code="support.health.read",
                    name="Read bridge health",
                    description="Allows support health checks.",
                ),
                BridgeCapability(
                    code="support.capabilities.read",
                    name="Read bridge capabilities",
                    description=None,
                ),
            ],
        )

    def get_active_subscription(self, request: BridgeRequest) -> BridgeSubscriptionResult:
        self.requests.append(("subscription", request))
        return self._build_subscription_result()

    def update_active_subscription(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionResult:
        self.requests.append(("subscription-update", request, payload))
        current = self._build_subscription_result()
        return BridgeSubscriptionResult(
            start_date=current.start_date,
            end_date=payload.get("end_date", current.end_date),
            grace_period_end_date=payload.get(
                "grace_period_end_date",
                current.grace_period_end_date,
            ),
            is_active=payload.get("is_active", current.is_active),
            status_message=current.status_message,
        )

    def get_subscription_messages(
        self,
        request: BridgeRequest,
    ) -> list[BridgeSubscriptionMessageResult]:
        self.requests.append(("subscription-messages", request))
        return self._build_subscription_messages()

    def upsert_subscription_messages(
        self,
        request: BridgeRequest,
        payload: list[dict[str, object]],
    ) -> list[BridgeSubscriptionMessageResult]:
        self.requests.append(("subscription-messages-update", request, payload))
        return [
            BridgeSubscriptionMessageResult(
                status=item["status"],
                message_template=item["message_template"],
            )
            for item in payload
        ]

    def get_subscription_config(
        self,
        request: BridgeRequest,
    ) -> BridgeSubscriptionConfigResult:
        self.requests.append(("subscription-config", request))
        return BridgeSubscriptionConfigResult(
            subscription=self._build_subscription_result(),
            messages=self._build_subscription_messages(),
        )

    def sync_subscription_config(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionConfigResult:
        self.requests.append(("subscription-config-sync", request, payload))
        current = self._build_subscription_result()
        subscription_payload = payload.get("subscription") or {}
        messages_payload = payload.get("messages")
        return BridgeSubscriptionConfigResult(
            subscription=BridgeSubscriptionResult(
                start_date=current.start_date,
                end_date=subscription_payload.get("end_date", current.end_date),
                grace_period_end_date=subscription_payload.get(
                    "grace_period_end_date",
                    current.grace_period_end_date,
                ),
                is_active=subscription_payload.get("is_active", current.is_active),
                status_message=current.status_message,
            ),
            messages=(
                [
                    BridgeSubscriptionMessageResult(
                        status=item["status"],
                        message_template=item["message_template"],
                    )
                    for item in messages_payload
                ]
                if isinstance(messages_payload, list)
                else self._build_subscription_messages()
            ),
        )

    def _build_subscription_result(self) -> BridgeSubscriptionResult:
        return BridgeSubscriptionResult(
            start_date="1405-01-01T00:00:00+0330",
            end_date="1405-02-01T00:00:00+0330",
            grace_period_end_date="1405-02-10T00:00:00+0330",
            is_active=True,
            status_message="",
        )

    def _build_subscription_messages(self) -> list[BridgeSubscriptionMessageResult]:
        return [
            BridgeSubscriptionMessageResult(
                status="expired",
                message_template="اشتراک شما به پایان رسیده است.",
            ),
            BridgeSubscriptionMessageResult(
                status="grace",
                message_template="مهلت شما {days} روز دیگر ادامه دارد.",
            ),
            BridgeSubscriptionMessageResult(
                status="near_expiry",
                message_template="اشتراک شما {days} روز دیگر منقضی می‌شود.",
            ),
        ]


class UnavailableBridgeClient:
    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        del request
        raise BridgeConnectionError("timed out")

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        del request
        raise BridgeConnectionError("timed out")

    def get_active_subscription(self, request: BridgeRequest) -> BridgeSubscriptionResult:
        del request
        raise BridgeConnectionError("timed out")

    def update_active_subscription(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionResult:
        del request, payload
        raise BridgeConnectionError("timed out")

    def get_subscription_messages(
        self,
        request: BridgeRequest,
    ) -> list[BridgeSubscriptionMessageResult]:
        del request
        raise BridgeConnectionError("timed out")

    def upsert_subscription_messages(
        self,
        request: BridgeRequest,
        payload: list[dict[str, object]],
    ) -> list[BridgeSubscriptionMessageResult]:
        del request, payload
        raise BridgeConnectionError("timed out")

    def get_subscription_config(self, request: BridgeRequest) -> BridgeSubscriptionConfigResult:
        del request
        raise BridgeConnectionError("timed out")

    def sync_subscription_config(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionConfigResult:
        del request, payload
        raise BridgeConnectionError("timed out")


class UnauthorizedBridgeClient:
    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        del request
        raise BridgeUnauthorizedError(status_code=401)

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        del request
        raise BridgeUnauthorizedError(status_code=401)

    def get_active_subscription(self, request: BridgeRequest) -> BridgeSubscriptionResult:
        del request
        raise BridgeUnauthorizedError(status_code=401)

    def update_active_subscription(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionResult:
        del request, payload
        raise BridgeUnauthorizedError(status_code=401)

    def get_subscription_messages(
        self,
        request: BridgeRequest,
    ) -> list[BridgeSubscriptionMessageResult]:
        del request
        raise BridgeUnauthorizedError(status_code=401)

    def upsert_subscription_messages(
        self,
        request: BridgeRequest,
        payload: list[dict[str, object]],
    ) -> list[BridgeSubscriptionMessageResult]:
        del request, payload
        raise BridgeUnauthorizedError(status_code=401)

    def get_subscription_config(self, request: BridgeRequest) -> BridgeSubscriptionConfigResult:
        del request
        raise BridgeUnauthorizedError(status_code=401)

    def sync_subscription_config(
        self,
        request: BridgeRequest,
        payload: dict[str, object],
    ) -> BridgeSubscriptionConfigResult:
        del request, payload
        raise BridgeUnauthorizedError(status_code=401)


class MissingSubscriptionBridgeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, BridgeRequest]] = []

    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        del request
        raise AssertionError("health should not be called in this test")

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        del request
        raise AssertionError("capabilities should not be called in this test")

    def get_active_subscription(self, request: BridgeRequest) -> BridgeSubscriptionResult:
        self.requests.append(("subscription", request))
        raise BridgeUnexpectedStatusError(
            status_code=404,
            response_body='{"error":"هیچ اشتراک فعالی وجود ندارد."}',
        )

    def get_subscription_config(self, request: BridgeRequest) -> BridgeSubscriptionConfigResult:
        self.requests.append(("subscription-config", request))
        raise BridgeUnexpectedStatusError(
            status_code=404,
            response_body='{"error":"هیچ اشتراک فعالی وجود ندارد."}',
        )

class FailedSubscriptionBridgeClient:
    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        del request
        raise AssertionError("health should not be called in this test")

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        del request
        raise AssertionError("capabilities should not be called in this test")

    def get_active_subscription(self, request: BridgeRequest) -> BridgeSubscriptionResult:
        del request
        raise BridgeUnexpectedStatusError(
            status_code=500,
            response_body='{"error":"database unavailable","request_id":"bridge-err-123"}',
        )

    def get_subscription_config(self, request: BridgeRequest) -> BridgeSubscriptionConfigResult:
        del request
        raise BridgeUnexpectedStatusError(
            status_code=500,
            response_body='{"error":"database unavailable","request_id":"bridge-err-123"}',
        )


def test_bridge_client_normalizes_iso_like_jalali_subscription_datetimes() -> None:
    bridge_client = BridgeClient()

    result = bridge_client._parse_subscription(  # noqa: SLF001
        {
            "start_date": "1404-01-01T03:30:00+0330",
            "end_date": "1404-04-29T02:30:00+0330",
            "grace_period_end_date": "1404-04-10T02:30:00+0330",
            "is_active": True,
            "status_message": "",
        }
    )

    assert result == BridgeSubscriptionResult(
        start_date="1404-01-01 03:30:00",
        end_date="1404-04-29 02:30:00",
        grace_period_end_date="1404-04-10 02:30:00",
        is_active=True,
        status_message="",
    )


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
    del client
    return token_for_mobile(mobile)


def _admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    admin = _create_admin(db_session=db_session)
    token = _login(client=client, mobile=admin.mobile)
    return {"Authorization": f"Bearer {token}"}


def _assert_bridge_request(
    request: BridgeRequest,
    *,
    customer_id: int,
    base_url: str,
    instance_id: str = "default",
    tenant_id: str = "",
    audience: str = "",
    correlation_id: str | None,
    timeout_seconds: int = 10,
    retry_count: int = 0,
    retry_backoff_seconds: float = 0.0,
    legacy_api_key: str | None = "bridge-secret",
) -> None:
    assert request.base_url == base_url
    assert request.correlation_id == correlation_id
    assert request.timeout_seconds == timeout_seconds
    assert request.retry_count == retry_count
    assert request.retry_backoff_seconds == retry_backoff_seconds
    assert request.legacy_api_key == legacy_api_key
    claims = jwt.get_unverified_claims(request.access_token)
    assert claims["customer_id"] == str(customer_id)
    assert claims["instance_id"] == instance_id
    assert claims["tenant_id"] == tenant_id
    assert claims["aud"] == audience
    assert claims["token_type"] == "bridge_access"


def test_customer_bridge_health_and_capabilities_use_customer_configuration(
    client: TestClient,
    db_session: Session,
) -> None:
    bridge_client = RecordingBridgeClient()
    app.dependency_overrides[get_bridge_client] = lambda: bridge_client
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Tehran Customer",
            "grade": 1,
        },
    )
    assert customer_response.status_code == 201
    customer_data = customer_response.json()
    customer_id = customer_data["id"]

    bridge_config_response = client.get(
        f"/customers/{customer_id}/bridge",
        headers=headers,
    )
    assert bridge_config_response.status_code == 200
    assert bridge_config_response.json() == {
        "customer_id": customer_id,
        "customer_name": "Tehran Customer",
        "instance_id": "default",
        "base_url_internal": None,
        "audience": None,
        "tenant_id": None,
        "status": "inactive",
        "request_timeout_seconds": None,
        "request_retry_count": None,
        "request_retry_backoff_seconds": None,
        "bridge_base_url": None,
        "bridge_is_enabled": False,
        "bridge_has_api_key": False,
        "last_online_status": None,
        "last_health_checked_at": None,
        "last_health_error": None,
    }

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://tehran.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200
    assert bridge_update_response.json() == {
        "customer_id": customer_id,
        "customer_name": "Tehran Customer",
        "instance_id": "default",
        "base_url_internal": "https://tehran.example.com",
        "audience": "zaraamad:default",
        "tenant_id": str(customer_id),
        "status": "active",
        "request_timeout_seconds": None,
        "request_retry_count": None,
        "request_retry_backoff_seconds": None,
        "bridge_base_url": "https://tehran.example.com",
        "bridge_is_enabled": True,
        "bridge_has_api_key": True,
        "last_online_status": None,
        "last_health_checked_at": None,
        "last_health_error": None,
    }

    refresh_response = client.post(
        f"/customers/{customer_id}/bridge/refresh-status",
        headers={**headers, "X-Correlation-ID": "corr-refresh"},
    )
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()
    assert refresh_data["customer_id"] == customer_id
    assert refresh_data["last_online_status"] is True
    assert refresh_data["last_health_checked_at"] is not None
    assert refresh_data["last_health_error"] is None

    health_response = client.get(
        f"/customers/{customer_id}/bridge/health",
        headers={**headers, "X-Correlation-ID": "corr-123"},
    )
    assert health_response.status_code == 200
    assert health_response.json() == {
        "customer_id": customer_id,
        "customer_name": "Tehran Customer",
        "bridge_base_url": "https://tehran.example.com",
        "status": "ok",
        "bridge_name": "Tehran Support Bridge",
        "bridge_version": "1.0.0",
    }

    capabilities_response = client.get(
        f"/customers/{customer_id}/bridge/capabilities",
        headers=headers,
    )
    assert capabilities_response.status_code == 200
    capabilities_data = capabilities_response.json()
    assert capabilities_data["customer_id"] == customer_id
    assert capabilities_data["bridge_name"] == "Tehran Support Bridge"
    assert [item["code"] for item in capabilities_data["capabilities"]] == [
        "support.health.read",
        "support.capabilities.read",
    ]

    assert [item[0] for item in bridge_client.requests] == [
        "health",
        "health",
        "capabilities",
    ]
    _assert_bridge_request(
        bridge_client.requests[0][1],
        customer_id=customer_id,
        base_url="https://tehran.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id="corr-refresh",
    )
    _assert_bridge_request(
        bridge_client.requests[1][1],
        customer_id=customer_id,
        base_url="https://tehran.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id="corr-123",
    )
    _assert_bridge_request(
        bridge_client.requests[2][1],
        customer_id=customer_id,
        base_url="https://tehran.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id=None,
    )


def test_customer_bridge_subscription_uses_customer_configuration(
    client: TestClient,
    db_session: Session,
) -> None:
    bridge_client = RecordingBridgeClient()
    app.dependency_overrides[get_bridge_client] = lambda: bridge_client
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Subscription Customer",
            "grade": 1,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://subscription.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    active_response = client.get(
        f"/customers/{customer_id}/bridge/subscriptions/active",
        headers={**headers, "X-Correlation-ID": "corr-subscription"},
    )
    assert active_response.status_code == 200
    assert active_response.json() == {
        "start_date": "1405-01-01 00:00:00",
        "end_date": "1405-02-01 00:00:00",
        "grace_period_end_date": "1405-02-10 00:00:00",
        "is_active": True,
        "status_message": "",
    }

    assert [item[0] for item in bridge_client.requests] == ["subscription"]
    _assert_bridge_request(
        bridge_client.requests[0][1],
        customer_id=customer_id,
        base_url="https://subscription.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id="corr-subscription",
    )


def test_customer_bridge_health_uses_instance_registry_claims_and_retry_metadata(
    client: TestClient,
    db_session: Session,
) -> None:
    bridge_client = RecordingBridgeClient()
    app.dependency_overrides[get_bridge_client] = lambda: bridge_client
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Registry Customer",
            "grade": 2,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "instance_id": "karaj-main",
            "base_url_internal": "https://karaj-internal.example.com/",
            "audience": "zaraamad:karaj-main",
            "tenant_id": "karaj",
            "status": "active",
            "request_timeout_seconds": 33,
            "request_retry_count": 2,
            "request_retry_backoff_seconds": 1.5,
        },
    )
    assert bridge_update_response.status_code == 200

    health_response = client.get(
        f"/customers/{customer_id}/bridge/health",
        params={"instance_id": "karaj-main"},
        headers={**headers, "X-Correlation-ID": "corr-registry"},
    )
    assert health_response.status_code == 200
    assert health_response.json()["bridge_base_url"] == "https://karaj-internal.example.com"

    assert [item[0] for item in bridge_client.requests] == ["health"]
    _assert_bridge_request(
        bridge_client.requests[0][1],
        customer_id=customer_id,
        base_url="https://karaj-internal.example.com",
        instance_id="karaj-main",
        tenant_id="karaj",
        audience="zaraamad:karaj-main",
        correlation_id="corr-registry",
        timeout_seconds=33,
        retry_count=2,
        retry_backoff_seconds=1.5,
        legacy_api_key=None,
    )


def test_customer_bridge_health_rejects_incomplete_bridge_configuration(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client=client, db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Qom Customer",
            "grade": 2,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    response = client.get(
        f"/customers/{customer_id}/bridge/health",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["message"] == CUSTOMER_BRIDGE_NOT_CONFIGURED
    assert "bridge_row" in response.json()["developer_message"]


def test_customer_bridge_subscription_config_fetch_and_sync_use_customer_configuration(
    client: TestClient,
    db_session: Session,
) -> None:
    bridge_client = RecordingBridgeClient()
    app.dependency_overrides[get_bridge_client] = lambda: bridge_client
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Config Customer",
            "grade": 2,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://subscription.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    config_response = client.get(
        f"/customers/{customer_id}/bridge/subscriptions/config",
        headers={**headers, "X-Correlation-ID": "corr-config"},
    )
    assert config_response.status_code == 200
    assert config_response.json() == {
        "subscription": {
            "start_date": "1405-01-01 00:00:00",
            "end_date": "1405-02-01 00:00:00",
            "grace_period_end_date": "1405-02-10 00:00:00",
            "is_active": True,
            "status_message": "",
        },
        "messages": [
            {
                "status": "expired",
                "message_template": "اشتراک شما به پایان رسیده است.",
            },
            {
                "status": "grace",
                "message_template": "مهلت شما {days} روز دیگر ادامه دارد.",
            },
            {
                "status": "near_expiry",
                "message_template": "اشتراک شما {days} روز دیگر منقضی می‌شود.",
            },
        ],
    }

    sync_response = client.patch(
        f"/customers/{customer_id}/bridge/subscriptions/config",
        headers={**headers, "X-Correlation-ID": "corr-sync"},
        json={
            "subscription": {
                "end_date": "1405-03-01 00:00:00",
                "grace_period_end_date": "1405-03-07 00:00:00",
                "is_active": False,
            },
            "messages": [
                {
                    "status": "expired",
                    "message_template": "اشتراک شما به پایان رسیده است.",
                },
                {
                    "status": "grace",
                    "message_template": "مهلت شما {days} روز دیگر ادامه دارد.",
                },
            ],
        },
    )
    assert sync_response.status_code == 200
    assert sync_response.json() == {
        "subscription": {
            "start_date": "1405-01-01 00:00:00",
            "end_date": "1405-03-01 00:00:00",
            "grace_period_end_date": "1405-03-07 00:00:00",
            "is_active": False,
            "status_message": "",
        },
        "messages": [
            {
                "status": "expired",
                "message_template": "اشتراک شما به پایان رسیده است.",
            },
            {
                "status": "grace",
                "message_template": "مهلت شما {days} روز دیگر ادامه دارد.",
            },
        ],
    }

    assert [item[0] for item in bridge_client.requests] == [
        "subscription-config",
        "subscription-config-sync",
    ]
    _assert_bridge_request(
        bridge_client.requests[0][1],
        customer_id=customer_id,
        base_url="https://subscription.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id="corr-config",
    )
    _assert_bridge_request(
        bridge_client.requests[1][1],
        customer_id=customer_id,
        base_url="https://subscription.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id="corr-sync",
    )
    sync_payload = bridge_client.requests[1][2]
    assert sync_payload["subscription"] == {
        "end_date": "1405-03-01 00:00:00",
        "grace_period_end_date": "1405-03-07 00:00:00",
        "is_active": False,
    }
    assert [item["status"] for item in sync_payload["messages"]] == ["expired", "grace"]


def test_customer_bridge_subscription_maps_missing_upstream_subscription_to_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    bridge_client = MissingSubscriptionBridgeClient()
    app.dependency_overrides[get_bridge_client] = lambda: bridge_client
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "No Subscription Customer",
            "grade": 2,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://subscription.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    active_response = client.get(
        f"/customers/{customer_id}/bridge/subscriptions/active",
        headers=headers,
    )
    assert active_response.status_code == 404
    response = active_response
    assert response.json()["message"] == "هیچ اشتراک فعالی وجود ندارد."
    assert "returned status 404" in response.json()["developer_message"]

    assert [item[0] for item in bridge_client.requests] == ["subscription"]
    _assert_bridge_request(
        bridge_client.requests[0][1],
        customer_id=customer_id,
        base_url="https://subscription.example.com",
        instance_id="default",
        tenant_id=str(customer_id),
        audience="zaraamad:default",
        correlation_id=None,
    )


def test_customer_bridge_subscription_surfaces_upstream_error_details_for_debugging(
    client: TestClient,
    db_session: Session,
) -> None:
    app.dependency_overrides[get_bridge_client] = lambda: FailedSubscriptionBridgeClient()
    headers = _admin_headers(client=client, db_session=db_session)

    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Failing Subscription Customer",
            "grade": 2,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://subscription.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    response = client.get(
        f"/customers/{customer_id}/bridge/subscriptions/active",
        headers=headers,
    )
    assert response.status_code == 502
    assert "unexpected status 500" in response.json()["developer_message"]
    assert "database unavailable" in response.json()["developer_message"]
    assert "bridge-err-123" in response.json()["developer_message"]


def test_customer_bridge_refresh_status_caches_offline_result_without_failing(
    client: TestClient,
    db_session: Session,
) -> None:
    app.dependency_overrides[get_bridge_client] = lambda: UnavailableBridgeClient()
    headers = _admin_headers(client=client, db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Mashhad Customer",
            "grade": 1,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://mashhad.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    refresh_response = client.post(
        f"/customers/{customer_id}/bridge/refresh-status",
        headers=headers,
    )
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()
    assert refresh_data["last_online_status"] is False
    assert refresh_data["last_health_checked_at"] is not None
    assert "timed out" in refresh_data["last_health_error"]

    bridge_config_response = client.get(
        f"/customers/{customer_id}/bridge",
        headers=headers,
    )
    assert bridge_config_response.status_code == 200
    bridge_config_data = bridge_config_response.json()
    assert bridge_config_data["last_online_status"] is False
    assert "timed out" in bridge_config_data["last_health_error"]


def test_customer_bridge_health_maps_unavailable_bridge_to_service_unavailable(
    client: TestClient,
    db_session: Session,
) -> None:
    app.dependency_overrides[get_bridge_client] = lambda: UnavailableBridgeClient()
    headers = _admin_headers(client=client, db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Karaj Customer",
            "grade": 1,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://karaj.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    response = client.get(
        f"/customers/{customer_id}/bridge/health",
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["message"] == CUSTOMER_BRIDGE_UNAVAILABLE
    assert response.json()["detail"] == CUSTOMER_BRIDGE_UNAVAILABLE

    bridge_config_response = client.get(
        f"/customers/{customer_id}/bridge",
        headers=headers,
    )
    assert bridge_config_response.status_code == 200
    bridge_config_data = bridge_config_response.json()
    assert bridge_config_data["last_online_status"] is False
    assert "timed out" in bridge_config_data["last_health_error"]


def test_customer_bridge_capabilities_maps_unauthorized_bridge_to_bad_gateway(
    client: TestClient,
    db_session: Session,
) -> None:
    app.dependency_overrides[get_bridge_client] = lambda: UnauthorizedBridgeClient()
    headers = _admin_headers(client=client, db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Shiraz Customer",
            "grade": 3,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://shiraz.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    response = client.get(
        f"/customers/{customer_id}/bridge/capabilities",
        headers=headers,
    )
    assert response.status_code == 502
    assert response.json()["message"] == CUSTOMER_BRIDGE_AUTH_FAILED
    assert response.json()["detail"] == CUSTOMER_BRIDGE_AUTH_FAILED


def test_customer_bridge_subscription_config_maps_unauthorized_bridge_to_bad_gateway(
    client: TestClient,
    db_session: Session,
) -> None:
    app.dependency_overrides[get_bridge_client] = lambda: UnauthorizedBridgeClient()
    headers = _admin_headers(client=client, db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Tabriz Customer",
            "grade": 3,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    bridge_update_response = client.patch(
        f"/customers/{customer_id}/bridge",
        headers=headers,
        json={
            "bridge_base_url": "https://tabriz.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert bridge_update_response.status_code == 200

    response = client.get(
        f"/customers/{customer_id}/bridge/subscriptions/config",
        headers=headers,
    )
    assert response.status_code == 502
    assert response.json()["message"] == CUSTOMER_BRIDGE_AUTH_FAILED
    assert response.json()["detail"] == CUSTOMER_BRIDGE_AUTH_FAILED


def test_local_subscription_routes_are_not_exposed() -> None:
    route_paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert "/sub/subscription/" not in route_paths
    assert "/sub/subscriptions/active/" not in route_paths
    assert "/sub/subscriptions/messages/" not in route_paths
