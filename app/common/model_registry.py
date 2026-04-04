from app.modules.auth import schemas as auth_schemas
from app.modules.customers import schemas as customers_schemas
from app.modules.feedback import schemas as feedback_schemas
from app.modules.forms import schemas as forms_schemas
from app.modules.service_catalog import schemas as service_catalog_schemas
from app.modules.users import schemas as users_schemas

MODEL_MODULES = (
    auth_schemas,
    customers_schemas,
    feedback_schemas,
    forms_schemas,
    service_catalog_schemas,
    users_schemas,
)
