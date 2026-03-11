from fastapi import FastAPI
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common import model_registry as _model_registry
from app.common.config import get_settings
from app.common.dtos import HomePageOut
from app.common.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.common.messages import HOME_WELCOME_TEMPLATE
from app.modules.auth.module import router as auth_router
from app.modules.customers.module import router as customer_router
from app.modules.service_catalog.module import router as service_catalog_router
from app.modules.users.module import router as user_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Zaraamad Portal backend APIs.",
        version=settings.app_version,
    )
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_origin_regex=settings.cors_allowed_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(customer_router)
    app.include_router(service_catalog_router)
    return app


app = create_app()


@app.get(
    "/",
    response_model=HomePageOut,
    summary="API home",
    description="Return a friendly welcome payload and documentation links.",
    responses={200: {"description": "Home payload returned."}},
)
def get_home() -> HomePageOut:
    settings = get_settings()
    return HomePageOut(
        message=HOME_WELCOME_TEMPLATE.format(app_name=settings.app_name),
        app_name=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
