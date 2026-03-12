from typing import Any

from fastapi import HTTPException as FastAPIHTTPException
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common import messages

_CUSTOM_VALUE_ERROR_TRANSLATIONS = {
    "customer_id is required for customer users.": messages.CUSTOMER_ID_REQUIRED,
    "items must not be empty.": messages.ITEMS_MUST_NOT_BE_EMPTY,
    "Invalid Iranian mobile format.": messages.INVALID_IRANIAN_MOBILE,
}

_HTTP_EXCEPTION_DEVELOPER_MESSAGES = {
    messages.INVALID_AUTH_TOKEN: "JWT validation failed.",
    messages.INVALID_TOKEN_TYPE: "JWT type claim is not 'access'.",
    messages.TOKEN_SUBJECT_MISSING: "JWT subject claim is missing.",
    messages.TOKEN_SUBJECT_INVALID: "JWT subject claim is invalid.",
    messages.MISSING_AUTH_TOKEN: "Authorization bearer token was not provided.",
    messages.MISSING_ACCESS_CREDENTIALS: "Neither Authorization bearer token nor X-Bridge-Key was provided.",
    messages.ADMIN_ACCESS_REQUIRED: "Authenticated user does not have admin role.",
    messages.INVALID_BRIDGE_KEY: "Provided X-Bridge-Key header did not match the configured bridge API key.",
    messages.INVALID_IRANIAN_MOBILE: "Iranian mobile validator rejected the input value.",
    messages.USER_NOT_FOUND: "Requested user record was not found.",
    messages.USER_INACTIVE: "Requested user is inactive.",
    messages.USER_NOT_FOUND_OR_INACTIVE: "Active user record for the provided identifier was not found.",
    messages.MOBILE_ALREADY_EXISTS: "Unique constraint on user mobile was violated.",
    messages.OTP_DELIVERY_FAILED: "OTP delivery provider failed.",
    messages.OTP_INVALID: "Provided OTP code is invalid or already consumed.",
    messages.OTP_EXPIRED: "Provided OTP code is expired.",
    messages.TOO_MANY_OTP_REQUESTS: "OTP request rate limit exceeded.",
    messages.DATA_INTEGRITY_ERROR: "A database integrity constraint was violated.",
    messages.CUSTOMER_NOT_FOUND: "Requested customer record was not found.",
    messages.SERVICE_PROJECT_NOT_FOUND: "Requested service project record was not found.",
    messages.SERVICE_GROUP_NOT_FOUND: "Requested service group record was not found.",
    messages.SERVICE_NOT_FOUND: "Requested service record was not found.",
    messages.PROJECT_ID_CANNOT_BE_NULL: "The project reference was not provided.",
    messages.PROJECT_ID_INVALID: "The supplied project_id does not exist.",
    messages.GROUP_ID_CANNOT_BE_NULL: "The group reference was not provided.",
    messages.GROUP_ID_INVALID: "The supplied group_id does not exist.",
    messages.SERVICE_ID_INVALID: "The supplied service_id does not exist.",
    messages.SALE_PRICE_CANNOT_BE_NULL: "The sale_price field was explicitly set to null.",
    messages.DUPLICATE_SERVICE_ID_IN_PAYLOAD: "The payload contains duplicate service_id values.",
    messages.DUPLICATE_CUSTOMER_SERVICE_CONFIGURATION: (
        "A duplicate customer/service configuration violated a unique constraint."
    ),
    messages.INACTIVE_SERVICE_CANNOT_BE_ASSIGNED: "An inactive service was passed for a new customer config.",
    messages.CUSTOMER_SERVICE_CONFIG_NOT_FOUND: "Requested customer service config record was not found.",
    messages.CUSTOMER_ID_REQUIRED: "Customer users must include customer_id.",
    messages.CUSTOMER_ID_INVALID_OR_INACTIVE: "The supplied customer_id is invalid or inactive.",
    messages.ACTIVE_SUBSCRIPTION_NOT_FOUND: "No active subscription record exists.",
    messages.ACTIVE_SUBSCRIPTION_END_DATE_REQUIRED: "Creating an active subscription requires an end_date value.",
    messages.DUPLICATE_SUBSCRIPTION_MESSAGE_STATUS: "The payload contains duplicate subscription message statuses.",
    messages.ROUTE_NOT_FOUND: "Route not found.",
    messages.METHOD_NOT_ALLOWED: "HTTP method is not allowed for this route.",
}


def _contains_latin_text(value: str) -> bool:
    return any("a" <= char.lower() <= "z" for char in value)


def _translate_custom_value_error(error: dict[str, Any]) -> str:
    ctx = error.get("ctx")
    if isinstance(ctx, dict):
        raw_error = ctx.get("error")
        if isinstance(raw_error, ValueError) and raw_error.args:
            raw_message = str(raw_error.args[0])
            return _CUSTOM_VALUE_ERROR_TRANSLATIONS.get(raw_message, raw_message)
    raw_message = str(error.get("msg", ""))
    if raw_message.startswith("Value error, "):
        raw_message = raw_message.removeprefix("Value error, ")
    return _CUSTOM_VALUE_ERROR_TRANSLATIONS.get(raw_message, raw_message)


def _translate_validation_message(error: dict[str, Any]) -> str:
    error_type = error.get("type")
    ctx = error.get("ctx") or {}

    if error_type == "value_error":
        message = _translate_custom_value_error(error)
        if message:
            return message
    if error_type == "missing":
        return "این فیلد الزامی است."
    if error_type in {"string_type", "string_unicode"}:
        return "مقدار باید رشته باشد."
    if error_type in {"int_type", "int_parsing"}:
        return "مقدار باید عدد صحیح باشد."
    if error_type in {"float_type", "float_parsing"}:
        return "مقدار باید عدد باشد."
    if error_type in {"bool_type", "bool_parsing"}:
        return "مقدار باید درست یا نادرست باشد."
    if error_type == "list_type":
        return "مقدار باید فهرست باشد."
    if error_type == "dict_type":
        return "مقدار باید شیء باشد."
    if error_type == "greater_than_equal":
        return f"مقدار باید بزرگ تر یا مساوی {ctx.get('ge')} باشد."
    if error_type == "greater_than":
        return f"مقدار باید بزرگ تر از {ctx.get('gt')} باشد."
    if error_type == "less_than_equal":
        return f"مقدار باید کوچک تر یا مساوی {ctx.get('le')} باشد."
    if error_type == "less_than":
        return f"مقدار باید کوچک تر از {ctx.get('lt')} باشد."
    if error_type == "string_too_short":
        return f"طول متن باید حداقل {ctx.get('min_length')} کاراکتر باشد."
    if error_type == "string_too_long":
        return f"طول متن باید حداکثر {ctx.get('max_length')} کاراکتر باشد."
    if error_type in {"enum", "literal_error"}:
        return "مقدار واردشده معتبر نیست."
    if error_type == "extra_forbidden":
        return "ارسال فیلد اضافی مجاز نیست."

    raw_message = str(error.get("msg", ""))
    if not raw_message:
        return messages.INVALID_REQUEST
    if raw_message.startswith("Value error, "):
        raw_message = raw_message.removeprefix("Value error, ")
    if _contains_latin_text(raw_message):
        return messages.INVALID_REQUEST
    return raw_message


def _build_validation_developer_message(error: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", [])) or "request"
    raw_message = str(error.get("msg", "Validation error"))
    return f"{location}: {raw_message} (type={error.get('type')})"


def _normalize_http_exception_message(exc: FastAPIHTTPException | StarletteHTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        return str(detail["message"])
    if isinstance(detail, str):
        if detail == "Not Found":
            return messages.ROUTE_NOT_FOUND
        if detail == "Method Not Allowed":
            return messages.METHOD_NOT_ALLOWED
        return detail
    return messages.INVALID_REQUEST


def _normalize_http_exception_developer_message(
    exc: FastAPIHTTPException | StarletteHTTPException,
    message: str,
) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("developer_message"):
        return str(detail["developer_message"])
    if isinstance(detail, str):
        if detail in {"Not Found", "Method Not Allowed"}:
            return _HTTP_EXCEPTION_DEVELOPER_MESSAGES[message]
        return _HTTP_EXCEPTION_DEVELOPER_MESSAGES.get(message, detail)
    return _HTTP_EXCEPTION_DEVELOPER_MESSAGES.get(message, "Request failed.")


async def http_exception_handler(_, exc: FastAPIHTTPException | StarletteHTTPException) -> JSONResponse:
    message = _normalize_http_exception_message(exc)
    developer_message = _normalize_http_exception_developer_message(exc, message)
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=jsonable_encoder(
            {
                "message": message,
                "developer_message": developer_message,
                "detail": message,
            }
        ),
    )


async def request_validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    translated_errors = []
    for error in exc.errors():
        translated_error = {
            "loc": error.get("loc", []),
            "field": ".".join(str(part) for part in error.get("loc", [])[1:]) or None,
            "msg": _translate_validation_message(error),
            "type": error.get("type"),
            "developer_message": _build_validation_developer_message(error),
        }
        translated_errors.append(translated_error)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(
            {
                "message": messages.VALIDATION_ERROR_MESSAGE,
                "developer_message": "Request validation failed.",
                "detail": translated_errors,
            }
        ),
    )


async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(
            {
                "message": messages.INTERNAL_SERVER_ERROR,
                "developer_message": f"{exc.__class__.__name__}: {exc}",
                "detail": messages.INTERNAL_SERVER_ERROR,
            }
        ),
    )
