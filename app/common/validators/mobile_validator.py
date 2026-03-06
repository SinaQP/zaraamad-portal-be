import re


class IranianMobileValidator:
    _MOBILE_PATTERN = re.compile(r"^(?:\+98|98|0)?9\d{9}$")

    def normalize(self, value: str) -> str:
        normalized = value.strip().replace(" ", "")
        if not self._MOBILE_PATTERN.match(normalized):
            raise ValueError("Invalid Iranian mobile format.")
        if normalized.startswith("+98"):
            return f"0{normalized[3:]}"
        if normalized.startswith("98"):
            return f"0{normalized[2:]}"
        if normalized.startswith("9"):
            return f"0{normalized}"
        return normalized


def get_mobile_validator() -> IranianMobileValidator:
    return IranianMobileValidator()
