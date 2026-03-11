from typing import Any

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common import messages

_CUSTOM_VALUE_ERROR_TRANSLATIONS = {
    "Invalid Iranian mobile format.": messages.INVALID_IRANIAN_MOBILE,
    "municipality_id is required for customer users.": messages.CUSTOMER_MUNICIPALITY_REQUIRED,
    "items must not be empty.": messages.ITEMS_MUST_NOT_BE_EMPTY,
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
        return "اين فيلد الزامي است."
    if error_type in {"string_type", "string_unicode"}:
        return "مقدار بايد رشته باشد."
    if error_type in {"int_type", "int_parsing"}:
        return "مقدار بايد عدد صحيح باشد."
    if error_type in {"float_type", "float_parsing"}:
        return "مقدار بايد عدد باشد."
    if error_type in {"bool_type", "bool_parsing"}:
        return "مقدار بايد درست يا نادرست باشد."
    if error_type == "list_type":
        return "مقدار بايد فهرست باشد."
    if error_type == "dict_type":
        return "مقدار بايد شيء باشد."
    if error_type == "greater_than_equal":
        return f"مقدار بايد بزرگ تر يا مساوي {ctx.get('ge')} باشد."
    if error_type == "greater_than":
        return f"مقدار بايد بزرگ تر از {ctx.get('gt')} باشد."
    if error_type == "less_than_equal":
        return f"مقدار بايد کوچک تر يا مساوي {ctx.get('le')} باشد."
    if error_type == "less_than":
        return f"مقدار بايد کوچک تر از {ctx.get('lt')} باشد."
    if error_type == "string_too_short":
        return f"طول متن بايد حداقل {ctx.get('min_length')} کاراکتر باشد."
    if error_type == "string_too_long":
        return f"طول متن بايد حداکثر {ctx.get('max_length')} کاراکتر باشد."
    if error_type in {"enum", "literal_error"}:
        return "مقدار واردشده معتبر نيست."
    if error_type == "extra_forbidden":
        return "ارسال فيلد اضافي مجاز نيست."

    raw_message = str(error.get("msg", ""))
    if not raw_message:
        return messages.INVALID_REQUEST
    if raw_message.startswith("Value error, "):
        raw_message = raw_message.removeprefix("Value error, ")
    if _contains_latin_text(raw_message):
        return messages.INVALID_REQUEST
    return raw_message


async def request_validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    translated_errors = []
    for error in exc.errors():
        translated_error = dict(error)
        translated_error["msg"] = _translate_validation_message(error)
        translated_errors.append(translated_error)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder({"detail": translated_errors}),
    )
