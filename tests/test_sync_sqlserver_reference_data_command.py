import json
from pathlib import Path

from app.commands.sync_sqlserver_reference_data import (
    DataSyncError,
    DataSyncSummary,
    ReferenceDataFileReader,
    SyncDbPayload,
    SyncPlanBuilder,
    SyncReportWriter,
    SyncSqlServerReferenceDataCommand,
    TargetServerInputReader,
    configure_logging,
    format_command_output,
)
from app.common.services.sqlserver_reference_sync import SqlServerModelSyncStats


class Args:
    transport_tariffs_file = None
    transport_tariff_locals_file = None
    transport_year_amounts_file = None
    transport_year_amount_locals_file = None


class FakeExecutor:
    def __init__(self) -> None:
        self.checked_targets = []
        self.discovered_targets = []
        self.executed_tables = []
        self.lookup_requests = []

    def check_target_connection(self, *, target_settings) -> None:
        self.checked_targets.append(target_settings)

    def discover_target_databases(self, *, target_settings):
        self.discovered_targets.append(target_settings)
        return ["db_one", "db_two"]

    def fetch_existing_column_values(self, *, target_settings, table, column_name):
        self.lookup_requests.append((target_settings, table, column_name))
        if table.table_name == "TransportTariffs":
            return {1}
        if table.table_name == "TransportTariffLocals":
            return {8001}
        return set()

    def execute_from_rows(self, *, target_settings, table, row_payloads, override=None):
        del target_settings, override
        self.executed_tables.append((table.model_name, row_payloads))
        return SqlServerModelSyncStats(
            mode="file",
            inserted_count=1,
            updated_count=2,
            source_row_count=len(row_payloads),
        )


def test_payload_enables_transport_tariffs_when_year_amounts_selected() -> None:
    payload = SyncDbPayload(sync_transport_year_amounts=True)

    assert payload.sync_transport_tariffs is True


def test_plan_builder_uses_only_supplied_files(tmp_path: Path) -> None:
    args = Args()
    args.transport_year_amounts_file = str(tmp_path / "year_amounts.xlsx")
    payload = SyncDbPayload(sync_transport_year_amounts=True)

    plans = SyncPlanBuilder().build(payload=payload, args=args)

    assert [plan.model_name for plan in plans] == ["TransportYearAmounts"]
    assert plans[0].table.schema_name == "Trp"
    assert plans[0].override is not None
    assert plans[0].override.column_names == (
        "Amount",
        "Year",
        "IsDeleted",
        "TransportTariffId",
    )
    assert plans[0].override.primary_key_columns == ("Year", "TransportTariffId")


def test_command_reads_targets_and_data_files_and_writes_json_report(tmp_path: Path) -> None:
    targets_path = tmp_path / "servers.csv"
    targets_path.write_text("ip,port,username,password\n10.0.0.1,1433,sa,secret\n", encoding="utf-8")

    data_path = tmp_path / "year_amounts.csv"
    data_path.write_text(
        "id,Amount,Year,IsDeleted,TransportTariffId\n59097,675000,1404,0,1\n",
        encoding="utf-8",
    )

    args = Args()
    args.transport_year_amounts_file = str(data_path)
    output_path = tmp_path / "report.json"

    command = SyncSqlServerReferenceDataCommand(
        target_reader=TargetServerInputReader(),
        data_reader=ReferenceDataFileReader(),
        plan_builder=SyncPlanBuilder(),
        executor=FakeExecutor(),
        report_writer=SyncReportWriter(),
        logger=configure_logging(log_level="INFO"),
    )
    summary = command.run(
        targets_input_path=targets_path,
        output_path=output_path,
        payload=SyncDbPayload(sync_transport_year_amounts=True),
        args=args,
    )

    assert summary.targets_processed == 1
    assert summary.selected_tables == 1
    assert summary.table_runs_attempted == 2
    assert summary.successful_table_runs == 2
    assert summary.skipped_row_count == 0
    assert summary.error_count == 0

    report_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(report_payload["results"]) == 2
    assert report_payload["results"][0]["model_name"] == "TransportYearAmounts"
    assert report_payload["results"][0]["source_row_count"] == 1
    assert report_payload["results"][0]["skipped_row_count"] == 0
    assert report_payload["skipped_rows"] == []


def test_command_skips_missing_reference_rows_and_reports_them(tmp_path: Path) -> None:
    targets_path = tmp_path / "servers.csv"
    targets_path.write_text("ip,port,username,password\n10.0.0.1,1433,sa,secret\n", encoding="utf-8")

    data_path = tmp_path / "year_amounts.csv"
    data_path.write_text(
        (
            "id,Amount,Year,IsDeleted,TransportTariffId\n"
            "59097,675000,1404,0,1\n"
            "59098,680000,1405,0,999\n"
        ),
        encoding="utf-8",
    )

    args = Args()
    args.transport_year_amounts_file = str(data_path)
    output_path = tmp_path / "report.json"
    fake_executor = FakeExecutor()

    command = SyncSqlServerReferenceDataCommand(
        target_reader=TargetServerInputReader(),
        data_reader=ReferenceDataFileReader(),
        plan_builder=SyncPlanBuilder(),
        executor=fake_executor,
        report_writer=SyncReportWriter(),
        logger=configure_logging(log_level="INFO"),
    )

    summary = command.run(
        targets_input_path=targets_path,
        output_path=output_path,
        payload=SyncDbPayload(sync_transport_year_amounts=True),
        args=args,
    )

    assert summary.skipped_row_count == 2
    assert fake_executor.executed_tables == [
        (
            "TransportYearAmounts",
            [
                {
                    "id": "59097",
                    "Amount": "675000",
                    "Year": "1404",
                    "IsDeleted": "0",
                    "TransportTariffId": "1",
                    "__source_row__": 2,
                }
            ],
        ),
        (
            "TransportYearAmounts",
            [
                {
                    "id": "59097",
                    "Amount": "675000",
                    "Year": "1404",
                    "IsDeleted": "0",
                    "TransportTariffId": "1",
                    "__source_row__": 2,
                }
            ],
        ),
    ]

    report_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert report_payload["results"][0]["skipped_row_count"] == 1
    assert report_payload["skipped_rows"][0]["target_database"] == "db_one"
    assert report_payload["skipped_rows"][0]["source_row"] == 3
    assert report_payload["skipped_rows"][0]["reference_value"] == "999"
    assert "skip شد" in report_payload["skipped_rows"][0]["reason"]


def test_format_command_output_includes_error_messages() -> None:
    summary = DataSyncSummary(
        targets_processed=1,
        selected_tables=1,
        table_runs_attempted=0,
        successful_table_runs=0,
        skipped_row_count=0,
        error_count=1,
        output_path=Path("report.xlsx"),
    )
    errors = [
        DataSyncError(
            target_host="192.168.1.10",
            target_database=None,
            sync_flag=None,
            model_name=None,
            source_row=2,
            error_message="Could not connect",
        )
    ]

    output_text = format_command_output(summary, errors, [])

    assert "error_count=1" in output_text
    assert "error_message=Could not connect" in output_text
