from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import SortOrder
from app.common.messages import DATA_INTEGRITY_ERROR
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.feedback.dtos import FeedbackCreate
from app.modules.feedback.schemas import Feedback
from app.modules.users.schemas import User


class FeedbackQueryBuilder:
    SORT_COLUMNS = {
        "id": Feedback.id,
        "user_id": Feedback.user_id,
        "created_at": Feedback.created_at,
        "updated_at": Feedback.updated_at,
    }

    def build_list_query(
        self,
        *,
        user_id: int | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Feedback, User]]:
        query = select(Feedback, User).join(User, User.id == Feedback.user_id)
        if user_id is not None:
            query = query.where(Feedback.user_id == user_id)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Feedback.message.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                    User.mobile.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Feedback.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Feedback.id.asc())
        return query


class FeedbackService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = FeedbackQueryBuilder()

    def create(
        self,
        *,
        dto: FeedbackCreate,
        current_user: CurrentUser,
    ) -> Feedback:
        feedback = Feedback(
            user_id=current_user.id,
            message=dto.message,
            selected_options=list(dto.selected_options),
        )
        self._db_session.add(feedback)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(feedback)
        return feedback

    def list_feedback(
        self,
        *,
        user_id: int | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[tuple[Feedback, User]], PaginationMeta]:
        query = self._query_builder.build_list_query(
            user_id=user_id,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        rows = self._db_session.execute(
            query.offset(pagination.offset).limit(pagination.page_size)
        ).all()
        items = [(row[0], row[1]) for row in rows]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta


def get_feedback_service(
    db_session: Session = Depends(get_db_session),
) -> FeedbackService:
    return FeedbackService(db_session=db_session)
