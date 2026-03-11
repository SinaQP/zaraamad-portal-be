from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.messages import (
    CUSTOMER_BRIDGE_AUTH_FAILED,
    CUSTOMER_BRIDGE_NOT_CONFIGURED,
    CUSTOMER_BRIDGE_UNAVAILABLE,
)
from app.common.services.bridge_client import (
    BridgeCapabilitiesResult,
    BridgeCapability,
    BridgeConnectionError,
    BridgeHealthResult,
    BridgeRequest,
    BridgeUnauthorizedError,
    get_bridge_client,
)
from app.main import app
from app.modules.users.schemas import User


class RecordingBridgeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, BridgeRequest]] = []

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


class UnavailableBridgeClient:
    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        raise BridgeConnectionError("timed out")

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        raise BridgeConnectionError("timed out")


class UnauthorizedBridgeClient:
    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        raise BridgeUnauthorizedError(status_code=401)

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        raise BridgeUnauthorizedError(status_code=401)


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
            "bridge_base_url": "https://tehran.example.com/",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert customer_response.status_code == 201
    customer_data = customer_response.json()
    assert customer_data["bridge_base_url"] == "https://tehran.example.com"
    assert customer_data["bridge_has_api_key"] is True
    customer_id = customer_data["id"]

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

    assert bridge_client.requests == [
        (
            "health",
            BridgeRequest(
                base_url="https://tehran.example.com",
                api_key="bridge-secret",
                timeout_seconds=10,
                correlation_id="corr-123",
            ),
        ),
        (
            "capabilities",
            BridgeRequest(
                base_url="https://tehran.example.com",
                api_key="bridge-secret",
                timeout_seconds=10,
                correlation_id=None,
            ),
        ),
    ]


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
    assert "bridge_is_enabled" in response.json()["developer_message"]


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
            "bridge_base_url": "https://karaj.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    response = client.get(
        f"/customers/{customer_id}/bridge/health",
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["message"] == CUSTOMER_BRIDGE_UNAVAILABLE
    assert response.json()["detail"] == CUSTOMER_BRIDGE_UNAVAILABLE


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
            "bridge_base_url": "https://shiraz.example.com",
            "bridge_api_key": "bridge-secret",
            "bridge_is_enabled": True,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    response = client.get(
        f"/customers/{customer_id}/bridge/capabilities",
        headers=headers,
    )
    assert response.status_code == 502
    assert response.json()["message"] == CUSTOMER_BRIDGE_AUTH_FAILED
    assert response.json()["detail"] == CUSTOMER_BRIDGE_AUTH_FAILED
