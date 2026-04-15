from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.common.security.secret_cipher import SecretCipherService
from app.common.services.sqlserver_reference_sync import SqlServerConnectionSettings
from app.main import app
from app.modules.customers.schemas import CustomerDatabaseConnection
from app.modules.customers.service import (
    CustomerDatabaseConnectionRuntimeError,
    CustomerDatabaseConnectionService,
    CustomerDatabaseConnectionValidationError,
    CustomerDatabaseConnectionVerifier,
    CustomerService,
    get_customer_database_connection_verifier,
)
from app.modules.customers.dtos import CustomerCreate, CustomerDatabaseConnectionCreate
from app.modules.users.schemas import User
from tests.auth_utils import token_for_mobile

TEST_CONNECTION_STRING = (
    "mssql+pyodbc://portal_user:super-secret-password@10.10.10.20:1433/"
    "CustomerPortalDb?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
)
TEST_SECRET_KEY = "-E_R1oAEBykFnlBgP-BSJ6MG_XvG3ytPIe7bU2MOzyU="


class RecordingCustomerDatabaseConnectionVerifier(CustomerDatabaseConnectionVerifier):
    def __init__(self) -> None:
        self.actions: list[tuple[str, str]] = []

    def build_settings(self, *, connection_string: str) -> SqlServerConnectionSettings:
        self.actions.append(("build", connection_string))
        return SqlServerConnectionSettings(
            host="10.10.10.20",
            port=1433,
            username="portal_user",
            password="super-secret-password",
            database_name="CustomerPortalDb",
            driver_name="ODBC Driver 18 for SQL Server",
            encrypt_connection=True,
            trust_server_certificate=False,
        )

    def test_connection(self, *, connection_string: str) -> None:
        self.actions.append(("test", connection_string))


class FailingCustomerDatabaseConnectionVerifier(RecordingCustomerDatabaseConnectionVerifier):
    def test_connection(self, *, connection_string: str) -> None:
        self.actions.append(("test", connection_string))
        raise CustomerDatabaseConnectionRuntimeError(
            "Could not connect to database with secret token."
        )


def _admin_headers(*, db_session: Session) -> dict[str, str]:
    admin_user = User(
        full_name="System Admin",
        mobile="09120000000",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()
    return {"Authorization": f"Bearer {token_for_mobile('09120000000')}"}


def test_customer_database_connection_service_encrypts_and_hashes_connection_string(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    verifier = CustomerDatabaseConnectionVerifier()
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
        secret_cipher_service=SecretCipherService(TEST_SECRET_KEY),
        verifier=verifier,
    )
    customer = customer_service.create(
        CustomerCreate(
            name="Tehran Customer",
            manager_name="Ali Rezaei",
            grade=1,
        )
    )

    _, database_connection = database_connection_service.upsert(
        customer_id=customer.id,
        dto=CustomerDatabaseConnectionCreate(
            connection_string=TEST_CONNECTION_STRING,
            secret_version="v1",
            is_active=True,
        ),
    )

    assert database_connection.encrypted_connection_string is not None
    assert database_connection.encrypted_connection_string != TEST_CONNECTION_STRING
    assert database_connection.connection_string_hash is not None
    assert database_connection.host is None
    assert database_connection.database_name is None
    assert database_connection.username is None
    assert database_connection.secret_ref is None

    _, _, settings = database_connection_service.build_sqlserver_connection_settings(
        customer_id=customer.id,
    )
    assert settings.host == "10.10.10.20"
    assert settings.database_name == "CustomerPortalDb"
    assert settings.username == "portal_user"
    assert settings.password == "super-secret-password"


def test_update_customer_database_connection_endpoint_hides_sensitive_values(
    client: TestClient,
    db_session: Session,
) -> None:
    verifier = RecordingCustomerDatabaseConnectionVerifier()
    app.dependency_overrides[get_customer_database_connection_verifier] = lambda: verifier
    headers = _admin_headers(db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Qom Customer",
            "grade": 2,
        },
    )
    customer_id = customer_response.json()["id"]

    response = client.patch(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
        json={
            "connection_string": TEST_CONNECTION_STRING,
            "secret_version": "v2",
            "is_active": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "customer_id": customer_id,
        "customer_name": "Qom Customer",
        "db_kind": "sqlserver",
        "is_active": True,
        "has_connection_secret": True,
        "secret_version": "v2",
        "credential_rotated_at": payload["credential_rotated_at"],
        "rotation_due_at": None,
        "last_connection_tested_at": None,
        "last_connection_test_success": None,
        "last_connection_error": None,
    }
    assert "connection_string" not in payload
    assert "host" not in payload
    assert "database_name" not in payload
    assert verifier.actions[0] == ("build", TEST_CONNECTION_STRING)

    database_connection = db_session.get(CustomerDatabaseConnection, customer_id)
    assert database_connection is not None
    assert database_connection.encrypted_connection_string is not None
    assert database_connection.encrypted_connection_string != TEST_CONNECTION_STRING
    assert database_connection.connection_string_hash is not None

    app.dependency_overrides.clear()


def test_get_customer_database_connection_endpoint_returns_non_sensitive_view(
    client: TestClient,
    db_session: Session,
) -> None:
    verifier = RecordingCustomerDatabaseConnectionVerifier()
    app.dependency_overrides[get_customer_database_connection_verifier] = lambda: verifier
    headers = _admin_headers(db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Mashhad Customer",
            "grade": 3,
        },
    )
    customer_id = customer_response.json()["id"]
    client.patch(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
        json={"connection_string": TEST_CONNECTION_STRING},
    )

    response = client.get(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == customer_id
    assert payload["customer_name"] == "Mashhad Customer"
    assert payload["has_connection_secret"] is True
    assert "connection_string" not in payload
    assert "host" not in payload

    app.dependency_overrides.clear()


def test_test_customer_database_connection_endpoint_updates_status_on_success(
    client: TestClient,
    db_session: Session,
) -> None:
    verifier = RecordingCustomerDatabaseConnectionVerifier()
    app.dependency_overrides[get_customer_database_connection_verifier] = lambda: verifier
    headers = _admin_headers(db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Shiraz Customer",
            "grade": 1,
        },
    )
    customer_id = customer_response.json()["id"]
    client.patch(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
        json={"connection_string": TEST_CONNECTION_STRING},
    )

    response = client.post(
        f"/customers/{customer_id}/database-connection/test",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_connection_secret"] is True
    assert payload["last_connection_test_success"] is True
    assert payload["last_connection_tested_at"] is not None
    assert payload["last_connection_error"] is None
    assert verifier.actions[-1] == ("test", TEST_CONNECTION_STRING)

    app.dependency_overrides.clear()


def test_test_customer_database_connection_endpoint_sanitizes_failure_response(
    client: TestClient,
    db_session: Session,
) -> None:
    verifier = FailingCustomerDatabaseConnectionVerifier()
    app.dependency_overrides[get_customer_database_connection_verifier] = lambda: verifier
    headers = _admin_headers(db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Tabriz Customer",
            "grade": 2,
        },
    )
    customer_id = customer_response.json()["id"]
    client.patch(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
        json={"connection_string": TEST_CONNECTION_STRING},
    )

    response = client.post(
        f"/customers/{customer_id}/database-connection/test",
        headers=headers,
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["message"] == "اتصال به پایگاه داده مشتری برقرار نشد."
    assert "10.10.10.20" not in payload["developer_message"]
    assert "CustomerPortalDb" not in payload["developer_message"]
    assert "super-secret-password" not in payload["developer_message"]

    database_connection = db_session.get(CustomerDatabaseConnection, customer_id)
    assert database_connection is not None
    assert database_connection.last_connection_test_success is False
    assert database_connection.last_connection_error == "Could not connect to database with *** ***."

    app.dependency_overrides.clear()


def test_update_customer_database_connection_endpoint_rejects_invalid_connection_string(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(db_session=db_session)
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Karaj Customer",
            "grade": 1,
        },
    )
    customer_id = customer_response.json()["id"]

    response = client.patch(
        f"/customers/{customer_id}/database-connection",
        headers=headers,
        json={"connection_string": "not-a-valid-connection-string"},
    )

    assert response.status_code == 422
    assert response.json()["message"] == "رشته اتصال پایگاه داده مشتری معتبر نیست."
