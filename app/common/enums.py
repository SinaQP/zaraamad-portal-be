from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"


class OtpPurpose(str, Enum):
    LOGIN = "login"
