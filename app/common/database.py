from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.common.config import get_settings


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DatabaseRuntime:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args=self._build_connect_args(database_url=database_url),
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_session(self) -> Generator[Session, None, None]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def _build_connect_args(self, *, database_url: str) -> dict[str, object]:
        drivername = make_url(database_url).drivername
        if drivername != "mssql+pyodbc":
            return {}
        return {"timeout": 30}


database_runtime = DatabaseRuntime(get_settings().database_url)


def get_db_session() -> Generator[Session, None, None]:
    yield from database_runtime.get_session()
