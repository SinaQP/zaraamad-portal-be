from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.common.config import Settings


@dataclass(frozen=True)
class SmsSendResult:
    ok: bool
    status_code: int
    raw_response: str | None = None


@dataclass(frozen=True)
class SmsPanelConfig:
    organization: str
    username: str
    password: str
    sender: str


class SmsServiceError(Exception):
    pass


class SmsConfigError(SmsServiceError):
    pass


class SmsDeliveryError(SmsServiceError):
    def __init__(self, result: SmsSendResult) -> None:
        self.result = result
        super().__init__("SMS delivery failed.")


class LoginOtpMessageBuilder:
    def build(self, otp_code: str) -> str:
        return (
            f"\u06a9\u062f \u062a\u0627\u06cc\u06cc\u062f \u0648\u0631\u0648\u062f \u0634\u0645\u0627: {otp_code}\n"
            "\u0627\u06cc\u0646 \u06a9\u062f \u0631\u0627 \u062f\u0631 \u0627\u062e\u062a\u06cc\u0627\u0631 \u062f\u06cc\u06af\u0631\u0627\u0646 \u0642\u0631\u0627\u0631 \u0646\u062f\u0647\u06cc\u062f."
        )


class SmsService:
    _SUCCESS_VALUES = {
        "1",
        "accepted",
        "ok",
        "queued",
        "sent",
        "success",
        "successful",
        "true",
    }
    _FAILURE_VALUES = {
        "-1",
        "0",
        "error",
        "fail",
        "failed",
        "false",
        "invalid",
        "not_sent",
        "notsent",
        "rejected",
    }
    _FAILURE_KEYWORDS = (
        "error",
        "fail",
        "invalid",
        "reject",
        "not sent",
        "notsent",
        "unsuccess",
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_sms(self, recipient: str, message: str) -> SmsSendResult:
        config = self._get_panel_config()
        request = self._build_request(
            config=config,
            recipient=recipient,
            message=message,
        )
        http_result = self._perform_request(request=request)
        result = self._evaluate_result(result=http_result)
        if not result.ok:
            raise SmsDeliveryError(result=result)
        return result

    def _build_request(
        self,
        config: SmsPanelConfig,
        recipient: str,
        message: str,
    ) -> Request:
        payload = {
            "organization": config.organization,
            "username": config.username,
            "password": config.password,
            "method": "send",
            "messages": [
                {
                    "sender": config.sender,
                    "recipient": recipient,
                    "body": message,
                }
            ],
        }
        return Request(
            url=self._settings.sms_api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    def _perform_request(self, request: Request) -> SmsSendResult:
        try:
            with urlopen(
                request,
                timeout=self._settings.sms_request_timeout_seconds,
            ) as response:
                return SmsSendResult(
                    ok=response.status == 200,
                    status_code=response.status,
                    raw_response=self._decode_response_body(response.read()),
                )
        except HTTPError as exc:
            return SmsSendResult(
                ok=False,
                status_code=exc.code,
                raw_response=self._decode_response_body(exc.read()),
            )
        except (TimeoutError, URLError, OSError) as exc:
            return SmsSendResult(
                ok=False,
                status_code=0,
                raw_response=str(exc),
            )

    def _evaluate_result(self, result: SmsSendResult) -> SmsSendResult:
        if result.status_code != 200:
            return SmsSendResult(
                ok=False,
                status_code=result.status_code,
                raw_response=result.raw_response,
            )

        payload = self._parse_json_payload(raw_response=result.raw_response)
        if payload is not None:
            delivery_state = self._extract_delivery_state(payload=payload)
            if delivery_state is False:
                return SmsSendResult(
                    ok=False,
                    status_code=result.status_code,
                    raw_response=result.raw_response,
                )
            if delivery_state is True:
                return SmsSendResult(
                    ok=True,
                    status_code=result.status_code,
                    raw_response=result.raw_response,
                )

        if self._body_contains_failure_keywords(raw_body=result.raw_response):
            return SmsSendResult(
                ok=False,
                status_code=result.status_code,
                raw_response=result.raw_response,
            )

        return SmsSendResult(
            ok=True,
            status_code=result.status_code,
            raw_response=result.raw_response,
        )

    def _get_panel_config(self) -> SmsPanelConfig:
        organization = self._settings.sms_panel_organization
        username = self._settings.sms_panel_username
        password = self._settings.sms_panel_password
        sender = self._settings.sms_panel_sender
        if not all([organization, username, password, sender]):
            raise SmsConfigError(
                "Missing SMS panel config: "
                "SMS_PANEL_ORGANIZATION, SMS_PANEL_USERNAME, SMS_PANEL_PASSWORD, SMS_PANEL_SENDER",
            )
        return SmsPanelConfig(
            organization=organization,
            username=username,
            password=password,
            sender=sender,
        )

    def _parse_json_payload(self, raw_response: str | None) -> object | None:
        if raw_response is None:
            return None
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            return None

    def _extract_delivery_state(self, payload: object) -> bool | None:
        indicators = list(self._iter_delivery_indicators(payload=payload))
        if not indicators:
            return None
        if False in indicators:
            return False
        if True in indicators:
            return True
        return None

    def _iter_delivery_indicators(self, payload: object):
        if isinstance(payload, dict):
            for key, value in payload.items():
                normalized_key = str(key).strip().lower()
                normalized_value = self._normalize_status_value(value=value)
                if normalized_key in {
                    "accepted",
                    "delivery",
                    "deliverystatus",
                    "ok",
                    "result",
                    "sent",
                    "status",
                    "success",
                } and normalized_value is not None:
                    yield normalized_value
                yield from self._iter_delivery_indicators(payload=value)
            return
        if isinstance(payload, list):
            for item in payload:
                yield from self._iter_delivery_indicators(payload=item)

    def _normalize_status_value(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value > 0
        if isinstance(value, float):
            return value > 0
        if isinstance(value, str):
            normalized_value = value.strip().lower()
            if normalized_value in self._SUCCESS_VALUES:
                return True
            if normalized_value in self._FAILURE_VALUES:
                return False
        return None

    def _body_contains_failure_keywords(self, raw_body: str | None) -> bool:
        if not raw_body:
            return False
        normalized_body = raw_body.strip().lower()
        return any(keyword in normalized_body for keyword in self._FAILURE_KEYWORDS)

    def _decode_response_body(self, raw_body: bytes | str) -> str:
        if isinstance(raw_body, bytes):
            return raw_body.decode("utf-8", errors="replace")
        return raw_body
