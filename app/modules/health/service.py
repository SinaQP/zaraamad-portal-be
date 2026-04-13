import logging

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import get_db_session
from app.modules.health.dtos import HealthDependencyOut, HealthStatusOut

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(
        self,
        db_session: Session,
        settings: Settings,
    ) -> None:
        self._db_session = db_session
        self._settings = settings

    def get_status(self) -> HealthStatusOut:
        dependencies = [self._check_primary_database()]
        sqlserver_dependency = self._check_sqlserver_database()
        if sqlserver_dependency is not None:
            dependencies.append(sqlserver_dependency)
        overall_status = self._resolve_overall_status(dependencies=dependencies)
        return HealthStatusOut(
            status=overall_status,
            dependencies=dependencies,
        )

    def _check_primary_database(self) -> HealthDependencyOut:
        try:
            self._db_session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning(
                "health_primary_database_check_failed",
                extra={"error_type": exc.__class__.__name__},
            )
            return HealthDependencyOut(
                name="postgres",
                is_online=False,
                status="offline",
                detail="اتصال به پایگاه داده اصلی برقرار نیست.",
            )
        return HealthDependencyOut(
            name="postgres",
            is_online=True,
            status="online",
            detail="اتصال به پایگاه داده اصلی برقرار است.",
        )

    def _check_sqlserver_database(self) -> HealthDependencyOut | None:
        if not self._settings.sqlserver_url:
            return None
        try:
            from sqlalchemy import create_engine

            engine = create_engine(
                self._settings.sqlserver_url,
                pool_pre_ping=True,
                connect_args={"timeout": 30},
            )
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
        except SQLAlchemyError as exc:
            logger.warning(
                "health_sqlserver_check_failed",
                extra={"error_type": exc.__class__.__name__},
            )
            return HealthDependencyOut(
                name="sqlserver",
                is_online=False,
                status="offline",
                detail="اتصال به پایگاه داده SQL Server برقرار نیست.",
            )
        return HealthDependencyOut(
            name="sqlserver",
            is_online=True,
            status="online",
            detail="اتصال به پایگاه داده SQL Server برقرار است.",
        )

    def _resolve_overall_status(
        self,
        *,
        dependencies: list[HealthDependencyOut],
    ) -> str:
        if all(dependency.is_online for dependency in dependencies):
            return "online"
        primary_database = dependencies[0]
        if primary_database.is_online:
            return "degraded"
        return "offline"


def get_health_service(
    db_session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> HealthService:
    return HealthService(
        db_session=db_session,
        settings=settings,
    )
