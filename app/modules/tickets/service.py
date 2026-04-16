from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import SortOrder, UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    DATA_INTEGRITY_ERROR,
    LOCAL_USER_CONTEXT_REQUIRED,
    TICKET_ACCESS_DENIED,
    TICKET_ASSIGNEE_INVALID,
    TICKET_INVALID_STATUS_TRANSITION,
    TICKET_NOT_FOUND,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.tickets.constants import TicketPriority, TicketStatus
from app.modules.tickets.dtos import TicketAssignRequest, TicketCreate, TicketStatusUpdate, TicketUpdate
from app.modules.tickets.schemas import Ticket
from app.modules.users.schemas import User


class TicketQueryBuilder:
    SORT_COLUMNS = {
        "id": Ticket.id,
        "status": Ticket.status,
        "priority": Ticket.priority,
        "created_at": Ticket.created_at,
        "updated_at": Ticket.updated_at,
        "resolved_at": Ticket.resolved_at,
    }

    def build_list_query(
        self,
        *,
        status_filter: TicketStatus | None,
        priority_filter: TicketPriority | None,
        created_by_user_id: int | None,
        assigned_to_user_id: int | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Ticket]]:
        query = select(Ticket).where(Ticket.is_active.is_(True))
        if status_filter is not None:
            query = query.where(Ticket.status == status_filter)
        if priority_filter is not None:
            query = query.where(Ticket.priority == priority_filter)
        if created_by_user_id is not None:
            query = query.where(Ticket.created_by_user_id == created_by_user_id)
        if assigned_to_user_id is not None:
            query = query.where(Ticket.assigned_to_user_id == assigned_to_user_id)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Ticket.title.ilike(search_pattern),
                    Ticket.description.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            return query.order_by(sort_column.desc(), Ticket.id.desc())
        return query.order_by(sort_column.asc(), Ticket.id.asc())


class TicketAccessPolicy:
    def ensure_local_actor(self, *, current_user: CurrentUser) -> int:
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=LOCAL_USER_CONTEXT_REQUIRED,
            )
        return current_user.id

    def ensure_admin(self, *, current_user: CurrentUser) -> None:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ADMIN_ACCESS_REQUIRED,
            )

    def enforce_ticket_visibility(
        self,
        *,
        current_user: CurrentUser,
        ticket: Ticket,
    ) -> None:
        if self._can_access_ticket(current_user=current_user, ticket=ticket):
            return
        role_label = current_user.role.value if current_user.role is not None else "unknown"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": TICKET_ACCESS_DENIED,
                "developer_message": (
                    f"User {current_user.user_id} with role {role_label} "
                    f"cannot access ticket {ticket.id}."
                ),
            },
        )

    def resolve_owner_scope(
        self,
        *,
        current_user: CurrentUser,
    ) -> int | None:
        if current_user.role == UserRole.ADMIN:
            return None
        return self.ensure_local_actor(current_user=current_user)

    def _can_access_ticket(self, *, current_user: CurrentUser, ticket: Ticket) -> bool:
        if current_user.role == UserRole.ADMIN:
            return True
        return current_user.id is not None and current_user.id == ticket.created_by_user_id


class TicketStatusPolicy:
    ALLOWED_TRANSITIONS = {
        TicketStatus.OPEN: {
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TicketStatus.REJECTED,
        },
        TicketStatus.IN_PROGRESS: {
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TicketStatus.REJECTED,
        },
        TicketStatus.RESOLVED: {
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TicketStatus.IN_PROGRESS,
        },
        TicketStatus.CLOSED: {
            TicketStatus.CLOSED,
        },
        TicketStatus.REJECTED: {
            TicketStatus.REJECTED,
            TicketStatus.OPEN,
        },
    }
    RESOLVED_STATES = {TicketStatus.RESOLVED, TicketStatus.CLOSED}

    def validate_transition(
        self,
        *,
        current_status: TicketStatus,
        target_status: TicketStatus,
    ) -> None:
        allowed_statuses = self.ALLOWED_TRANSITIONS[current_status]
        if target_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=TICKET_INVALID_STATUS_TRANSITION,
            )

    def resolve_resolved_at(
        self,
        *,
        status_value: TicketStatus,
    ) -> datetime | None:
        if status_value in self.RESOLVED_STATES:
            return datetime.now(UTC)
        return None


class TicketUserLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_active_or_422(self, *, user_id: int) -> User:
        user = self._db_session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=TICKET_ASSIGNEE_INVALID,
            )
        return user


class TicketService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = TicketQueryBuilder()
        self._access_policy = TicketAccessPolicy()
        self._status_policy = TicketStatusPolicy()
        self._user_lookup_service = TicketUserLookupService(db_session=db_session)

    def create(self, *, dto: TicketCreate, current_user: CurrentUser) -> Ticket:
        actor_id = self._access_policy.ensure_local_actor(current_user=current_user)
        if dto.assigned_to_user_id is not None:
            self._user_lookup_service.get_active_or_422(user_id=dto.assigned_to_user_id)
        ticket = Ticket(
            title=dto.title,
            description=dto.description,
            status=TicketStatus.OPEN,
            priority=dto.priority,
            created_by_user_id=actor_id,
            assigned_to_user_id=dto.assigned_to_user_id,
            status_changed_by_user_id=None,
            resolved_at=None,
            is_active=True,
        )
        self._db_session.add(ticket)
        self._commit_with_integrity_guard()
        self._db_session.refresh(ticket)
        return ticket

    def list_tickets(
        self,
        *,
        current_user: CurrentUser,
        status_filter: TicketStatus | None,
        priority_filter: TicketPriority | None,
        created_by_user_id: int | None,
        assigned_to_user_id: int | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[Ticket], PaginationMeta]:
        owner_scope_user_id = self._access_policy.resolve_owner_scope(current_user=current_user)
        target_created_by = owner_scope_user_id if owner_scope_user_id is not None else created_by_user_id
        query = self._query_builder.build_list_query(
            status_filter=status_filter,
            priority_filter=priority_filter,
            created_by_user_id=target_created_by,
            assigned_to_user_id=assigned_to_user_id,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        items = list(self._db_session.scalars(paginated_query).all())
        return items, PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_visible_or_404(self, *, ticket_id: int, current_user: CurrentUser) -> Ticket:
        ticket = self._db_session.get(Ticket, ticket_id)
        if ticket is None or not ticket.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TICKET_NOT_FOUND,
            )
        self._access_policy.enforce_ticket_visibility(
            current_user=current_user,
            ticket=ticket,
        )
        return ticket

    def update(self, *, ticket_id: int, dto: TicketUpdate, current_user: CurrentUser) -> Ticket:
        self._access_policy.ensure_local_actor(current_user=current_user)
        ticket = self.get_visible_or_404(ticket_id=ticket_id, current_user=current_user)
        for field_name, field_value in dto.model_dump(exclude_unset=True, exclude_none=False).items():
            setattr(ticket, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(ticket)
        return ticket

    def change_status(
        self,
        *,
        ticket_id: int,
        dto: TicketStatusUpdate,
        current_user: CurrentUser,
    ) -> Ticket:
        actor_id = self._access_policy.ensure_local_actor(current_user=current_user)
        self._access_policy.ensure_admin(current_user=current_user)
        ticket = self.get_visible_or_404(ticket_id=ticket_id, current_user=current_user)
        self._status_policy.validate_transition(
            current_status=ticket.status,
            target_status=dto.status,
        )
        ticket.status = dto.status
        ticket.status_changed_by_user_id = actor_id
        ticket.resolved_at = self._status_policy.resolve_resolved_at(status_value=dto.status)
        self._commit_with_integrity_guard()
        self._db_session.refresh(ticket)
        return ticket

    def assign(
        self,
        *,
        ticket_id: int,
        dto: TicketAssignRequest,
        current_user: CurrentUser,
    ) -> Ticket:
        actor_id = self._access_policy.ensure_local_actor(current_user=current_user)
        self._access_policy.ensure_admin(current_user=current_user)
        ticket = self.get_visible_or_404(ticket_id=ticket_id, current_user=current_user)
        if dto.assigned_to_user_id is not None:
            self._user_lookup_service.get_active_or_422(user_id=dto.assigned_to_user_id)
        ticket.assigned_to_user_id = dto.assigned_to_user_id
        ticket.status_changed_by_user_id = actor_id
        self._commit_with_integrity_guard()
        self._db_session.refresh(ticket)
        return ticket

    def deactivate(self, *, ticket_id: int, current_user: CurrentUser) -> Ticket:
        self._access_policy.ensure_local_actor(current_user=current_user)
        self._access_policy.ensure_admin(current_user=current_user)
        ticket = self.get_visible_or_404(ticket_id=ticket_id, current_user=current_user)
        ticket.is_active = False
        self._db_session.commit()
        self._db_session.refresh(ticket)
        return ticket

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


def get_ticket_service(db_session: Session = Depends(get_db_session)) -> TicketService:
    return TicketService(db_session=db_session)

