from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.common.enums import SortOrder
from app.common.messages import DATA_INTEGRITY_ERROR, CUSTOMER_NOT_FOUND
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.customers.dtos import CustomerCreate, CustomerUpdate
from app.modules.customers.schemas import Customer


class CustomerQueryBuilder:
    SORT_COLUMNS = {
        "id": Customer.id,
        "name": Customer.name,
        "grade": Customer.grade,
        "is_active": Customer.is_active,
        "created_at": Customer.created_at,
        "updated_at": Customer.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Customer]]:
        query = select(Customer)
        if is_active is not None:
            query = query.where(Customer.is_active.is_(is_active))
        if search:
            query = query.where(Customer.name.ilike(f"%{search}%"))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Customer.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Customer.id.asc())
        return query


class CustomerService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = CustomerQueryBuilder()

    def create(self, dto: CustomerCreate) -> Customer:
        customer = Customer(
            name=dto.name,
            grade=dto.grade,
            is_active=True,
        )
        self._db_session.add(customer)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def list(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[Customer], PaginationMeta]:
        query = self._query_builder.build_list_query(
            is_active=is_active,
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
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def get_or_404(self, customer_id: int) -> Customer:
        customer = self._db_session.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return customer

    def update(self, customer_id: int, dto: CustomerUpdate) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(customer, field_name, field_value)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def deactivate(self, customer_id: int) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        customer.is_active = False
        self._db_session.commit()
        self._db_session.refresh(customer)
        return customer


def get_customer_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerService:
    return CustomerService(db_session=db_session)
