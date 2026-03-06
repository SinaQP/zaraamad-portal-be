from app.common.config import get_settings
from app.common.database import database_runtime
from app.common.seeds import AdminSeedService


def run() -> None:
    settings = get_settings()
    seed_service = AdminSeedService(settings=settings)
    with database_runtime.session_factory() as session:
        admin = seed_service.seed_default_admin(db_session=session)
        print(f"Seeded admin user id={admin.id} mobile={admin.mobile}")


if __name__ == "__main__":
    run()
