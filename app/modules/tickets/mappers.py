from app.modules.tickets.dtos import TicketOut
from app.modules.tickets.schemas import Ticket


class TicketMapper:
    def to_out(self, ticket: Ticket) -> TicketOut:
        return TicketOut(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            priority=ticket.priority,
            status=ticket.status,
            created_by_user_id=ticket.created_by_user_id,
            assigned_to_user_id=ticket.assigned_to_user_id,
            status_changed_by_user_id=ticket.status_changed_by_user_id,
            resolved_at=ticket.resolved_at,
            is_active=ticket.is_active,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )


def get_ticket_mapper() -> TicketMapper:
    return TicketMapper()

