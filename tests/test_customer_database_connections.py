from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.modules.customers.dtos import CustomerCreate, CustomerDatabaseConnectionCreate
from app.modules.customers.mappers import CustomerMapper
from app.modules.customers.service import CustomerDatabaseConnectionService, CustomerService


def test_customer_database_connection_service_upserts_metadata(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
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
            host="10.10.10.20",
            port=1433,
            database_name="CustomerPortalDb",
            username="portal_reader",
            secret_ref="kv/zaraamad/customers/1/sqlserver-password",
            secret_version="v3",
            driver_name="ODBC Driver 18 for SQL Server",
            encrypt_connection=True,
            trust_server_certificate=False,
            is_active=True,
        ),
    )

    assert database_connection.customer_id == customer.id
    assert database_connection.secret_ref == "kv/zaraamad/customers/1/sqlserver-password"
    assert database_connection.encrypt_connection is True
    assert database_connection.trust_server_certificate is False


def test_customer_database_connection_mapper_hides_secret_ref(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
    )
    mapper = CustomerMapper()
    customer = customer_service.create(
        CustomerCreate(
            name="Qom Customer",
            manager_name="Sara Ahmadi",
            grade=2,
        )
    )
    customer, database_connection = database_connection_service.upsert(
        customer_id=customer.id,
        dto=CustomerDatabaseConnectionCreate(
            host="10.10.10.30",
            port=1433,
            database_name="QomDb",
            username="portal_reader",
            secret_ref="kv/zaraamad/customers/2/sqlserver-password",
        ),
    )

    dto = mapper.to_database_connection_out(
        customer=customer,
        database_connection=database_connection,
    )

    assert dto is not None
    assert dto.has_secret_ref is True
    assert "secret_ref" not in dto.model_dump()


def test_customer_database_connection_service_builds_sqlserver_settings(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
    )
    customer = customer_service.create(
        CustomerCreate(
            name="Mashhad Customer",
            manager_name="Reza Karimi",
            grade=3,
        )
    )
    database_connection_service.upsert(
        customer_id=customer.id,
        dto=CustomerDatabaseConnectionCreate(
            host="10.10.10.40",
            port=1444,
            database_name="MashhadDb",
            username="portal_sync",
            secret_ref="kv/zaraamad/customers/3/sqlserver-password",
            driver_name="ODBC Driver 18 for SQL Server",
            encrypt_connection=True,
            trust_server_certificate=False,
        ),
    )

    _, _, settings = database_connection_service.build_sqlserver_connection_settings(
        customer_id=customer.id,
        password="super-secret-password",
    )

    assert settings.host == "10.10.10.40"
    assert settings.port == 1444
    assert settings.database_name == "MashhadDb"
    assert settings.username == "portal_sync"
    assert settings.password == "super-secret-password"
    assert settings.encrypt_connection is True
    assert settings.trust_server_certificate is False


def test_customer_database_connection_service_requires_password(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
    )
    customer = customer_service.create(
        CustomerCreate(
            name="Shiraz Customer",
            manager_name="Mina Kazemi",
            grade=1,
        )
    )
    database_connection_service.upsert(
        customer_id=customer.id,
        dto=CustomerDatabaseConnectionCreate(
            host="10.10.10.50",
            port=1433,
            database_name="ShirazDb",
            username="portal_sync",
            secret_ref="kv/zaraamad/customers/4/sqlserver-password",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        database_connection_service.build_sqlserver_connection_settings(
            customer_id=customer.id,
            password="   ",
        )

    assert exc_info.value.status_code == 422


def test_customer_database_connection_service_sanitizes_test_error_message(db_session) -> None:
    customer_service = CustomerService(db_session=db_session)
    database_connection_service = CustomerDatabaseConnectionService(
        db_session=db_session,
        customer_service=customer_service,
    )
    customer = customer_service.create(
        CustomerCreate(
            name="Tabriz Customer",
            manager_name="Arman Rahimi",
            grade=2,
        )
    )
    database_connection_service.upsert(
        customer_id=customer.id,
        dto=CustomerDatabaseConnectionCreate(
            host="10.10.10.60",
            port=1433,
            database_name="TabrizDb",
            username="portal_sync",
            secret_ref="kv/zaraamad/customers/5/sqlserver-password",
        ),
    )

    _, database_connection = database_connection_service.persist_connection_test_result(
        customer_id=customer.id,
        checked_at=datetime.now(UTC),
        is_success=False,
        error_message="password mismatch for secret token",
    )

    assert database_connection.last_connection_test_success is False
    assert database_connection.last_connection_error == "*** mismatch for *** ***"
