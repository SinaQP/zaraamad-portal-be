"""
Portable SMS service extracted from the current Zaraamad BE project.

Source mapping in this repository:
- apps/zarvand/otp.py
- apps/zarvand/zarand_sms_panel.py

Behavior preserved from the source project:
- If SMS_PANEL_TYPE == "stage", send with the PayamSMS REST endpoint.
- Otherwise, send with the Zarand SMS panel endpoint.
- The OTP message helper keeps the same message format used in otp.py.

This file is intentionally framework-agnostic so it can be copied into
another Python project without Django dependencies.

OTP behavior in the source project (documented here for handoff only):
- Entry point: POST /zarvand/send-verification-code/
- Verification: POST /zarvand/validate-sms-code/
- Person lookup is done by national_code.
- Mobile number is taken from request.mobile_number; otherwise from person.mobile_Number.
- OTP is stored in Cor].[OTP with a one-to-one relation to the person.
- The source project uses HOTP with a fixed counter value: 2548.
- Resend is blocked for 120 seconds unless the mobile number changes.
- After 3 failed verification attempts, validation is blocked for 15 minutes.
- This portable file does not implement DB-backed OTP persistence or validation.

Required third-party dependency:
- requests

Environment variables:

Common:
- SMS_PANEL_TYPE=stage          -> use PayamSMS REST provider
- FRONTEND_BASE_URL=https://... -> used only by build_login_otp_message()

PayamSMS provider ("stage"):
- API_ORGANIZATION
- API_USERNAME
- API_PASSWORD

Zarand panel provider (default when SMS_PANEL_TYPE != "stage"):
- ZARAND_SMS_PANEL_USERNAME
- ZARAND_SMS_PANEL_PASSWORD
- ZARAND_SMS_PANEL_FROMNUM
- ZARAND_SMS_PANEL_BASE_URL

Example:
    service = SmsService()
    result = service.send_sms(
        recipient="09123456789",
        message="Test message",
        customer_id=123,
    )
    if not result.ok:
        print(result.message)
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests


PAYAMSMS_API_URL = "https://payamsms.com/services/rest/index.php"
PAYAMSMS_DEFAULT_SENDER = "9820002739006"


@dataclass(frozen=True)
class SmsSendResult:
    ok: bool
    status_code: int
    message: str
    provider: str
    raw_response: Optional[str] = None


class SmsConfigError(ValueError):
    pass


class SmsService:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 15):
        self.session = session or requests.Session()
        self.timeout = timeout

    def send_sms(
        self,
        recipient: str,
        message: str,
        customer_id: Optional[int] = None,
    ) -> SmsSendResult:
        sms_panel_type = os.environ.get("SMS_PANEL_TYPE", "")
        if sms_panel_type == "stage":
            return self._send_with_payamsms(
                recipient=recipient,
                message=message,
                customer_id=customer_id,
            )
        return self._send_with_zarand_panel(recipient=recipient, message=message)

    def _send_with_zarand_panel(self, recipient: str, message: str) -> SmsSendResult:
        username = os.getenv("ZARAND_SMS_PANEL_USERNAME")
        password = os.getenv("ZARAND_SMS_PANEL_PASSWORD")
        from_num = os.getenv("ZARAND_SMS_PANEL_FROMNUM")
        base_url = os.getenv("ZARAND_SMS_PANEL_BASE_URL")

        if not all([username, password, from_num, base_url]):
            raise SmsConfigError(
                "Missing Zarand SMS panel env vars: "
                "ZARAND_SMS_PANEL_USERNAME, ZARAND_SMS_PANEL_PASSWORD, "
                "ZARAND_SMS_PANEL_FROMNUM, ZARAND_SMS_PANEL_BASE_URL"
            )

        params = {
            "username": username,
            "password": password,
            "message": message,
            "fromNumber": from_num,
            "toNumber": recipient,
        }

        url = f"{base_url}?{urlencode(params)}"
        response = self.session.get(url, timeout=self.timeout)

        if response.status_code != 200:
            return SmsSendResult(
                ok=False,
                status_code=response.status_code,
                message="SMS was not sent by Zarand panel.",
                provider="zarand_panel",
                raw_response=response.text,
            )

        try:
            root = ET.fromstring(response.text)
            string_element = root.find(".//{http://tempuri.org/}string")
            if string_element is not None:
                return SmsSendResult(
                    ok=True,
                    status_code=200,
                    message="SMS sent successfully.",
                    provider="zarand_panel",
                    raw_response=response.text,
                )
        except ET.ParseError:
            return SmsSendResult(
                ok=False,
                status_code=500,
                message="Zarand panel returned invalid XML.",
                provider="zarand_panel",
                raw_response=response.text,
            )

        return SmsSendResult(
            ok=False,
            status_code=500,
            message="SMS was not accepted by Zarand panel.",
            provider="zarand_panel",
            raw_response=response.text,
        )

    def _send_with_payamsms(
        self,
        recipient: str,
        message: str,
        customer_id: Optional[int] = None,
    ) -> SmsSendResult:
        organization = os.environ.get("API_ORGANIZATION")
        username = os.environ.get("API_USERNAME")
        password = os.environ.get("API_PASSWORD")

        if not all([organization, username, password]):
            raise SmsConfigError(
                "Missing PayamSMS env vars: "
                "API_ORGANIZATION, API_USERNAME, API_PASSWORD"
            )

        payload = {
            "organization": organization,
            "username": username,
            "password": password,
            "method": "send",
            "messages": [
                {
                    "sender": PAYAMSMS_DEFAULT_SENDER,
                    "recipient": recipient,
                    "body": message,
                    "customerId": customer_id,
                }
            ],
        }

        response = self.session.post(
            PAYAMSMS_API_URL,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code != 200:
            return SmsSendResult(
                ok=False,
                status_code=response.status_code,
                message="SMS was not sent by PayamSMS.",
                provider="payamsms",
                raw_response=response.text,
            )

        return SmsSendResult(
            ok=True,
            status_code=200,
            message="SMS sent successfully.",
            provider="payamsms",
            raw_response=response.text,
        )


def build_login_otp_message(otp_code: str, frontend_base_url: Optional[str] = None) -> str:
    """
    Keeps the same OTP message format used in apps/zarvand/otp.py.
    """

    frontend_url = frontend_base_url or os.getenv("FRONTEND_BASE_URL", "")
    cleaned_frontend_url = (
        re.sub(r"^https?://", "", frontend_url) if frontend_url else ""
    )
    return (
        f"کد تایید شما برای ورود به سامانه زروند: {otp_code}\n"
        f"@{cleaned_frontend_url}#{otp_code}"
    )