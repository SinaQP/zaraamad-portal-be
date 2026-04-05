from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"
    PUBLIC = "public"


class OtpPurpose(str, Enum):
    LOGIN = "login"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SubscriptionMessageStatus(str, Enum):
    EXPIRED = "expired"
    GRACE = "grace"
    NEAR_EXPIRY = "near_expiry"
