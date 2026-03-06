from app.modules.auth import schemas as auth_schemas
from app.modules.municipalities import schemas as municipalities_schemas
from app.modules.service_catalog import schemas as service_catalog_schemas
from app.modules.users import schemas as users_schemas

MODEL_MODULES = (
    auth_schemas,
    municipalities_schemas,
    service_catalog_schemas,
    users_schemas,
)
