from datetime import UTC, datetime, timedelta
from secrets import randbelow

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import Base, get_db_session
from app.common.enums import OtpPurpose, UserRole
from app.common.security.jwt_service import JWTService, get_jwt_service
from app.common.services.otp_provider import OTPProvider, get_otp_provider
from app.modules.auth.dtos import AccessTokenOut, OtpRequestCreate, OtpRequestResult, OtpVerifyCreate
from app.modules.auth.mappers import AuthMapper, get_auth_mapper
from app.modules.auth.schemas import OTPCode


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
        otp_provider: OTPProvider,
        mapper: AuthMapper,
    ) -> None:
        self._db_session = db_session
        self._settings = settings
        self._jwt_service = jwt_service
        self._otp_provider = otp_provider
        self._mapper = mapper
        self._otp_policy = OTPPolicy(settings=settings)

    def request_otp(self, dto: OtpRequestCreate) -> OtpRequestResult:
        user_row = self._get_active_user_by_mobile(mobile=dto.mobile)
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive.",
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
        self._db_session.commit()
        delivery_result = self._otp_provider.send_login_otp(
            mobile=dto.mobile,
            otp_code=otp_code,
        )
        return OtpRequestResult(
            message=delivery_result.message,
            dev_otp=delivery_result.dev_otp,
        )

    def verify_otp(self, dto: OtpVerifyCreate) -> AccessTokenOut:
        otp_record = self._get_latest_unused_otp(mobile=dto.mobile, purpose=OtpPurpose.LOGIN)
        if otp_record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP is invalid.",
            )
        if otp_record.code != dto.otp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP is invalid.",
            )
        if self._is_expired(otp_record.expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP is expired.",
            )
        otp_record.is_used = True
        user_row = self._get_active_user_by_mobile(mobile=dto.mobile)
        if user_row is None:
            self._db_session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive.",
            )
        access_token = self._jwt_service.create_access_token(
            user_id=user_row["id"],
            mobile=user_row["mobile"],
            role=UserRole(user_row["role"]),
        )
        self._db_session.commit()
        return AccessTokenOut(
            access_token=access_token,
            token_type="bearer",
            user=self._mapper.from_user_row(user_row=user_row),
        )

    def _get_active_user_by_mobile(self, mobile: str):
        user_table = Base.metadata.tables["users"]
        return self._db_session.execute(
            select(
                user_table.c.id,
                user_table.c.full_name,
                user_table.c.mobile,
                user_table.c.role,
                user_table.c.municipality_id,
                user_table.c.is_active,
            ).where(
                user_table.c.mobile == mobile,
                user_table.c.is_active.is_(True),
            )
        ).mappings().first()

    def _enforce_rate_limit(self, mobile: str) -> None:
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
                detail="Too many OTP requests. Try again later.",
            )

    def _invalidate_previous_otps(self, mobile: str, purpose: OtpPurpose) -> None:
        self._db_session.execute(
            update(OTPCode)
            .where(
                OTPCode.mobile == mobile,
                OTPCode.purpose == purpose,
                OTPCode.is_used.is_(False),
            )
            .values(is_used=True)
        )

    def _get_latest_unused_otp(self, mobile: str, purpose: OtpPurpose) -> OTPCode | None:
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
        normalized_expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        return normalized_expires_at <= datetime.now(UTC)


def get_auth_service(
    db_session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    jwt_service: JWTService = Depends(get_jwt_service),
    otp_provider: OTPProvider = Depends(get_otp_provider),
    mapper: AuthMapper = Depends(get_auth_mapper),
) -> AuthService:
    return AuthService(
        db_session=db_session,
        settings=settings,
        jwt_service=jwt_service,
        otp_provider=otp_provider,
        mapper=mapper,
    )
