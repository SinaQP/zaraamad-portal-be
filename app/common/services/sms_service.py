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
            f"کد تایید ورود شما: {otp_code}\n"
            "این کد را در اختیار دیگران قرار ندهید."
        )


class SmsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_sms(self, recipient: str, message: str) -> SmsSendResult:
        config = self._get_panel_config()
        request = self._build_request(
            config=config,
            recipient=recipient,
            message=message,
        )
        result = self._perform_request(request=request)
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

    def _decode_response_body(self, raw_body: bytes | str) -> str:
        if isinstance(raw_body, bytes):
            return raw_body.decode("utf-8", errors="replace")
        return raw_body
