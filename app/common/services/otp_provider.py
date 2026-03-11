from dataclasses import dataclass

from fastapi import Depends, status

from app.common.config import Settings, get_settings
from app.common.messages import OTP_DELIVERY_FAILED, OTP_GENERATED_TEMPLATE
from app.common.services.sms_service import (
    LoginOtpMessageBuilder,
    SmsConfigError,
    SmsDeliveryError,
    SmsService,
)


@dataclass(frozen=True)
class OTPDeliveryResult:
    message: str
    dev_otp: str | None = None


class OTPProviderError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.message = OTP_DELIVERY_FAILED
        super().__init__(self.message)


class OTPProviderConfigurationError(OTPProviderError):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OTPProviderDeliveryError(OTPProviderError):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class OTPProvider:
    def send_login_otp(self, mobile: str, otp_code: str) -> OTPDeliveryResult:
        raise NotImplementedError


class MockOTPProvider(OTPProvider):
    def __init__(self, dev_mode: bool) -> None:
        self._dev_mode = dev_mode

    def send_login_otp(self, mobile: str, otp_code: str) -> OTPDeliveryResult:
        if self._dev_mode:
            return OTPDeliveryResult(
                message=OTP_GENERATED_TEMPLATE.format(mobile=mobile),
                dev_otp=otp_code,
            )
        return OTPDeliveryResult(message=OTP_GENERATED_TEMPLATE.format(mobile=mobile))


class SmsOTPProvider(OTPProvider):
    def __init__(
        self,
        sms_service: SmsService,
        message_builder: LoginOtpMessageBuilder,
    ) -> None:
        self._sms_service = sms_service
        self._message_builder = message_builder

    def send_login_otp(self, mobile: str, otp_code: str) -> OTPDeliveryResult:
        message = self._message_builder.build(otp_code=otp_code)
        try:
            self._sms_service.send_sms(
                recipient=mobile,
                message=message,
            )
        except SmsConfigError as exc:
            raise OTPProviderConfigurationError() from exc
        except SmsDeliveryError as exc:
            raise OTPProviderDeliveryError() from exc
        return OTPDeliveryResult(message=OTP_GENERATED_TEMPLATE.format(mobile=mobile))


def get_otp_provider(settings: Settings = Depends(get_settings)) -> OTPProvider:
    if settings.otp_dev_mode:
        return MockOTPProvider(dev_mode=True)
    return SmsOTPProvider(
        sms_service=SmsService(settings=settings),
        message_builder=LoginOtpMessageBuilder(),
    )
