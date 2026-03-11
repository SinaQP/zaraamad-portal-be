from app.common.config import get_settings
from app.common.messages import OTP_GENERATED_TEMPLATE


class OTPDeliveryResult:
    def __init__(self, message: str, dev_otp: str | None = None) -> None:
        self.message = message
        self.dev_otp = dev_otp


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


def get_otp_provider() -> OTPProvider:
    return MockOTPProvider(dev_mode=get_settings().otp_dev_mode)
