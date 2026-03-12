from app.modules.auth import schemas as auth_schemas
from app.modules.customers import schemas as customers_schemas
from app.modules.service_catalog import schemas as service_catalog_schemas
from app.modules.subscriptions import schemas as subscriptions_schemas
from app.modules.users import schemas as users_schemas

MODEL_MODULES = (
    auth_schemas,
    customers_schemas,
    service_catalog_schemas,
    subscriptions_schemas,
    users_schemas,
)
