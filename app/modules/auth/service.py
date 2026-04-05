from datetime import UTC, datetime, timedelta
from secrets import randbelow

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import Base, get_db_session
from app.common.enums import OtpPurpose, UserRole
from app.common.messages import (
    DATA_INTEGRITY_ERROR,
    INVALID_CREDENTIALS,
    MOBILE_ALREADY_EXISTS,
    OTP_EXPIRED,
    OTP_INVALID,
    TOO_MANY_OTP_REQUESTS,
    USER_NOT_FOUND_OR_INACTIVE,
)
from app.common.security.jwt_service import JWTService, get_jwt_service
from app.common.security.password_service import PasswordService, get_password_service
from app.common.services.otp_provider import OTPProvider, OTPProviderError, get_otp_provider
from app.modules.auth.dtos import (
    AccessTokenOut,
    LoginCreate,
    OtpRequestCreate,
    OtpRequestResult,
    OtpVerifyCreate,
    PublicSignUpCreate,
)
from app.modules.auth.mappers import AuthMapper, get_auth_mapper
from app.modules.auth.schemas import OTPCode
from app.modules.users.schemas import User


class OTPPolicy:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def expires_after(self) -> timedelta:
        return timedelta(seconds=self._settings.otp_expire_seconds)

    @property
    def request_limit_count(self) -> int:
        return self._settings.otp_request_limit_count

    @property
    def request_limit_window(self) -> timedelta:
        return timedelta(seconds=self._settings.otp_request_limit_window_seconds)


class AuthService:
    def __init__(
        self,
        db_session: Session,
        settings: Settings,
        jwt_service: JWTService,
        password_service: PasswordService,
        otp_provider: OTPProvider,
        mapper: AuthMapper,
    ) -> None:
        self._db_session = db_session
        self._jwt_service = jwt_service
        self._password_service = password_service
        self._otp_provider = otp_provider
        self._mapper = mapper
        self._otp_policy = OTPPolicy(settings=settings)

    def request_otp(self, dto: OtpRequestCreate) -> OtpRequestResult:
        user_row = self._get_active_user_by_mobile(mobile=dto.mobile)
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=USER_NOT_FOUND_OR_INACTIVE,
            )
        self._enforce_rate_limit(mobile=dto.mobile)
        self._invalidate_previous_otps(mobile=dto.mobile, purpose=OtpPurpose.LOGIN)
        otp_code = self._generate_otp_code()
        now = datetime.now(UTC)
        otp_record = OTPCode(
            mobile=dto.mobile,
            code=otp_code,
            purpose=OtpPurpose.LOGIN,
            expires_at=now + self._otp_policy.expires_after,
            is_used=False,
        )
        self._db_session.add(otp_record)
        try:
            delivery_result = self._otp_provider.send_login_otp(
                mobile=dto.mobile,
                otp_code=otp_code,
            )
            self._db_session.commit()
        except OTPProviderError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.message,
            ) from exc
        return OtpRequestResult(
            message=delivery_result.message,
            dev_otp=delivery_result.dev_otp,
        )

    def sign_up_public(self, dto: PublicSignUpCreate) -> AccessTokenOut:
        user = User(
            full_name=dto.full_name,
            mobile=dto.mobile,
            role=UserRole.PUBLIC,
            customer_id=None,
            organization_name=dto.organization_name,
            organization_type=dto.organization_type,
            is_active=True,
        )
        self._db_session.add(user)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            self._raise_integrity_exception(exc)
        self._db_session.refresh(user)
        return self._build_access_token_response_for_user(user=user)

    def verify_otp(self, dto: OtpVerifyCreate) -> AccessTokenOut:
        otp_record = self._get_latest_unused_otp(
            mobile=dto.mobile,
            purpose=OtpPurpose.LOGIN,
        )
        if otp_record is None or otp_record.code != dto.otp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OTP_INVALID,
            )
        if self._is_expired(otp_record.expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OTP_EXPIRED,
            )
        otp_record.is_used = True
        user_row = self._get_active_user_by_mobile(mobile=dto.mobile)
        if user_row is None:
            self._db_session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=USER_NOT_FOUND_OR_INACTIVE,
            )
        self._db_session.commit()
        return self._build_access_token_response_for_user_row(user_row=user_row)

    def login(self, dto: LoginCreate) -> AccessTokenOut:
        user_row = self._get_active_user_by_mobile(mobile=dto.mobile)
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CREDENTIALS,
            )
        if not self._password_service.verify_password(
            password=dto.password,
            stored_password=user_row["password"],
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CREDENTIALS,
            )
        if self._password_service.is_legacy_plaintext_password(user_row["password"]):
            self._upgrade_legacy_password(user_id=user_row["id"], password=dto.password)
        return self._build_access_token_response_for_user_row(user_row=user_row)

    def _get_active_user_by_mobile(self, *, mobile: str):
        user_table = Base.metadata.tables["users"]
        return self._db_session.execute(
            select(
                user_table.c.id,
                user_table.c.full_name,
                user_table.c.mobile,
                user_table.c.role,
                user_table.c.customer_id,
                user_table.c.organization_name,
                user_table.c.organization_type,
                user_table.c.is_active,
                user_table.c.password,
            ).where(
                user_table.c.mobile == mobile,
                user_table.c.is_active.is_(True),
            )
        ).mappings().first()

    def _upgrade_legacy_password(self, *, user_id: int, password: str) -> None:
        user_table = Base.metadata.tables["users"]
        self._db_session.execute(
            update(user_table)
            .where(user_table.c.id == user_id)
            .values(password=self._password_service.hash_password(password=password))
        )
        self._db_session.commit()

    def _enforce_rate_limit(self, *, mobile: str) -> None:
        threshold = datetime.now(UTC) - self._otp_policy.request_limit_window
        request_count = self._db_session.execute(
            select(func.count(OTPCode.id)).where(
                OTPCode.mobile == mobile,
                OTPCode.purpose == OtpPurpose.LOGIN,
                OTPCode.created_at >= threshold,
            )
        ).scalar_one()
        if request_count >= self._otp_policy.request_limit_count:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=TOO_MANY_OTP_REQUESTS,
            )

    def _invalidate_previous_otps(self, *, mobile: str, purpose: OtpPurpose) -> None:
        self._db_session.execute(
            update(OTPCode)
            .where(
                OTPCode.mobile == mobile,
                OTPCode.purpose == purpose,
                OTPCode.is_used.is_(False),
            )
            .values(is_used=True)
        )

    def _get_latest_unused_otp(self, *, mobile: str, purpose: OtpPurpose) -> OTPCode | None:
        return self._db_session.execute(
            select(OTPCode)
            .where(
                OTPCode.mobile == mobile,
                OTPCode.purpose == purpose,
                OTPCode.is_used.is_(False),
            )
            .order_by(OTPCode.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _generate_otp_code(self) -> str:
        return str(randbelow(900000) + 100000)

    def _is_expired(self, expires_at: datetime) -> bool:
        normalized_expires_at = (
            expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        )
        return normalized_expires_at <= datetime.now(UTC)

    def _build_access_token_response_for_user_row(self, *, user_row) -> AccessTokenOut:
        access_token = self._jwt_service.create_access_token(
            user_id=user_row["id"],
            mobile=user_row["mobile"],
            role=UserRole(user_row["role"]),
        )
        return AccessTokenOut(
            access_token=access_token,
            token_type="bearer",
            user=self._mapper.from_user_row(user_row=user_row),
        )

    def _build_access_token_response_for_user(self, *, user: User) -> AccessTokenOut:
        access_token = self._jwt_service.create_access_token(
            user_id=user.id,
            mobile=user.mobile,
            role=user.role,
        )
        return AccessTokenOut(
            access_token=access_token,
            token_type="bearer",
            user=self._mapper.from_user(user=user),
        )

    def _raise_integrity_exception(self, exc: Exception) -> None:
        error_text = str(getattr(exc, "orig", exc)).lower()
        if "mobile" in error_text:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=MOBILE_ALREADY_EXISTS,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DATA_INTEGRITY_ERROR,
        ) from exc


def get_auth_service(
    db_session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    jwt_service: JWTService = Depends(get_jwt_service),
    password_service: PasswordService = Depends(get_password_service),
    otp_provider: OTPProvider = Depends(get_otp_provider),
    mapper: AuthMapper = Depends(get_auth_mapper),
) -> AuthService:
    return AuthService(
        db_session=db_session,
        settings=settings,
        jwt_service=jwt_service,
        password_service=password_service,
        otp_provider=otp_provider,
        mapper=mapper,
    )
