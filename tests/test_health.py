from app.main import app
from app.modules.health.dtos import HealthDependencyOut, HealthStatusOut
from app.modules.health.service import get_health_service


class StubHealthService:
    def __init__(self, status: HealthStatusOut) -> None:
        self._status = status

    def get_status(self) -> HealthStatusOut:
        return self._status


def test_health_returns_200_for_online_status(client):
    app.dependency_overrides[get_health_service] = lambda: StubHealthService(
        HealthStatusOut(
            status="online",
            dependencies=[
                HealthDependencyOut(
                    name="postgres",
                    is_online=True,
                    status="online",
                    detail="اتصال به پایگاه داده اصلی برقرار است.",
                )
            ],
        )
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "online"
    app.dependency_overrides.clear()


def test_health_returns_503_for_offline_status(client):
    app.dependency_overrides[get_health_service] = lambda: StubHealthService(
        HealthStatusOut(
            status="offline",
            dependencies=[
                HealthDependencyOut(
                    name="postgres",
                    is_online=False,
                    status="offline",
                    detail="اتصال به پایگاه داده اصلی برقرار نیست.",
                )
            ],
        )
    )

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "offline"
    app.dependency_overrides.clear()
