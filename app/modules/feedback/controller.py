from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.dtos import CurrentUser
from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.common.security.dependencies import get_current_user, require_admin
from app.modules.feedback.dtos import FeedbackCreate, FeedbackListOut, FeedbackOut
from app.modules.feedback.mappers import FeedbackMapper, get_feedback_mapper
from app.modules.feedback.service import FeedbackService, get_feedback_service

FEEDBACK_TAG = "feedback"

router = APIRouter(prefix="/feedback", tags=[FEEDBACK_TAG])


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create feedback",
    description="Store free-text feedback and selected dynamic option labels for the authenticated user.",
    responses={
        201: {"description": "Feedback created."},
        401: {"description": "Authentication required."},
        422: {"description": "Payload validation failed."},
    },
)
def create_feedback(
    payload: FeedbackCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
    mapper: FeedbackMapper = Depends(get_feedback_mapper),
) -> FeedbackOut:
    feedback = service.create(
        dto=payload,
        current_user=current_user,
    )
    return mapper.to_out(
        feedback=feedback,
        user=current_user,
    )


@router.get(
    "",
    response_model=FeedbackListOut,
    summary="List feedback",
    description="Return stored feedback records for administrative review.",
    responses={
        200: {"description": "Feedback list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_feedback(
    response: Response,
    user_id: int | None = Query(default=None, description="Filter by user id."),
    search: str | None = Query(
        default=None,
        description="Search by feedback message, user full name, or user mobile.",
    ),
    sort_by: Literal["id", "user_id", "created_at", "updated_at"] = Query(
        default="created_at",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: FeedbackService = Depends(get_feedback_service),
    mapper: FeedbackMapper = Depends(get_feedback_mapper),
) -> FeedbackListOut:
    rows, meta = service.list_feedback(
        user_id=user_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return FeedbackListOut(
        items=[
            mapper.to_out(
                feedback=feedback,
                user=user,
            )
            for feedback, user in rows
        ],
        total_page=meta.total_pages,
    )
