from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.common.enums import SubscriptionMessageStatus
from app.common.validators.jalali_datetime import validate_jalali_datetime_string

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class BridgeSubscriptionMessageResult:
    status: SubscriptionMessageStatus
    message_template: str


@dataclass(frozen=True)
class BridgeSubscriptionConfigResult:
    subscription: BridgeSubscriptionResult
    messages: list[BridgeSubscriptionMessageResult]


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
    _CAPABILITIES_PATH = "/internal-api/v1/bridge/capabilities"
    _ACTIVE_SUBSCRIPTION_PATH = "/sub/subscriptions/active/"
    _SUBSCRIPTION_MESSAGES_PATH = "/sub/subscriptions/messages/"

    def get_health(self, request: BridgeRequest) -> BridgeHealthResult:
        payload = self._request_json_object(request=request, path=self._HEALTH_PATH)
        status = self._read_required_str(payload=payload, field_name="status")
        bridge_name = self._read_required_str(payload=payload, field_name="bridge_name")
        bridge_version = self._read_optional_str(payload=payload, field_name="bridge_version")
        return BridgeHealthResult(
            status=status,
            bridge_name=bridge_name,
            bridge_version=bridge_version,
        )

    def get_capabilities(self, request: BridgeRequest) -> BridgeCapabilitiesResult:
        payload = self._request_json_object(request=request, path=self._CAPABILITIES_PATH)
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
        payload = self._request_json_object(
            request=request,
            path=self._ACTIVE_SUBSCRIPTION_PATH,
        )
        return self._parse_subscription(payload=payload)

    def update_active_subscription(
        self,
        request: BridgeRequest,
        payload: dict[str, Any],
    ) -> BridgeSubscriptionResult:
        response_payload = self._request_json_object(
            request=request,
            path=self._ACTIVE_SUBSCRIPTION_PATH,
            method="PATCH",
            body=payload,
        )
        return self._parse_subscription(payload=response_payload)

    def get_subscription_messages(
        self,
        request: BridgeRequest,
    ) -> list[BridgeSubscriptionMessageResult]:
        payload = self._request_json_array(
            request=request,
            path=self._SUBSCRIPTION_MESSAGES_PATH,
        )
        return [self._parse_subscription_message(item=item) for item in payload]

    def upsert_subscription_messages(
        self,
        request: BridgeRequest,
        payload: list[dict[str, Any]],
    ) -> list[BridgeSubscriptionMessageResult]:
        response_payload = self._request_json_array(
            request=request,
            path=self._SUBSCRIPTION_MESSAGES_PATH,
            method="PATCH",
            body=payload,
        )
        return [self._parse_subscription_message(item=item) for item in response_payload]

    def get_subscription_config(
        self,
        request: BridgeRequest,
    ) -> BridgeSubscriptionConfigResult:
        return BridgeSubscriptionConfigResult(
            subscription=self.get_active_subscription(request=request),
            messages=self.get_subscription_messages(request=request),
        )

    def sync_subscription_config(
        self,
        request: BridgeRequest,
        payload: dict[str, Any],
    ) -> BridgeSubscriptionConfigResult:
        raw_subscription_payload = payload.get("subscription")
        raw_messages_payload = payload.get("messages")

        if raw_subscription_payload is not None and not isinstance(raw_subscription_payload, dict):
            raise BridgeInvalidResponseError("Field 'subscription' must be an object when provided.")
        if raw_messages_payload is not None and not isinstance(raw_messages_payload, list):
            raise BridgeInvalidResponseError("Field 'messages' must be a JSON array when provided.")

        subscription = (
            self.update_active_subscription(
                request=request,
                payload=raw_subscription_payload,
            )
            if raw_subscription_payload is not None
            else self.get_active_subscription(request=request)
        )
        messages = (
            self.upsert_subscription_messages(
                request=request,
                payload=raw_messages_payload,
            )
            if raw_messages_payload is not None
            else self.get_subscription_messages(request=request)
        )
        return BridgeSubscriptionConfigResult(
            subscription=subscription,
            messages=messages,
        )

    def _parse_subscription(self, payload: dict[str, Any]) -> BridgeSubscriptionResult:
        start_date = self._read_required_jalali_datetime(
            payload=payload,
            field_name="start_date",
        )
        end_date = self._read_required_jalali_datetime(
            payload=payload,
            field_name="end_date",
        )
        grace_period_end_date = self._read_optional_jalali_datetime(
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

    def _parse_subscription_message(self, item: Any) -> BridgeSubscriptionMessageResult:
        if not isinstance(item, dict):
            raise BridgeInvalidResponseError("Each subscription message item must be an object.")
        raw_status = self._read_required_str(payload=item, field_name="status")
        try:
            status = SubscriptionMessageStatus(raw_status)
        except ValueError as exc:
            raise BridgeInvalidResponseError(
                "Field 'status' must be a supported subscription message status."
            ) from exc
        message_template = self._read_required_str(
            payload=item,
            field_name="message_template",
        )
        return BridgeSubscriptionMessageResult(
            status=status,
            message_template=message_template,
        )

    def _request_json_object(
        self,
        request: BridgeRequest,
        path: str,
        *,
        method: str = "GET",
        body: Any | None = None,
    ) -> dict[str, Any]:
        payload = self._request_json_value(
            request=request,
            path=path,
            method=method,
            body=body,
        )
        if not isinstance(payload, dict):
            raise BridgeInvalidResponseError("Bridge response must be a JSON object.")
        return payload

    def _request_json_array(
        self,
        request: BridgeRequest,
        path: str,
        *,
        method: str = "GET",
        body: Any | None = None,
    ) -> list[Any]:
        payload = self._request_json_value(
            request=request,
            path=path,
            method=method,
            body=body,
        )
        if not isinstance(payload, list):
            raise BridgeInvalidResponseError("Bridge response must be a JSON array.")
        return payload

    def _request_json_value(
        self,
        request: BridgeRequest,
        path: str,
        *,
        method: str = "GET",
        body: Any | None = None,
    ) -> Any:
        http_request = self._build_request(
            request=request,
            path=path,
            method=method,
            body=body,
        )
        self._log_request(http_request=http_request, timeout_seconds=request.timeout_seconds)
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw_response = self._decode_response_body(response.read())
                logger.info(
                    "Bridge response received: method=%s url=%s status=%s",
                    http_request.get_method(),
                    http_request.full_url,
                    getattr(response, "status", "unknown"),
                )
        except HTTPError as exc:
            response_body = self._decode_response_body(exc.read())
            logger.warning(
                "Bridge response error: method=%s url=%s status=%s body=%s",
                http_request.get_method(),
                http_request.full_url,
                exc.code,
                response_body,
            )
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
            logger.warning(
                "Bridge connection error: method=%s url=%s error=%s",
                http_request.get_method(),
                http_request.full_url,
                exc,
            )
            raise BridgeConnectionError(str(exc)) from exc
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise BridgeInvalidResponseError("Bridge response was not valid JSON.") from exc
        return payload

    def _build_request(
        self,
        request: BridgeRequest,
        path: str,
        *,
        method: str = "GET",
        body: Any | None = None,
    ) -> Request:
        base_url = request.base_url.rstrip("/")
        headers = {
            "Accept": "application/json",
            "X-Bridge-Key": request.api_key,
        }
        if request.correlation_id:
            headers["X-Correlation-ID"] = request.correlation_id
        encoded_body: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded_body = json.dumps(
                body,
                ensure_ascii=False,
                default=self._encode_json_body,
            ).encode("utf-8")
        return Request(
            url=f"{base_url}{path}",
            headers=headers,
            data=encoded_body,
            method=method,
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

    def _read_required_jalali_datetime(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> str:
        value = self._read_required_str(payload=payload, field_name=field_name)
        return self._normalize_jalali_datetime(field_name=field_name, value=value)

    def _read_optional_jalali_datetime(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = self._read_optional_str(payload=payload, field_name=field_name)
        if value is None:
            return None
        return self._normalize_jalali_datetime(field_name=field_name, value=value)

    def _normalize_jalali_datetime(self, *, field_name: str, value: str) -> str:
        try:
            return validate_jalali_datetime_string(value)
        except ValueError as exc:
            raise BridgeInvalidResponseError(
                f"Field '{field_name}' must be a supported Jalali datetime string."
            ) from exc

    def _decode_response_body(self, raw_body: bytes | str) -> str:
        if isinstance(raw_body, bytes):
            return raw_body.decode("utf-8", errors="replace")
        return raw_body

    def _encode_json_body(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")

    def _log_request(self, http_request: Request, timeout_seconds: int) -> None:
        raw_body = getattr(http_request, "data", None)
        body_text: str | None = None
        if isinstance(raw_body, bytes):
            body_text = raw_body.decode("utf-8", errors="replace")
        elif isinstance(raw_body, str):
            body_text = raw_body
        logger.info(
            "Bridge request sending: method=%s url=%s timeout_seconds=%s headers=%s body=%s",
            http_request.get_method(),
            http_request.full_url,
            timeout_seconds,
            self._sanitize_headers(dict(http_request.header_items())),
            body_text,
        )

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        sanitized_headers = dict(headers)
        for key in list(sanitized_headers):
            if key.lower() == "x-bridge-key":
                sanitized_headers[key] = self._mask_secret(sanitized_headers[key])
        return sanitized_headers

    def _mask_secret(self, value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"


def get_bridge_client() -> BridgeClient:
    return BridgeClient()
