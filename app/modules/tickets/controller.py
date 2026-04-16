from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.dtos import CurrentUser
from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.common.security.dependencies import get_current_user
from app.modules.tickets.constants import TicketPriority, TicketStatus
from app.modules.tickets.dtos import (
    TicketAssignRequest,
    TicketCreate,
    TicketListOut,
    TicketOut,
    TicketStatusUpdate,
    TicketUpdate,
)
from app.modules.tickets.mappers import TicketMapper, get_ticket_mapper
from app.modules.tickets.service import TicketService, get_ticket_service

TICKETS_TAG = "tickets"

router = APIRouter(prefix="/tickets", tags=[TICKETS_TAG])


@router.post(
    "",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
    description="Create a new ticket for the authenticated user.",
    responses={
        201: {"description": "Ticket created."},
        401: {"description": "Authentication required."},
        403: {"description": "Local user context is required."},
        422: {"description": "Payload validation failed."},
    },
)
def create_ticket(
    payload: TicketCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.create(dto=payload, current_user=current_user)
    return mapper.to_out(ticket=ticket)


@router.get(
    "",
    response_model=TicketListOut,
    summary="List tickets",
    description="Return paginated tickets with optional filtering by status, priority, creator, assignee, and search.",
    responses={
        200: {"description": "Ticket list returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Access denied."},
    },
)
def list_tickets(
    response: Response,
    status_filter: TicketStatus | None = Query(default=None, alias="status", description="Filter by ticket status."),
    priority: TicketPriority | None = Query(default=None, description="Filter by ticket priority."),
    created_by_user_id: int | None = Query(default=None, description="Filter by creator user id."),
    assigned_to_user_id: int | None = Query(default=None, description="Filter by assignee user id."),
    search: str | None = Query(default=None, description="Search by ticket title or description."),
    sort_by: Literal["id", "status", "priority", "created_at", "updated_at", "resolved_at"] = Query(
        default="created_at",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketListOut:
    items, meta = service.list_tickets(
        current_user=current_user,
        status_filter=status_filter,
        priority_filter=priority,
        created_by_user_id=created_by_user_id,
        assigned_to_user_id=assigned_to_user_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return TicketListOut(
        items=[mapper.to_out(ticket=item) for item in items],
        total_page=meta.total_pages,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Get ticket",
    description="Return a single ticket by id if visible to the authenticated user.",
    responses={
        200: {"description": "Ticket returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Access denied."},
        404: {"description": "Ticket not found."},
    },
)
def get_ticket(
    ticket_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.get_visible_or_404(ticket_id=ticket_id, current_user=current_user)
    return mapper.to_out(ticket=ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Update ticket",
    description="Partially update ticket title, description, or priority.",
    responses={
        200: {"description": "Ticket updated."},
        401: {"description": "Authentication required."},
        403: {"description": "Access denied."},
        404: {"description": "Ticket not found."},
        422: {"description": "Payload validation failed."},
    },
)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.update(ticket_id=ticket_id, dto=payload, current_user=current_user)
    return mapper.to_out(ticket=ticket)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketOut,
    summary="Change ticket status",
    description="Change ticket status using the configured status transition rules. Admin only.",
    responses={
        200: {"description": "Ticket status updated."},
        401: {"description": "Authentication required."},
        403: {"description": "Admin access required."},
        404: {"description": "Ticket not found."},
        422: {"description": "Invalid status transition."},
    },
)
def change_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.change_status(
        ticket_id=ticket_id,
        dto=payload,
        current_user=current_user,
    )
    return mapper.to_out(ticket=ticket)


@router.patch(
    "/{ticket_id}/assign",
    response_model=TicketOut,
    summary="Assign ticket",
    description="Assign or unassign a ticket to a user. Admin only.",
    responses={
        200: {"description": "Ticket assignment updated."},
        401: {"description": "Authentication required."},
        403: {"description": "Admin access required."},
        404: {"description": "Ticket not found."},
        422: {"description": "Assignee validation failed."},
    },
)
def assign_ticket(
    ticket_id: int,
    payload: TicketAssignRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.assign(
        ticket_id=ticket_id,
        dto=payload,
        current_user=current_user,
    )
    return mapper.to_out(ticket=ticket)


@router.delete(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Deactivate ticket",
    description="Soft delete ticket by setting is_active=false. Admin only.",
    responses={
        200: {"description": "Ticket deactivated."},
        401: {"description": "Authentication required."},
        403: {"description": "Admin access required."},
        404: {"description": "Ticket not found."},
    },
)
def deactivate_ticket(
    ticket_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    mapper: TicketMapper = Depends(get_ticket_mapper),
) -> TicketOut:
    ticket = service.deactivate(ticket_id=ticket_id, current_user=current_user)
    return mapper.to_out(ticket=ticket)

