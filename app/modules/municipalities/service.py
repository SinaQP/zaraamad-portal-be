from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import get_db_session
from app.modules.municipalities.dtos import MunicipalityCreate, MunicipalityUpdate
from app.modules.municipalities.schemas import Municipality


class MunicipalityQueryBuilder:
    def build_list_query(self, is_active: bool | None) -> Select[tuple[Municipality]]:
        query = select(Municipality).order_by(Municipality.id.asc())
        if is_active is not None:
            query = query.where(Municipality.is_active.is_(is_active))
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

    def list(self, is_active: bool | None) -> list[Municipality]:
        query = self._query_builder.build_list_query(is_active=is_active)
        return list(self._db_session.scalars(query).all())

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
