from fastapi import FastAPI

from app.common import model_registry as _model_registry
from app.common.config import get_settings
from app.common.dtos import HomePageOut
from app.modules.auth.module import router as auth_router
from app.modules.municipalities.module import router as municipality_router
from app.modules.service_catalog.module import router as service_catalog_router
from app.modules.users.module import router as user_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Zaraamad Portal backend APIs.",
        version=settings.app_version,
    )
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(municipality_router)
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
        message=f"Welcome to {settings.app_name}",
        app_name=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
