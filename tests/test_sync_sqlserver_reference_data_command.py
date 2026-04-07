import json
from pathlib import Path

from app.commands.sync_sqlserver_reference_data import (
    SyncDbMultiServerCommand,
    SyncDbPayload,
    SyncModelCatalog,
    SyncReportWriter,
    SyncServerInputReader,
    configure_logging,
)
from app.common.services.sqlserver_reference_sync import SqlServerModelSyncStats


class FakeSyncExecutor:
    def __init__(self) -> None:
        self.connection_checks = []
        self.executed_models = []

    def check_connections(self, *, source_settings, target_settings) -> None:
        self.connection_checks.append((source_settings, target_settings))

    def execute(
        self,
        *,
        source_settings,
        target_settings,
        table,
        linked_server_name=None,
        override=None,
    ) -> SqlServerModelSyncStats:
        del source_settings, target_settings, linked_server_name, override
        self.executed_models.append(table.model_name)
        if table.model_name == "TransportYearAmounts":
            raise RuntimeError("year amounts failed")
        return SqlServerModelSyncStats(
            mode="staging",
            inserted_count=2,
            updated_count=1,
            source_row_count=5,
        )


def test_payload_enables_transport_tariffs_when_year_amounts_selected() -> None:
    payload = SyncDbPayload(sync_transport_year_amounts=True)

    assert payload.sync_transport_tariffs is True


def test_model_catalog_orders_transport_dependencies() -> None:
    catalog = SyncModelCatalog()
    payload = SyncDbPayload(sync_transport_year_amounts=True)

    plans = catalog.build(payload=payload)

    assert [plan.model_name for plan in plans] == [
        "TransportTariffs",
        "TransportTariffLocals",
        "TransportYearAmounts",
        "TransportYearAmountLocals",
    ]


def test_command_reads_csv_and_writes_json_report(tmp_path: Path) -> None:
    input_path = tmp_path / "connections.csv"
    output_path = tmp_path / "report.json"
    input_path.write_text(
        "ip,username,password\n10.0.0.1,sa,secret\n",
        encoding="utf-8",
    )

    executor = FakeSyncExecutor()
    command = SyncDbMultiServerCommand(
        input_reader=SyncServerInputReader(),
        model_catalog=SyncModelCatalog(),
        executor=executor,
        report_writer=SyncReportWriter(),
        logger=configure_logging(log_level="INFO"),
    )

    summary = command.run(
        input_path=input_path,
        output_path=output_path,
        payload=SyncDbPayload(sync_transport_year_amounts=True),
        source_database="online_db",
        target_database="default",
        linked_server_name=None,
    )

    assert summary.servers_processed == 1
    assert summary.selected_models == 4
    assert summary.model_runs_attempted == 4
    assert summary.successful_model_runs == 3
    assert summary.error_count == 1
    assert executor.executed_models == [
        "TransportTariffs",
        "TransportTariffLocals",
        "TransportYearAmounts",
        "TransportYearAmountLocals",
    ]

    report_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert report_payload["summary"]["selected_models"] == 4
    assert len(report_payload["results"]) == 3
    assert len(report_payload["errors"]) == 1
    assert report_payload["errors"][0]["model_name"] == "TransportYearAmounts"
    assert "year amounts failed" in report_payload["errors"][0]["error_message"]
