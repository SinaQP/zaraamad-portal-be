from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from jose import jwt

from app.common.config import Settings, get_settings
from app.common.dtos import CurrentUser
from app.common.messages import (
    CUSTOMER_BRIDGE_AUTH_FAILED,
    CUSTOMER_BRIDGE_INVALID_RESPONSE,
    CUSTOMER_BRIDGE_NOT_CONFIGURED,
    CUSTOMER_BRIDGE_REQUEST_FAILED,
    CUSTOMER_BRIDGE_UNAVAILABLE,
    LOCAL_USER_CONTEXT_REQUIRED,
)
from app.modules.customers.schemas import CustomerBridgeConfig
from app.modules.customers.service import (
    CustomerBridgeConfigService,
    CustomerScopedAccessPolicy,
    get_customer_bridge_config_service,
)

logger = logging.getLogger(__name__)


class CustomerPortalBridgePilotService:
    _PORTAL_BRIDGE_ALGORITHM = "RS256"
    _PILOT_ENDPOINT_PATH = "/internal/portal/pilot/ping"

    def __init__(
        self,
        *,
        bridge_config_service: CustomerBridgeConfigService,
        settings: Settings,
    ) -> None:
        self._bridge_config_service = bridge_config_service
        self._settings = settings
        self._access_policy = CustomerScopedAccessPolicy()

    def proxy_pilot_ping(
        self,
        *,
        customer_id: int,
        current_user: CurrentUser,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=LOCAL_USER_CONTEXT_REQUIRED,
            )

        customer, bridge_config = self._bridge_config_service.get_active(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer.id,
        )
        target_base_url = self._resolve_target_base_url(
            customer_id=customer.id,
            bridge_config=bridge_config,
        )
        signing_private_key = self._require_signing_private_key()
        bridge_id = str(bridge_config.customer_id)
        portal_token = self._create_portal_bridge_token(
            portal_user_id=current_user.id,
            bridge_id=bridge_id,
            customer_id=customer.id,
            signing_private_key=signing_private_key,
        )
        target_endpoint_url = f"{target_base_url}{self._PILOT_ENDPOINT_PATH}"
        logger.info(
            "Portal Zaraamad pilot proxy started user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s",
            current_user.id,
            customer.id,
            bridge_id,
            target_endpoint_url,
            correlation_id,
        )
        payload, upstream_status = self._fetch_pilot_payload(
            portal_token=portal_token,
            correlation_id=correlation_id,
            user_id=current_user.id,
            bridge_id=bridge_id,
            customer_id=customer.id,
            target_endpoint_url=target_endpoint_url,
        )
        logger.info(
            "Portal Zaraamad pilot proxy completed user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s",
            current_user.id,
            customer.id,
            bridge_id,
            target_endpoint_url,
            correlation_id,
            upstream_status,
        )
        return payload

    def _resolve_target_base_url(
        self,
        *,
        customer_id: int,
        bridge_config: CustomerBridgeConfig | None,
    ) -> str:
        missing_fields: list[str] = []
        if bridge_config is None:
            missing_fields.extend(["bridge_is_enabled", "bridge_base_url"])
        else:
            if not bridge_config.bridge_is_enabled:
                missing_fields.append("bridge_is_enabled")
            if not bridge_config.bridge_base_url:
                missing_fields.append("bridge_base_url")
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": CUSTOMER_BRIDGE_NOT_CONFIGURED,
                    "developer_message": (
                        "Portal to Zaraamad pilot proxy requires customer bridge "
                        f"fields {', '.join(missing_fields)} for customer {customer_id}."
                    ),
                },
            )
        return bridge_config.bridge_base_url.rstrip("/")

    def _require_signing_private_key(self) -> str:
        private_key = (self._settings.jwt_private_key or "").strip()
        if not private_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": CUSTOMER_BRIDGE_REQUEST_FAILED,
                    "developer_message": (
                        "Missing required JWT_PRIVATE_KEY configuration for Portal to Zaraamad signing."
                    ),
                },
            )
        return private_key.replace("\\n", "\n")

    def _create_portal_bridge_token(
        self,
        *,
        portal_user_id: int,
        bridge_id: str,
        customer_id: int,
        signing_private_key: str,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "iss": self._settings.jwt_issuer,
            "sub": f"user:{portal_user_id}",
            "bridge_id": bridge_id,
            "customer_id": str(customer_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._settings.jwt_ttl_seconds)).timestamp()),
            "jti": str(uuid4()),
        }
        try:
            return jwt.encode(
                payload,
                signing_private_key,
                algorithm=self._PORTAL_BRIDGE_ALGORITHM,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": CUSTOMER_BRIDGE_REQUEST_FAILED,
                    "developer_message": (
                        "Portal bridge JWT signing failed. "
                        f"Verify JWT_PRIVATE_KEY RS256 private key format. Error: {exc}"
                    ),
                },
            ) from exc

    def _fetch_pilot_payload(
        self,
        *,
        portal_token: str,
        correlation_id: str | None,
        user_id: int,
        bridge_id: str,
        customer_id: int,
        target_endpoint_url: str,
    ) -> tuple[dict[str, Any], int]:
        endpoint_url = target_endpoint_url
        upstream_status = status.HTTP_200_OK
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {portal_token}",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        request = Request(
            url=endpoint_url,
            headers=headers,
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._settings.bridge_request_timeout_seconds) as response:
                raw_response = self._decode_body(response.read())
                upstream_status = int(getattr(response, "status", status.HTTP_200_OK))
        except TimeoutError as exc:
            logger.warning(
                "Portal Zaraamad pilot proxy timeout user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s error=%s",
                user_id,
                customer_id,
                bridge_id,
                endpoint_url,
                correlation_id,
                status.HTTP_504_GATEWAY_TIMEOUT,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "message": CUSTOMER_BRIDGE_UNAVAILABLE,
                    "developer_message": (
                        "Portal timed out waiting for Zaraamad pilot endpoint "
                        f"{endpoint_url}: {exc}"
                    ),
                },
            ) from exc
        except HTTPError as exc:
            response_body = self._decode_body(exc.read())
            if exc.code in {401, 403}:
                logger.warning(
                    "Portal Zaraamad pilot proxy auth failure user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s",
                    user_id,
                    customer_id,
                    bridge_id,
                    endpoint_url,
                    correlation_id,
                    exc.code,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "message": CUSTOMER_BRIDGE_AUTH_FAILED,
                        "developer_message": (
                            "Zaraamad rejected portal JWT at "
                            f"{endpoint_url} with status {exc.code}. Body: "
                            f"{self._compact_text(response_body)}"
                        ),
                    },
                ) from exc
            logger.warning(
                "Portal Zaraamad pilot proxy upstream error user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s",
                user_id,
                customer_id,
                bridge_id,
                endpoint_url,
                correlation_id,
                exc.code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_REQUEST_FAILED,
                    "developer_message": (
                        "Portal to Zaraamad pilot proxy failed at "
                        f"{endpoint_url} with status {exc.code}. Body: "
                        f"{self._compact_text(response_body)}"
                        ),
                    },
                ) from exc
        except (URLError, OSError) as exc:
            upstream_status = (
                status.HTTP_504_GATEWAY_TIMEOUT
                if self._is_timeout_error(exc)
                else status.HTTP_502_BAD_GATEWAY
            )
            logger.warning(
                "Portal Zaraamad pilot proxy connection error user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s error=%s",
                user_id,
                customer_id,
                bridge_id,
                endpoint_url,
                correlation_id,
                upstream_status,
                exc,
            )
            raise HTTPException(
                status_code=upstream_status,
                detail={
                    "message": CUSTOMER_BRIDGE_UNAVAILABLE,
                    "developer_message": (
                        "Portal could not reach Zaraamad pilot endpoint "
                        f"{endpoint_url}: {exc}"
                    ),
                },
            ) from exc

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Portal Zaraamad pilot proxy invalid JSON user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s",
                user_id,
                customer_id,
                bridge_id,
                endpoint_url,
                correlation_id,
                upstream_status,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_INVALID_RESPONSE,
                    "developer_message": (
                        "Zaraamad pilot endpoint did not return JSON. "
                        f"Endpoint: {endpoint_url}"
                    ),
                },
            ) from exc

        if not isinstance(payload, dict):
            logger.warning(
                "Portal Zaraamad pilot proxy non-object JSON user_id=%s customer_id=%s bridge_id=%s target_url=%s correlation_id=%s upstream_status=%s",
                user_id,
                customer_id,
                bridge_id,
                endpoint_url,
                correlation_id,
                upstream_status,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_INVALID_RESPONSE,
                    "developer_message": (
                        "Zaraamad pilot endpoint returned non-object JSON. "
                        f"Endpoint: {endpoint_url}"
                    ),
                },
            )
        return payload, upstream_status

    def _decode_body(self, value: bytes | str) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _compact_text(self, value: str, *, max_length: int = 400) -> str:
        compact = " ".join(value.split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length]}..."

    def _is_timeout_error(self, exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        if isinstance(exc, URLError):
            return isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower()
        return "timed out" in str(exc).lower()


def get_customer_portal_bridge_pilot_service(
    customer_bridge_config_service: CustomerBridgeConfigService = Depends(get_customer_bridge_config_service),
    settings: Settings = Depends(get_settings),
) -> CustomerPortalBridgePilotService:
    return CustomerPortalBridgePilotService(
        bridge_config_service=customer_bridge_config_service,
        settings=settings,
    )
