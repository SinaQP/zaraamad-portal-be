from datetime import date

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.common.messages import (
    ACTIVE_SUBSCRIPTION_END_DATE_REQUIRED,
    ACTIVE_SUBSCRIPTION_NOT_FOUND,
    DATA_INTEGRITY_ERROR,
    DUPLICATE_SUBSCRIPTION_MESSAGE_STATUS,
    ITEMS_MUST_NOT_BE_EMPTY,
)
from app.modules.subscriptions.dtos import SubscriptionCreate, SubscriptionMessageCreate, SubscriptionUpdate
from app.modules.subscriptions.schemas import Subscription, SubscriptionMessage


class SubscriptionService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def create_active(self, dto: SubscriptionCreate) -> Subscription:
        self._deactivate_active_subscriptions()
        subscription = Subscription(
            start_date=date.today(),
            end_date=dto.end_date,
            grace_period_end_date=None,
            is_active=True,
        )
        self._db_session.add(subscription)
        self._commit_with_integrity_guard()
        self._db_session.refresh(subscription)
        return subscription

    def get_active(self) -> Subscription:
        subscription = self._get_active_subscription()
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ACTIVE_SUBSCRIPTION_NOT_FOUND,
            )
        return subscription

    def update_active(self, dto: SubscriptionUpdate) -> Subscription:
        subscription = self._get_active_subscription()
        if subscription is None:
            return self._create_active_from_update(dto=dto)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(subscription, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(subscription)
        return subscription

    def list_messages(self) -> list[SubscriptionMessage]:
        return list(
            self._db_session.scalars(
                select(SubscriptionMessage).order_by(
                    SubscriptionMessage.status.asc(),
                    SubscriptionMessage.id.asc(),
                )
            ).all()
        )

    def upsert_messages(
        self,
        dtos: list[SubscriptionMessageCreate],
    ) -> list[SubscriptionMessage]:
        self._validate_message_payload(dtos=dtos)
        statuses = [item.status for item in dtos]
        existing_messages = list(
            self._db_session.scalars(
                select(SubscriptionMessage).where(SubscriptionMessage.status.in_(statuses))
            ).all()
        )
        existing_map = {item.status: item for item in existing_messages}

        for item in dtos:
            existing_message = existing_map.get(item.status)
            if existing_message is None:
                self._db_session.add(
                    SubscriptionMessage(
                        status=item.status,
                        message_template=item.message_template,
                    )
                )
                continue
            existing_message.message_template = item.message_template

        self._commit_with_integrity_guard()
        return self.list_messages()

    def _create_active_from_update(self, dto: SubscriptionUpdate) -> Subscription:
        if dto.end_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ACTIVE_SUBSCRIPTION_END_DATE_REQUIRED,
            )
        subscription = Subscription(
            start_date=date.today(),
            end_date=dto.end_date,
            grace_period_end_date=dto.grace_period_end_date,
            is_active=True if dto.is_active is None else dto.is_active,
        )
        self._db_session.add(subscription)
        self._commit_with_integrity_guard()
        self._db_session.refresh(subscription)
        return subscription

    def _get_active_subscription(self) -> Subscription | None:
        return self._db_session.scalar(
            select(Subscription)
            .where(Subscription.is_active.is_(True))
            .order_by(Subscription.id.desc())
            .limit(1)
        )

    def _deactivate_active_subscriptions(self) -> None:
        active_subscriptions = list(
            self._db_session.scalars(
                select(Subscription).where(Subscription.is_active.is_(True))
            ).all()
        )
        for subscription in active_subscriptions:
            subscription.is_active = False

    def _validate_message_payload(self, dtos: list[SubscriptionMessageCreate]) -> None:
        if len(dtos) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ITEMS_MUST_NOT_BE_EMPTY,
            )

        statuses = [item.status for item in dtos]
        if len(statuses) != len(set(statuses)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=DUPLICATE_SUBSCRIPTION_MESSAGE_STATUS,
            )

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


def get_subscription_service(
    db_session: Session = Depends(get_db_session),
) -> SubscriptionService:
    return SubscriptionService(db_session=db_session)
