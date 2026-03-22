from argparse import ArgumentParser
from pathlib import Path

from app.common.database import database_runtime
from app.modules.customers.service import CustomerIncomeImportService


def parse_args():
    parser = ArgumentParser(
        description="Import municipality customer income data from an Excel workbook.",
    )
    parser.add_argument(
        "workbook_path",
        nargs="?",
        default="Book1.xlsx",
        help="Path to the Excel workbook. Defaults to Book1.xlsx in the current working directory.",
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    workbook_path = Path(args.workbook_path).resolve()

    try:
        with database_runtime.session_factory() as session:
            import_service = CustomerIncomeImportService(db_session=session)
            report = import_service.import_workbook(workbook_path=workbook_path)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Imported customer income data from {workbook_path}")
    print(
        "processed_customer_count="
        f"{report.processed_customer_count} "
        f"upserted_summary_count={report.upserted_summary_count} "
        f"upserted_bucket_count={report.upserted_bucket_count} "
        f"validation_failures={len(report.validation_failures)}"
    )
    if not report.validation_failures:
        return

    print("Validation failures:")
    for failure in report.validation_failures:
        print(
            f"customer_name={failure.customer_name} "
            f"summary_registered_income_amount={failure.summary_registered_income_amount} "
            f"bucket_total_registered_income_amount={failure.bucket_total_registered_income_amount} "
            f"message={failure.message}"
        )


if __name__ == "__main__":
    run()
