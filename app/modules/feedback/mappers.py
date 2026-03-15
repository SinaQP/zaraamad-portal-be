from app.common.dtos import CurrentUser
from app.modules.feedback.dtos import FeedbackOut
from app.modules.feedback.schemas import Feedback
from app.modules.users.schemas import User


class FeedbackMapper:
    def to_out(
        self,
        *,
        feedback: Feedback,
        user: CurrentUser | User,
    ) -> FeedbackOut:
        return FeedbackOut(
            id=feedback.id,
            user_id=feedback.user_id,
            user_full_name=user.full_name,
            user_mobile=user.mobile,
            message=feedback.message,
            selected_options=list(feedback.selected_options),
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )


def get_feedback_mapper() -> FeedbackMapper:
    return FeedbackMapper()
