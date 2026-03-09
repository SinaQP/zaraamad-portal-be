from app.modules.municipalities.dtos import MunicipalityOut
from app.modules.municipalities.schemas import Municipality


class MunicipalityMapper:
    def to_out(self, municipality: Municipality) -> MunicipalityOut:
        return MunicipalityOut(
            id=municipality.id,
            name=municipality.name,
            grade=municipality.grade,
            is_active=municipality.is_active,
            created_at=municipality.created_at,
            updated_at=municipality.updated_at,
        )


def get_municipality_mapper() -> MunicipalityMapper:
    return MunicipalityMapper()
