from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.common.enums import SortOrder
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.municipalities.dtos import MunicipalityCreate, MunicipalityUpdate
from app.modules.municipalities.schemas import Municipality


class MunicipalityQueryBuilder:
    SORT_COLUMNS = {
        "id": Municipality.id,
        "name": Municipality.name,
        "grade": Municipality.grade,
        "is_active": Municipality.is_active,
        "created_at": Municipality.created_at,
        "updated_at": Municipality.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Municipality]]:
        query = select(Municipality)
        if is_active is not None:
            query = query.where(Municipality.is_active.is_(is_active))
        if search:
            query = query.where(Municipality.name.ilike(f"%{search}%"))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Municipality.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Municipality.id.asc())
        return query


class MunicipalityService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = MunicipalityQueryBuilder()

    def create(self, dto: MunicipalityCreate) -> Municipality:
        municipality = Municipality(
            name=dto.name,
            grade=dto.grade,
            is_active=True,
        )
        self._db_session.add(municipality)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
            ) from exc
        self._db_session.refresh(municipality)
        return municipality

    def list(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[Municipality], PaginationMeta]:
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

    def get_or_404(self, municipality_id: int) -> Municipality:
        municipality = self._db_session.get(Municipality, municipality_id)
        if municipality is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Municipality not found.",
            )
        return municipality

    def update(self, municipality_id: int, dto: MunicipalityUpdate) -> Municipality:
        municipality = self.get_or_404(municipality_id=municipality_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(municipality, field_name, field_value)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
            ) from exc
        self._db_session.refresh(municipality)
        return municipality

    def deactivate(self, municipality_id: int) -> Municipality:
        municipality = self.get_or_404(municipality_id=municipality_id)
        municipality.is_active = False
        self._db_session.commit()
        self._db_session.refresh(municipality)
        return municipality


def get_municipality_service(
    db_session: Session = Depends(get_db_session),
) -> MunicipalityService:
    return MunicipalityService(db_session=db_session)
