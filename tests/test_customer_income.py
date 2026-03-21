from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.enums import UserRole
from app.modules.customers.schemas import Customer, CustomerIncomeBucket, CustomerIncomeSummary
from app.modules.customers.service import CustomerIncomeImportService
from app.modules.users.schemas import User


def _write_income_workbook(
    workbook_path: Path,
    *,
    tehran_summary_amount: int = 1000,
    tehran_bucket_amounts: tuple[int, int] = (400, 600),
    qom_summary_amount: int = 500,
    qom_bucket_amounts: tuple[int, int] = (200, 300),
) -> None:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Sheet1"
    summary_sheet.append(
        [
            "registered_income_amount_12m",
            "issued_bills_count_12m",
            "paid_bills_count_12m",
            "collection_rate_percent_12m",
            None,
        ]
    )
    summary_sheet.append(
        [
            tehran_summary_amount,
            100,
            80,
            80,
            "شهرداری تهران",
        ]
    )
    summary_sheet.append(
        [
            qom_summary_amount,
            50,
            40,
            None,
            "شهرداری قم",
        ]
    )

    bucket_sheet = workbook.create_sheet("Sheet2")
    bucket_sheet.append(
        [
            "bucket_code",
            "chart_label",
            "registered_income_amount_12m",
            "شهرداری تهران",
        ]
    )
    bucket_sheet.append([110400, "عوارض ساختمانی", tehran_bucket_amounts[0], None])
    bucket_sheet.append([110500, 110500, tehran_bucket_amounts[1], None])
    bucket_sheet.append([None, None, None, None])
    bucket_sheet.append([110400, 123, qom_bucket_amounts[0], "شهرداری قم"])
    bucket_sheet.append([110500, "عوارض خدماتی", qom_bucket_amounts[1], None])

    workbook.save(workbook_path)
    workbook.close()


def _create_user(
    db_session: Session,
    *,
    full_name: str,
    mobile: str,
    role: UserRole,
    customer_id: int | None,
) -> User:
    user = User(
        full_name=full_name,
        mobile=mobile,
        role=role,
        customer_id=customer_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client: TestClient, mobile: str) -> str:
    otp_response = client.post("/auth/request-otp", json={"mobile": mobile})
    otp_code = otp_response.json()["dev_otp"]
    verify_response = client.post(
        "/auth/verify-otp",
        json={"mobile": mobile, "otp_code": otp_code},
    )
    return verify_response.json()["access_token"]


def test_customer_income_import_service_parses_and_imports_workbook(
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Book1.xlsx"
    _write_income_workbook(workbook_path)

    service = CustomerIncomeImportService(db_session=db_session)
    workbook_data = service.parse_workbook(workbook_path=workbook_path)

    assert len(workbook_data.summaries) == 2
    assert workbook_data.summaries[1].customer_name == "شهرداری قم"
    assert workbook_data.summaries[1].collection_rate_percent_12m is None

    tehran_service_bucket = next(
        item
        for item in workbook_data.buckets
        if item.customer_name == "شهرداری تهران" and item.bucket_code == "110500"
    )
    qom_construction_bucket = next(
        item
        for item in workbook_data.buckets
        if item.customer_name == "شهرداری قم" and item.bucket_code == "110400"
    )
    assert tehran_service_bucket.chart_label == "عوارض خدماتی"
    assert qom_construction_bucket.chart_label == "عوارض ساختمانی"

    report = service.import_workbook(workbook_path=workbook_path)

    assert report.processed_customer_count == 2
    assert report.upserted_summary_count == 2
    assert report.upserted_bucket_count == 4
    assert report.validation_failures == []

    tehran_customer = db_session.scalar(
        select(Customer).where(Customer.name == "شهرداری تهران")
    )
    assert tehran_customer is not None

    tehran_summary = db_session.get(CustomerIncomeSummary, tehran_customer.id)
    assert tehran_summary is not None
    assert tehran_summary.registered_income_amount_12m == 1000
    assert tehran_summary.collection_rate_percent_12m == 80

    tehran_buckets = list(
        db_session.scalars(
            select(CustomerIncomeBucket)
            .where(CustomerIncomeBucket.customer_id == tehran_customer.id)
            .order_by(CustomerIncomeBucket.bucket_code.asc())
        ).all()
    )
    assert [item.bucket_code for item in tehran_buckets] == ["110400", "110500"]
    assert [item.chart_label for item in tehran_buckets] == [
        "عوارض ساختمانی",
        "عوارض خدماتی",
    ]


def test_customer_income_import_service_reports_validation_failures(
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Book1.xlsx"
    _write_income_workbook(
        workbook_path,
        qom_summary_amount=600,
    )

    service = CustomerIncomeImportService(db_session=db_session)
    report = service.import_workbook(workbook_path=workbook_path)

    assert len(report.validation_failures) == 1
    failure = report.validation_failures[0]
    assert failure.customer_name == "شهرداری قم"
    assert failure.summary_registered_income_amount_12m == 600
    assert failure.bucket_total_registered_income_amount_12m == 500


def test_customer_income_import_service_is_idempotent(
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Book1.xlsx"
    _write_income_workbook(workbook_path)

    service = CustomerIncomeImportService(db_session=db_session)
    first_report = service.import_workbook(workbook_path=workbook_path)

    assert first_report.upserted_bucket_count == 4

    _write_income_workbook(
        workbook_path,
        tehran_summary_amount=1200,
        tehran_bucket_amounts=(500, 700),
    )
    second_report = service.import_workbook(workbook_path=workbook_path)

    assert second_report.processed_customer_count == 2
    assert db_session.scalar(select(func.count()).select_from(CustomerIncomeSummary)) == 2
    assert db_session.scalar(select(func.count()).select_from(CustomerIncomeBucket)) == 4

    tehran_customer = db_session.scalar(
        select(Customer).where(Customer.name == "شهرداری تهران")
    )
    assert tehran_customer is not None

    tehran_summary = db_session.get(CustomerIncomeSummary, tehran_customer.id)
    assert tehran_summary is not None
    assert tehran_summary.registered_income_amount_12m == 1200

    tehran_bucket_amounts = list(
        db_session.scalars(
            select(CustomerIncomeBucket.registered_income_amount_12m)
            .where(CustomerIncomeBucket.customer_id == tehran_customer.id)
            .order_by(CustomerIncomeBucket.bucket_code.asc())
        ).all()
    )
    assert tehran_bucket_amounts == [500, 700]


def test_customer_income_endpoints_return_expected_shapes(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Book1.xlsx"
    _write_income_workbook(workbook_path)

    import_service = CustomerIncomeImportService(db_session=db_session)
    import_service.import_workbook(workbook_path=workbook_path)

    admin = _create_user(
        db_session=db_session,
        full_name="Income Admin",
        mobile="09129990001",
        role=UserRole.ADMIN,
        customer_id=None,
    )
    tehran_customer = db_session.scalar(
        select(Customer).where(Customer.name == "شهرداری تهران")
    )
    assert tehran_customer is not None
    tehran_user = _create_user(
        db_session=db_session,
        full_name="Tehran Income User",
        mobile="09129990002",
        role=UserRole.CUSTOMER,
        customer_id=tehran_customer.id,
    )

    admin_headers = {"Authorization": f"Bearer {_login(client=client, mobile=admin.mobile)}"}
    tehran_headers = {"Authorization": f"Bearer {_login(client=client, mobile=tehran_user.mobile)}"}

    list_response = client.get(
        "/customers/income",
        headers=admin_headers,
        params={
            "sort_by": "registered_income_amount_12m",
            "sort_order": "desc",
        },
    )
    assert list_response.status_code == 200
    assert list_response.headers["X-Total-Count"] == "2"

    list_payload = list_response.json()
    assert list_payload["total_page"] == 1
    assert [item["customer_name"] for item in list_payload["items"]] == [
        "شهرداری تهران",
        "شهرداری قم",
    ]
    assert list_payload["items"][1]["collection_rate_percent_12m"] is None

    detail_response = client.get(
        f"/customers/{tehran_customer.id}/income",
        headers=tehran_headers,
    )
    assert detail_response.status_code == 200

    detail_payload = detail_response.json()
    assert detail_payload["customer"]["name"] == "شهرداری تهران"
    assert detail_payload["summary"]["registered_income_amount_12m"] == 1000
    assert detail_payload["summary"]["collection_rate_percent_12m"] == 80
    assert [item["bucket_code"] for item in detail_payload["buckets"]] == [
        "110400",
        "110500",
    ]
    assert [item["chart_label"] for item in detail_payload["buckets"]] == [
        "عوارض ساختمانی",
        "عوارض خدماتی",
    ]
