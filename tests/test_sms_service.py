from __future__ import annotations

import pytest

from app.common.config import Settings
from app.common.services import sms_service as sms_service_module
from app.common.services.sms_service import SmsDeliveryError, SmsService


class FakeHTTPResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb


def test_stage_provider_rejects_explicit_failure_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        del request, timeout
        return FakeHTTPResponse(status=200, body='{"status":"failed"}')

    monkeypatch.setattr(sms_service_module, "urlopen", fake_urlopen)
    settings = Settings(
        _env_file=None,
        otp_dev_mode=False,
        sms_panel_organization="org",
        sms_panel_username="user",
        sms_panel_password="pass",
        sms_panel_sender="9820002739006",
        sms_api_url="https://sms.example.com/api",
    )

    service = SmsService(settings=settings)

    with pytest.raises(SmsDeliveryError) as exc_info:
        service.send_sms(recipient="09120000000", message="test")

    assert exc_info.value.result.status_code == 200
    assert exc_info.value.result.raw_response == '{"status":"failed"}'
