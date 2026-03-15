from app.common.services.bridge_client import (
    BridgeSubscriptionConfigResult,
    BridgeSubscriptionMessageResult,
    BridgeSubscriptionResult,
)
from app.modules.subscriptions.dtos import (
    BridgeSubscriptionConfigOut,
    BridgeSubscriptionMessageOut,
    BridgeSubscriptionOut,
)


class SubscriptionBridgeMapper:
    def to_subscription_out(self, subscription: BridgeSubscriptionResult) -> BridgeSubscriptionOut:
        return BridgeSubscriptionOut(
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            grace_period_end_date=subscription.grace_period_end_date,
            is_active=subscription.is_active,
            status_message="",
        )

    def to_message_out(
        self,
        subscription_message: BridgeSubscriptionMessageResult,
    ) -> BridgeSubscriptionMessageOut:
        return BridgeSubscriptionMessageOut(
            status=subscription_message.status,
            message_template=subscription_message.message_template,
        )

    def to_messages_out(
        self,
        messages: list[BridgeSubscriptionMessageResult],
    ) -> list[BridgeSubscriptionMessageOut]:
        return [
            self.to_message_out(subscription_message=item)
            for item in messages
        ]

    def to_config_out(self, config: BridgeSubscriptionConfigResult) -> BridgeSubscriptionConfigOut:
        return BridgeSubscriptionConfigOut(
            subscription=self.to_subscription_out(subscription=config.subscription),
            messages=self.to_messages_out(messages=config.messages),
        )


def get_subscription_bridge_mapper() -> SubscriptionBridgeMapper:
    return SubscriptionBridgeMapper()
