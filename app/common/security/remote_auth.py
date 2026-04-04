from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.config import Settings, get_settings
from app.common.messages import (
    FORM_ADMIN_ACCESS_REQUIRED,
    INVALID_AUTH_TOKEN,
    MISSING_AUTH_TOKEN,
    REMOTE_AUTH_INVALID_RESPONSE,
    REMOTE_AUTH_UNAVAILABLE,
)

remote_bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Enter the Zaraamad access token that is validated through remote introspection.",
)

_FORM_ADMIN_PERMISSION_CODES = frozenset(
    {
        "form.admin",
        "forms.admin",
        "form_service.admin",
        "form-service.admin",
    }
)
_FORM_ADMIN_ROLES = frozenset(
    {
        "admin",
        "staff",
        "superuser",
        "form_admin",
        "form-admin",
    }
)
_REMOTE_AUTH_ROLE_KEYS = ("role", "user_role", "userRole")
_REMOTE_AUTH_PERMISSION_KEYS = (
    "permissions",
    "permission_codes",
    "permissionCodes",
    "perms",
)
_REMOTE_AUTH_USER_ID_KEYS = ("user_id", "userId", "id", "pk")
_REMOTE_AUTH_USER_NAME_KEYS = ("user_name", "userName", "full_name", "fullName", "name")
_REMOTE_AUTH_MUNICIPALITY_CODE_KEYS = (
    "municipality_code",
    "municipalityCode",
)
_REMOTE_AUTH_MUNICIPALITY_KEYS = ("municipality",)


@dataclass(frozen=True)
class RemoteAuthenticatedUser:
    user_id: int
    user_name: str | None
    municipality_code: str | None
    municipality: Any | None
    raw_payload: dict[str, Any]
    is_introspection_bypassed: bool = False


@dataclass(frozen=True)
class RemoteAuthCacheEntry:
    user: RemoteAuthenticatedUser
    expires_at: float


class RemoteAuthUnauthorizedError(Exception):
    def __init__(self, *, status_code: int, response_body: str | None = None) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Remote introspection rejected the bearer token with status {status_code}.")


class RemoteAuthConnectionError(Exception):
    pass


class RemoteAuthInvalidResponseError(Exception):
    pass


class RemoteAuthCache:
    def __init__(self) -> None:
        self._entries: dict[str, RemoteAuthCacheEntry] = {}
        self._lock = Lock()

    def get(self, token: str) -> RemoteAuthenticatedUser | None:
        cache_key = self._build_cache_key(token=token)
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                return None
            if entry.expires_at <= monotonic():
                self._entries.pop(cache_key, None)
                return None
            return entry.user

    def set(
        self,
        *,
        token: str,
        user: RemoteAuthenticatedUser,
        ttl_seconds: int,
    ) -> None:
        cache_key = self._build_cache_key(token=token)
        with self._lock:
            self._entries[cache_key] = RemoteAuthCacheEntry(
                user=user,
                expires_at=monotonic() + ttl_seconds,
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _build_cache_key(self, *, token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()


class RemoteAuthIntrospectionClient:
    def introspect(
        self,
        *,
        url: str,
        authorization_header: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        request = Request(
            url=url,
            headers={
                "Accept": "application/json",
                "Authorization": authorization_header,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_response = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403}:
                raise RemoteAuthUnauthorizedError(
                    status_code=exc.code,
                    response_body=response_body,
                ) from exc
            raise RemoteAuthConnectionError(
                f"Remote introspection request failed with status {exc.code}."
            ) from exc
        except (TimeoutError, URLError, OSError) as exc:
            raise RemoteAuthConnectionError(str(exc)) from exc

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RemoteAuthInvalidResponseError(
                "Remote introspection response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise RemoteAuthInvalidResponseError(
                "Remote introspection response must be a JSON object."
            )
        return payload


class RemoteAuthPayloadExtractor:
    def extract(self, payload: dict[str, Any]) -> RemoteAuthenticatedUser:
        candidate_payloads = self._build_candidate_payloads(payload=payload)
        user_id = self._extract_required_user_id(candidate_payloads=candidate_payloads)
        return RemoteAuthenticatedUser(
            user_id=user_id,
            user_name=self._extract_optional_string(
                candidate_payloads=candidate_payloads,
                field_names=_REMOTE_AUTH_USER_NAME_KEYS,
            ),
            municipality_code=self._extract_optional_municipality_code(
                candidate_payloads=candidate_payloads
            ),
            municipality=self._extract_optional_municipality(
                candidate_payloads=candidate_payloads
            ),
            raw_payload=payload,
        )

    def _build_candidate_payloads(
        self,
        *,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidates = [payload]
        for key in ("data", "user", "result"):
            nested_payload = payload.get(key)
            if isinstance(nested_payload, dict):
                candidates.append(nested_payload)
                nested_user = nested_payload.get("user")
                if isinstance(nested_user, dict):
                    candidates.append(nested_user)
        return candidates

    def _extract_required_user_id(
        self,
        *,
        candidate_payloads: list[dict[str, Any]],
    ) -> int:
        for candidate in candidate_payloads:
            for field_name in _REMOTE_AUTH_USER_ID_KEYS:
                raw_value = candidate.get(field_name)
                if raw_value in (None, ""):
                    continue
                try:
                    return int(raw_value)
                except (TypeError, ValueError):
                    continue
        raise RemoteAuthInvalidResponseError(
            "Remote introspection response did not contain a valid user identifier."
        )

    def _extract_optional_string(
        self,
        *,
        candidate_payloads: list[dict[str, Any]],
        field_names: tuple[str, ...],
    ) -> str | None:
        for candidate in candidate_payloads:
            for field_name in field_names:
                raw_value = candidate.get(field_name)
                if raw_value is None:
                    continue
                if isinstance(raw_value, str):
                    normalized_value = raw_value.strip()
                    return normalized_value or None
        return None

    def _extract_optional_municipality_code(
        self,
        *,
        candidate_payloads: list[dict[str, Any]],
    ) -> str | None:
        direct_code = self._extract_optional_string(
            candidate_payloads=candidate_payloads,
            field_names=_REMOTE_AUTH_MUNICIPALITY_CODE_KEYS,
        )
        if direct_code is not None:
            return direct_code

        municipality = self._extract_optional_municipality(
            candidate_payloads=candidate_payloads
        )
        if isinstance(municipality, dict):
            for field_name in ("code", "municipality_code", "municipalityCode"):
                raw_value = municipality.get(field_name)
                if isinstance(raw_value, str) and raw_value.strip():
                    return raw_value.strip()
        if isinstance(municipality, str):
            normalized_value = municipality.strip()
            return normalized_value or None
        return None

    def _extract_optional_municipality(
        self,
        *,
        candidate_payloads: list[dict[str, Any]],
    ) -> Any | None:
        for candidate in candidate_payloads:
            for field_name in _REMOTE_AUTH_MUNICIPALITY_KEYS:
                raw_value = candidate.get(field_name)
                if raw_value is None:
                    continue
                return raw_value
        return None


class RemoteBearerAuthenticator:
    def __init__(
        self,
        *,
        settings: Settings,
        introspection_client: RemoteAuthIntrospectionClient,
        payload_extractor: RemoteAuthPayloadExtractor,
        cache: RemoteAuthCache,
    ) -> None:
        self._settings = settings
        self._introspection_client = introspection_client
        self._payload_extractor = payload_extractor
        self._cache = cache

    def authenticate(self, token: str) -> RemoteAuthenticatedUser:
        cached_user = self._cache.get(token=token)
        if cached_user is not None:
            return cached_user

        try:
            payload = self._introspection_client.introspect(
                url=self._settings.auth_introspection_url,
                authorization_header=f"Bearer {token}",
                timeout_seconds=self._settings.auth_introspection_timeout,
            )
            user = self._payload_extractor.extract(payload=payload)
        except RemoteAuthUnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "message": INVALID_AUTH_TOKEN,
                    "developer_message": (
                        f"Remote introspection rejected the bearer token with status {exc.status_code}."
                    ),
                },
            ) from exc
        except RemoteAuthInvalidResponseError as exc:
            if self._settings.auth_introspection_fail_open:
                return self._build_fail_open_user()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": REMOTE_AUTH_INVALID_RESPONSE,
                    "developer_message": str(exc),
                },
            ) from exc
        except RemoteAuthConnectionError as exc:
            if self._settings.auth_introspection_fail_open:
                return self._build_fail_open_user()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": REMOTE_AUTH_UNAVAILABLE,
                    "developer_message": f"Remote introspection request failed: {exc}",
                },
            ) from exc

        self._cache.set(
            token=token,
            user=user,
            ttl_seconds=self._settings.auth_introspection_cache_ttl,
        )
        return user

    def _build_fail_open_user(self) -> RemoteAuthenticatedUser:
        return RemoteAuthenticatedUser(
            user_id=0,
            user_name=None,
            municipality_code=None,
            municipality=None,
            raw_payload={"auth_bypass": True},
            is_introspection_bypassed=True,
        )


class RemoteFormAdminAuthorizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def authorize(self, user: RemoteAuthenticatedUser) -> None:
        if self._settings.is_form_admin:
            return

        if self._has_form_admin_flag(payload=user.raw_payload):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=FORM_ADMIN_ACCESS_REQUIRED,
        )

    def _has_form_admin_flag(self, *, payload: dict[str, Any]) -> bool:
        if self._read_truthy_flag(payload=payload, field_names=("is_form_admin", "isFormAdmin")):
            return True
        if self._read_truthy_flag(payload=payload, field_names=("is_staff", "isStaff")):
            return True
        if self._read_truthy_flag(payload=payload, field_names=("is_superuser", "isSuperuser")):
            return True

        role = self._read_string(
            payload=payload,
            field_names=_REMOTE_AUTH_ROLE_KEYS,
        )
        if role is not None and role.lower() in _FORM_ADMIN_ROLES:
            return True

        for field_name in _REMOTE_AUTH_PERMISSION_KEYS:
            raw_permissions = payload.get(field_name)
            if isinstance(raw_permissions, list):
                normalized_permissions = {
                    item.strip().lower()
                    for item in raw_permissions
                    if isinstance(item, str) and item.strip()
                }
                if normalized_permissions.intersection(_FORM_ADMIN_PERMISSION_CODES):
                    return True

        nested_payloads = []
        for key in ("data", "user", "result"):
            nested_payload = payload.get(key)
            if isinstance(nested_payload, dict):
                nested_payloads.append(nested_payload)
        for nested_payload in nested_payloads:
            if self._has_form_admin_flag(payload=nested_payload):
                return True
        return False

    def _read_truthy_flag(
        self,
        *,
        payload: dict[str, Any],
        field_names: tuple[str, ...],
    ) -> bool:
        for field_name in field_names:
            raw_value = payload.get(field_name)
            if isinstance(raw_value, bool):
                return raw_value
        return False

    def _read_string(
        self,
        *,
        payload: dict[str, Any],
        field_names: tuple[str, ...],
    ) -> str | None:
        for field_name in field_names:
            raw_value = payload.get(field_name)
            if isinstance(raw_value, str) and raw_value.strip():
                return raw_value.strip()
        return None


_remote_auth_cache = RemoteAuthCache()


def get_remote_auth_cache() -> RemoteAuthCache:
    return _remote_auth_cache


def get_remote_auth_introspection_client() -> RemoteAuthIntrospectionClient:
    return RemoteAuthIntrospectionClient()


def get_remote_auth_payload_extractor() -> RemoteAuthPayloadExtractor:
    return RemoteAuthPayloadExtractor()


def get_remote_bearer_authenticator(
    settings: Settings = Depends(get_settings),
    introspection_client: RemoteAuthIntrospectionClient = Depends(
        get_remote_auth_introspection_client
    ),
    payload_extractor: RemoteAuthPayloadExtractor = Depends(
        get_remote_auth_payload_extractor
    ),
    cache: RemoteAuthCache = Depends(get_remote_auth_cache),
) -> RemoteBearerAuthenticator:
    return RemoteBearerAuthenticator(
        settings=settings,
        introspection_client=introspection_client,
        payload_extractor=payload_extractor,
        cache=cache,
    )


def get_remote_form_admin_authorizer(
    settings: Settings = Depends(get_settings),
) -> RemoteFormAdminAuthorizer:
    return RemoteFormAdminAuthorizer(settings=settings)


def get_remote_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(remote_bearer_scheme),
    authenticator: RemoteBearerAuthenticator = Depends(get_remote_bearer_authenticator),
) -> RemoteAuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_AUTH_TOKEN,
        )
    return authenticator.authenticate(token=credentials.credentials)


def get_optional_remote_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(remote_bearer_scheme),
    authenticator: RemoteBearerAuthenticator = Depends(get_remote_bearer_authenticator),
) -> RemoteAuthenticatedUser | None:
    if credentials is None:
        return None
    return authenticator.authenticate(token=credentials.credentials)


def require_remote_form_admin(
    current_user: RemoteAuthenticatedUser = Depends(get_remote_authenticated_user),
    authorizer: RemoteFormAdminAuthorizer = Depends(get_remote_form_admin_authorizer),
) -> RemoteAuthenticatedUser:
    authorizer.authorize(user=current_user)
    return current_user
