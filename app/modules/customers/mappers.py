from app.modules.customers.dtos import CustomerOut
from app.modules.customers.schemas import Customer


class CustomerMapper:
    def to_out(self, customer: Customer) -> CustomerOut:
        return CustomerOut(
            id=customer.id,
            name=customer.name,
            grade=customer.grade,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )


def get_customer_mapper() -> CustomerMapper:
    return CustomerMapper()
