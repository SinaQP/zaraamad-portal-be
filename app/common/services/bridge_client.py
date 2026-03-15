from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class BridgeRequest:
    base_url: str
    api_key: str
    timeout_seconds: int
    correlation_id: str | None = None


@dataclass(frozen=True)
class BridgeHealthResult:
    status: str
    bridge_name: str
    bridge_version: str | None = None


@dataclass(frozen=True)
class BridgeCapability:
    code: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class BridgeCapabilitiesResult:
    bridge_name: str
    bridge_version: str | None
    capabilities: list[BridgeCapability]


@dataclass(frozen=True)
class BridgeSubscriptionResult:
    start_date: str
    end_date: str
    grace_period_end_date: str | None
    is_active: bool
    status_message: str


class BridgeClientError(Exception):
    pass


class BridgeConnectionError(BridgeClientError):
    pass


class BridgeUnauthorizedError(BridgeClientError):
    def __init__(self, status_code: int, response_body: str | None = None) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Bridge authorization failed with status {status_code}.")


class BridgeUnexpectedStatusError(BridgeClientError):
    def __init__(self, status_code: int, response_body: str | None = None) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Bridge request failed with status {status_code}.")


class BridgeInvalidResponseError(BridgeClientError):
    pass


class BridgeClient:
    _HEALTH_PATH = "/bridge/health"
    _CAPABILITIES_PATH = "/bridge/capabilities"
    _ACTIVE_SUBSCRIPTION_PATH = "/sub/subscriptions/active/"

    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        payload = self._request_json(request=request, path=self._HEALTH_PATH)
        status = self._read_required_str(payload=payload, field_name="status")
        bridge_name = self._read_required_str(payload=payload, field_name="bridge_name")
        bridge_version = self._read_optional_str(payload=payload, field_name="bridge_version")
        return BridgeHealthResult(
            status=status,
            bridge_name=bridge_name,
            bridge_version=bridge_version,
        )

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        payload = self._request_json(request=request, path=self._CAPABILITIES_PATH)
        bridge_name = self._read_required_str(payload=payload, field_name="bridge_name")
        bridge_version = self._read_optional_str(payload=payload, field_name="bridge_version")
        raw_capabilities = payload.get("capabilities")
        if not isinstance(raw_capabilities, list):
            raise BridgeInvalidResponseError("Field 'capabilities' must be a JSON array.")
        capabilities = [self._parse_capability(item=item) for item in raw_capabilities]
        return BridgeCapabilitiesResult(
            bridge_name=bridge_name,
            bridge_version=bridge_version,
            capabilities=capabilities,
        )

    def get_active_subscription(
        self,
        request: BridgeRequest,
    ) -> BridgeSubscriptionResult:
        payload = self._request_json(
            request=request,
            path=self._ACTIVE_SUBSCRIPTION_PATH,
        )
        start_date = self._read_required_str(payload=payload, field_name="start_date")
        end_date = self._read_required_str(payload=payload, field_name="end_date")
        grace_period_end_date = self._read_optional_str(
            payload=payload,
            field_name="grace_period_end_date",
        )
        is_active = self._read_required_bool(payload=payload, field_name="is_active")
        status_message = payload.get("status_message", "")
        if not isinstance(status_message, str):
            raise BridgeInvalidResponseError(
                "Field 'status_message' must be a string when provided."
            )
        return BridgeSubscriptionResult(
            start_date=start_date,
            end_date=end_date,
            grace_period_end_date=grace_period_end_date,
            is_active=is_active,
            status_message=status_message,
        )

    def _request_json(self, request: BridgeRequest, path: str) -> dict[str, Any]:
        http_request = self._build_request(request=request, path=path)
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw_response = self._decode_response_body(response.read())
        except HTTPError as exc:
            response_body = self._decode_response_body(exc.read())
            if exc.code in {401, 403}:
                raise BridgeUnauthorizedError(
                    status_code=exc.code,
                    response_body=response_body,
                ) from exc
            raise BridgeUnexpectedStatusError(
                status_code=exc.code,
                response_body=response_body,
            ) from exc
        except (TimeoutError, URLError, OSError) as exc:
            raise BridgeConnectionError(str(exc)) from exc
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise BridgeInvalidResponseError("Bridge response was not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise BridgeInvalidResponseError("Bridge response must be a JSON object.")
        return payload

    def _build_request(self, request: BridgeRequest, path: str) -> Request:
        base_url = request.base_url.rstrip("/")
        headers = {
            "Accept": "application/json",
            "X-Bridge-Key": request.api_key,
        }
        if request.correlation_id:
            headers["X-Correlation-ID"] = request.correlation_id
        return Request(
            url=f"{base_url}{path}",
            headers=headers,
            method="GET",
        )

    def _parse_capability(self, item: Any) -> BridgeCapability:
        if not isinstance(item, dict):
            raise BridgeInvalidResponseError("Each capability item must be an object.")
        code = self._read_required_str(payload=item, field_name="code")
        name = self._read_required_str(payload=item, field_name="name")
        description = self._read_optional_str(payload=item, field_name="description")
        return BridgeCapability(
            code=code,
            name=name,
            description=description,
        )

    def _read_required_str(self, payload: dict[str, Any], field_name: str) -> str:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise BridgeInvalidResponseError(
                f"Field '{field_name}' must be a non-empty string."
            )
        return value.strip()

    def _read_optional_str(self, payload: dict[str, Any], field_name: str) -> str | None:
        value = payload.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise BridgeInvalidResponseError(
                f"Field '{field_name}' must be a string when provided."
            )
        normalized_value = value.strip()
        return normalized_value or None

    def _read_required_bool(self, payload: dict[str, Any], field_name: str) -> bool:
        value = payload.get(field_name)
        if not isinstance(value, bool):
            raise BridgeInvalidResponseError(
                f"Field '{field_name}' must be a boolean."
            )
        return value

    def _decode_response_body(self, raw_body: bytes | str) -> str:
        if isinstance(raw_body, bytes):
            return raw_body.decode("utf-8", errors="replace")
        return raw_body


def get_bridge_client() -> BridgeClient:
    return BridgeClient()
