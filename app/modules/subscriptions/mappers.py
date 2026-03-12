from app.modules.subscriptions.dtos import SubscriptionMessageOut, SubscriptionOut
from app.modules.subscriptions.schemas import Subscription, SubscriptionMessage


class SubscriptionMapper:
    def to_subscription_out(self, subscription: Subscription) -> SubscriptionOut:
        return SubscriptionOut(
            id=subscription.id,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            grace_period_end_date=subscription.grace_period_end_date,
            is_active=subscription.is_active,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )

    def to_subscription_message_out(
        self,
        subscription_message: SubscriptionMessage,
    ) -> SubscriptionMessageOut:
        return SubscriptionMessageOut(
            id=subscription_message.id,
            status=subscription_message.status,
            message_template=subscription_message.message_template,
            created_at=subscription_message.created_at,
            updated_at=subscription_message.updated_at,
        )


def get_subscription_mapper() -> SubscriptionMapper:
    return SubscriptionMapper()
