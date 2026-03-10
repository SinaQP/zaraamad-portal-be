from fastapi.testclient import TestClient


def test_localhost_frontend_origin_is_allowed_by_default(client: TestClient) -> None:
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unknown_origin_is_rejected_by_default(client: TestClient) -> None:
    response = client.options(
        "/",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
