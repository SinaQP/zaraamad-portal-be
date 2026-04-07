"""Manual SQL Server reference-data sync command for multiple source/target databases."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, ConfigDict, model_validator

from app.common.services.sqlserver_reference_sync import (
    DEFAULT_SQL_SERVER_PORT,
    SqlServerConnectionSettings,
    SqlServerEngineFactory,
    SqlServerMetadataLoader,
    SqlServerModelSyncExecutor,
    SqlServerSyncPlanBuilder,
    SqlServerSyncSqlBuilder,
    SqlServerSyncTableOverride,
    SqlServerTableReference,
)


@dataclass(frozen=True)
class SyncDatabaseTarget:
    host: str
    port: int
    username: str
    password: str
    database_name: str


@dataclass(frozen=True)
class SyncServerTarget:
    source: SyncDatabaseTarget
    target: SyncDatabaseTarget
    linked_server_name: str | None
    source_row: int


@dataclass(frozen=True)
class SyncModelExecutionPlan:
    sync_flag: str
    model_name: str
    table: SqlServerTableReference
    override: SqlServerSyncTableOverride | None


@dataclass(frozen=True)
class SyncExecutionResult:
    source_host: str
    source_database: str
    target_host: str
    target_database: str
    sync_flag: str
    model_name: str
    schema_name: str
    table_name: str
    mode: str
    inserted_count: int
    updated_count: int
    source_row_count: int | None
    linked_server_name: str | None
    status: str


@dataclass(frozen=True)
class SyncExecutionError:
    source_host: str | None
    source_database: str | None
    target_host: str | None
    target_database: str | None
    sync_flag: str | None
    model_name: str | None
    source_row: int | None
    error_message: str


@dataclass(frozen=True)
class SyncCommandSummary:
    servers_processed: int
    selected_models: int
    model_runs_attempted: int
    successful_model_runs: int
    error_count: int
    output_path: Path


class SyncDbPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sync_actions: bool = False
    sync_cities: bool = False
    sync_municipality_info: bool = False
    sync_menus: bool = False
    sync_provinces: bool = False
    sync_subsystems: bool = False
    sync_transport_colors: bool = False
    sync_transport_manufacturer_countries: bool = False
    sync_transport_plates: bool = False
    sync_transport_systems: bool = False
    sync_transport_usage_types: bool = False
    sync_transport_tariffs: bool = False
    sync_transport_year_amounts: bool = False
    sync_income_codes: bool = False

    @model_validator(mode="after")
    def apply_transport_dependencies(self) -> "SyncDbPayload":
        if self.sync_transport_year_amounts:
            self.sync_transport_tariffs = True
        return self


class SyncServerInputReader:
    HEADER_ALIASES = {
        "host": {"ip", "host", "hostname", "server", "serverip", "serverhost", "address"},
        "port": {"port", "serverport", "dbport"},
        "username": {"username", "user", "userid", "uid", "login"},
        "password": {"password", "pass", "passwd", "pwd"},
        "source_host": {"sourceip", "sourcehost", "sourcehostname", "sourceaddress"},
        "source_port": {"sourceport", "sourcedbport"},
        "source_username": {"sourceusername", "sourceuser", "sourceuid", "sourcelogin"},
        "source_password": {"sourcepassword", "sourcepass", "sourcepasswd", "sourcepwd"},
        "source_database": {"sourcedatabase", "source_db", "sourcedb"},
        "target_host": {"targetip", "targethost", "targethostname", "targetaddress"},
        "target_port": {"targetport", "targetdbport"},
        "target_username": {"targetusername", "targetuser", "targetuid", "targetlogin"},
        "target_password": {"targetpassword", "targetpass", "targetpasswd", "targetpwd"},
        "target_database": {"targetdatabase", "target_db", "targetdb", "database"},
        "linked_server_name": {
            "linkedserver",
            "linkedservername",
            "linked_server",
            "linked_server_name",
        },
    }

    def read(
        self,
        *,
        input_path: Path,
        default_source_database: str,
        default_target_database: str,
        default_linked_server_name: str | None,
    ) -> tuple[list[SyncServerTarget], list[SyncExecutionError]]:
        rows = self._read_rows(input_path=input_path)
        targets: list[SyncServerTarget] = []
        errors: list[SyncExecutionError] = []
        for row_number, row in rows:
            try:
                targets.append(
                    self._build_target(
                        row=row,
                        row_number=row_number,
                        default_source_database=default_source_database,
                        default_target_database=default_target_database,
                        default_linked_server_name=default_linked_server_name,
                    )
                )
            except ValueError as exc:
                errors.append(
                    SyncExecutionError(
                        source_host=self._normalize_text(row.get("source_host") or row.get("host")),
                        source_database=self._normalize_text(row.get("source_database")) or default_source_database,
                        target_host=self._normalize_text(row.get("target_host") or row.get("host")),
                        target_database=self._normalize_text(row.get("target_database")) or default_target_database,
                        sync_flag=None,
                        model_name=None,
                        source_row=row_number,
                        error_message=f"Input row {row_number}: {exc}",
                    )
                )
        return targets, errors

    def _read_rows(self, *, input_path: Path) -> list[tuple[int, dict[str, Any]]]:
        suffix = input_path.suffix.lower()
        if suffix == ".csv":
            return self._read_csv(input_path=input_path)
        if suffix == ".xlsx":
            return self._read_xlsx(input_path=input_path)
        raise ValueError("Input file must be .xlsx or .csv.")

    def _read_csv(self, *, input_path: Path) -> list[tuple[int, dict[str, Any]]]:
        with input_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
            rows = list(csv.reader(file_handle))
        if not rows:
            return []
        header_lookup = self._build_header_lookup(headers=rows[0])
        return [
            (row_number, self._extract_row_values(row=row, header_lookup=header_lookup))
            for row_number, row in enumerate(rows[1:], start=2)
        ]

    def _read_xlsx(self, *, input_path: Path) -> list[tuple[int, dict[str, Any]]]:
        workbook = load_workbook(filename=input_path, read_only=True, data_only=True)
        try:
            rows = list(workbook.active.iter_rows(values_only=True))
        finally:
            workbook.close()
        if not rows:
            return []
        header_lookup = self._build_header_lookup(headers=rows[0])
        return [
            (row_number, self._extract_row_values(row=row, header_lookup=header_lookup))
            for row_number, row in enumerate(rows[1:], start=2)
        ]

    def _build_header_lookup(self, *, headers: Sequence[object]) -> dict[str, int]:
        lookup: dict[str, int] = {}
        for index, header in enumerate(headers):
            normalized_header = self._normalize_header_name(header)
            if normalized_header is None:
                continue
            for canonical_name, aliases in self.HEADER_ALIASES.items():
                if normalized_header in aliases and canonical_name not in lookup:
                    lookup[canonical_name] = index
        return lookup

    def _extract_row_values(
        self,
        *,
        row: Sequence[object],
        header_lookup: dict[str, int],
    ) -> dict[str, Any]:
        return {
            canonical_name: row[column_index] if column_index < len(row) else None
            for canonical_name, column_index in header_lookup.items()
        }

    def _build_target(
        self,
        *,
        row: dict[str, Any],
        row_number: int,
        default_source_database: str,
        default_target_database: str,
        default_linked_server_name: str | None,
    ) -> SyncServerTarget:
        source_target = SyncDatabaseTarget(
            host=self._require_value(
                row=row,
                specific_key="source_host",
                generic_key="host",
                field_label="source host",
            ),
            port=self._resolve_port(row=row, specific_key="source_port", generic_key="port"),
            username=self._require_value(
                row=row,
                specific_key="source_username",
                generic_key="username",
                field_label="source username",
            ),
            password=self._require_value(
                row=row,
                specific_key="source_password",
                generic_key="password",
                field_label="source password",
            ),
            database_name=self._resolve_database_name(
                row=row,
                key="source_database",
                default_value=default_source_database,
                field_label="source database",
            ),
        )
        target_target = SyncDatabaseTarget(
            host=self._require_value(
                row=row,
                specific_key="target_host",
                generic_key="host",
                field_label="target host",
            ),
            port=self._resolve_port(row=row, specific_key="target_port", generic_key="port"),
            username=self._require_value(
                row=row,
                specific_key="target_username",
                generic_key="username",
                field_label="target username",
            ),
            password=self._require_value(
                row=row,
                specific_key="target_password",
                generic_key="password",
                field_label="target password",
            ),
            database_name=self._resolve_database_name(
                row=row,
                key="target_database",
                default_value=default_target_database,
                field_label="target database",
            ),
        )
        linked_server_name = self._normalize_text(row.get("linked_server_name"))
        return SyncServerTarget(
            source=source_target,
            target=target_target,
            linked_server_name=linked_server_name or default_linked_server_name,
            source_row=row_number,
        )

    def _require_value(
        self,
        *,
        row: dict[str, Any],
        specific_key: str,
        generic_key: str,
        field_label: str,
    ) -> str:
        normalized_value = self._normalize_text(row.get(specific_key))
        if normalized_value is not None:
            return normalized_value
        normalized_generic_value = self._normalize_text(row.get(generic_key))
        if normalized_generic_value is not None:
            return normalized_generic_value
        raise ValueError(f"Missing {field_label} value.")

    def _resolve_database_name(
        self,
        *,
        row: dict[str, Any],
        key: str,
        default_value: str,
        field_label: str,
    ) -> str:
        normalized_value = self._normalize_text(row.get(key))
        if normalized_value is not None:
            return normalized_value
        normalized_default_value = default_value.strip()
        if normalized_default_value:
            return normalized_default_value
        raise ValueError(f"Missing {field_label} value.")

    def _resolve_port(
        self,
        *,
        row: dict[str, Any],
        specific_key: str,
        generic_key: str,
    ) -> int:
        specific_port = self._safe_port(row.get(specific_key))
        if specific_port is not None:
            return specific_port
        generic_port = self._safe_port(row.get(generic_key))
        if generic_port is not None:
            return generic_port
        return DEFAULT_SQL_SERVER_PORT

    def _normalize_header_name(self, value: object) -> str | None:
        text_value = self._normalize_text(value)
        if text_value is None:
            return None
        return "".join(
            character for character in text_value.lower() if character.isalnum() or character == "_"
        )

    def _normalize_text(self, value: object | None) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        if not text_value:
            return None
        return text_value

    def _safe_port(self, value: object | None) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None


class SyncModelCatalog:
    _MODEL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("sync_menus", ("Menus",)),
        ("sync_provinces", ("Provinces",)),
        ("sync_subsystems", ("SubSystems",)),
        ("sync_actions", ("Action",)),
        ("sync_cities", ("Cities",)),
        ("sync_municipality_info", ("MunicipalityInfo",)),
        ("sync_transport_colors", ("TransportColors",)),
        ("sync_transport_manufacturer_countries", ("TransportManufacturerCountries",)),
        ("sync_transport_plates", ("TransportPlates",)),
        ("sync_transport_systems", ("TransportSystems",)),
        ("sync_transport_usage_types", ("TransportUsageTypes",)),
        ("sync_transport_tariffs", ("TransportTariffs", "TransportTariffLocals")),
        ("sync_transport_year_amounts", ("TransportYearAmounts", "TransportYearAmountLocals")),
        ("sync_income_codes", ("IncomeCodes",)),
    )

    def build(self, *, payload: SyncDbPayload) -> list[SyncModelExecutionPlan]:
        plans: list[SyncModelExecutionPlan] = []
        payload_values = payload.model_dump()
        for sync_flag, model_names in self._MODEL_GROUPS:
            if not payload_values[sync_flag]:
                continue
            for model_name in model_names:
                plans.append(
                    SyncModelExecutionPlan(
                        sync_flag=sync_flag,
                        model_name=model_name,
                        table=SqlServerTableReference(
                            model_name=model_name,
                            schema_name="dbo",
                            table_name=model_name,
                        ),
                        override=None,
                    )
                )
        return plans


class SyncReportWriter:
    _RESULT_COLUMNS = [
        "source_host",
        "source_database",
        "target_host",
        "target_database",
        "sync_flag",
        "model_name",
        "schema_name",
        "table_name",
        "mode",
        "inserted_count",
        "updated_count",
        "source_row_count",
        "linked_server_name",
        "status",
    ]
    _ERROR_COLUMNS = [
        "source_host",
        "source_database",
        "target_host",
        "target_database",
        "sync_flag",
        "model_name",
        "source_row",
        "error_message",
    ]

    def save(
        self,
        *,
        output_path: Path,
        summary: SyncCommandSummary,
        results: Sequence[SyncExecutionResult],
        errors: Sequence[SyncExecutionError],
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".json":
            self._save_json(
                output_path=output_path,
                summary=summary,
                results=results,
                errors=errors,
            )
            return
        self._save_xlsx(
            output_path=output_path,
            summary=summary,
            results=results,
            errors=errors,
        )

    def _save_json(
        self,
        *,
        output_path: Path,
        summary: SyncCommandSummary,
        results: Sequence[SyncExecutionResult],
        errors: Sequence[SyncExecutionError],
    ) -> None:
        payload = {
            "summary": {
                "servers_processed": summary.servers_processed,
                "selected_models": summary.selected_models,
                "model_runs_attempted": summary.model_runs_attempted,
                "successful_model_runs": summary.successful_model_runs,
                "error_count": summary.error_count,
                "output_path": str(summary.output_path),
            },
            "results": [result.__dict__ for result in results],
            "errors": [error.__dict__ for error in errors],
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_xlsx(
        self,
        *,
        output_path: Path,
        summary: SyncCommandSummary,
        results: Sequence[SyncExecutionResult],
        errors: Sequence[SyncExecutionError],
    ) -> None:
        workbook = Workbook(write_only=True)
        summary_sheet = workbook.create_sheet(title="summary")
        results_sheet = workbook.create_sheet(title="results")
        errors_sheet = workbook.create_sheet(title="errors")

        summary_sheet.append(["metric", "value"])
        summary_sheet.append(["servers_processed", summary.servers_processed])
        summary_sheet.append(["selected_models", summary.selected_models])
        summary_sheet.append(["model_runs_attempted", summary.model_runs_attempted])
        summary_sheet.append(["successful_model_runs", summary.successful_model_runs])
        summary_sheet.append(["error_count", summary.error_count])
        summary_sheet.append(["output_path", str(summary.output_path)])

        results_sheet.append(self._RESULT_COLUMNS)
        for result in results:
            results_sheet.append([getattr(result, column_name) for column_name in self._RESULT_COLUMNS])

        errors_sheet.append(self._ERROR_COLUMNS)
        for error in errors:
            errors_sheet.append([getattr(error, column_name) for column_name in self._ERROR_COLUMNS])

        workbook.save(output_path)


class SyncDbMultiServerCommand:
    def __init__(
        self,
        *,
        input_reader: SyncServerInputReader,
        model_catalog: SyncModelCatalog,
        executor: SqlServerModelSyncExecutor,
        report_writer: SyncReportWriter,
        logger: logging.Logger,
    ) -> None:
        self._input_reader = input_reader
        self._model_catalog = model_catalog
        self._executor = executor
        self._report_writer = report_writer
        self._logger = logger

    def run(
        self,
        *,
        input_path: Path,
        output_path: Path,
        payload: SyncDbPayload,
        source_database: str,
        target_database: str,
        linked_server_name: str | None,
    ) -> SyncCommandSummary:
        targets, input_errors = self._input_reader.read(
            input_path=input_path,
            default_source_database=source_database,
            default_target_database=target_database,
            default_linked_server_name=linked_server_name,
        )
        execution_plans = self._model_catalog.build(payload=payload)

        results: list[SyncExecutionResult] = []
        errors = list(input_errors)
        successful_model_runs = 0
        model_runs_attempted = 0

        for target in targets:
            source_settings = SqlServerConnectionSettings(
                host=target.source.host,
                port=target.source.port,
                username=target.source.username,
                password=target.source.password,
                database_name=target.source.database_name,
            )
            target_settings = SqlServerConnectionSettings(
                host=target.target.host,
                port=target.target.port,
                username=target.target.username,
                password=target.target.password,
                database_name=target.target.database_name,
            )
            try:
                self._executor.check_connections(
                    source_settings=source_settings,
                    target_settings=target_settings,
                )
            except Exception as exc:
                self._logger.error(
                    "server_connection_check_failed source_host=%s source_database=%s target_host=%s target_database=%s error=%s",
                    target.source.host,
                    target.source.database_name,
                    target.target.host,
                    target.target.database_name,
                    exc,
                )
                errors.append(
                    SyncExecutionError(
                        source_host=target.source.host,
                        source_database=target.source.database_name,
                        target_host=target.target.host,
                        target_database=target.target.database_name,
                        sync_flag=None,
                        model_name=None,
                        source_row=target.source_row,
                        error_message=str(exc),
                    )
                )
                continue

            for execution_plan in execution_plans:
                model_runs_attempted += 1
                resolved_linked_server_name = self._resolve_linked_server_name(
                    source_database_name=target.source.database_name,
                    explicit_linked_server_name=target.linked_server_name,
                )
                try:
                    stats = self._executor.execute(
                        source_settings=source_settings,
                        target_settings=target_settings,
                        table=execution_plan.table,
                        linked_server_name=resolved_linked_server_name,
                        override=execution_plan.override,
                    )
                    successful_model_runs += 1
                    self._logger.info(
                        "sync_completed source_host=%s source_database=%s target_host=%s target_database=%s model_name=%s mode=%s inserted=%s updated=%s",
                        target.source.host,
                        target.source.database_name,
                        target.target.host,
                        target.target.database_name,
                        execution_plan.model_name,
                        stats.mode,
                        stats.inserted_count,
                        stats.updated_count,
                    )
                    results.append(
                        SyncExecutionResult(
                            source_host=target.source.host,
                            source_database=target.source.database_name,
                            target_host=target.target.host,
                            target_database=target.target.database_name,
                            sync_flag=execution_plan.sync_flag,
                            model_name=execution_plan.model_name,
                            schema_name=execution_plan.table.schema_name,
                            table_name=execution_plan.table.table_name,
                            mode=stats.mode,
                            inserted_count=stats.inserted_count,
                            updated_count=stats.updated_count,
                            source_row_count=stats.source_row_count,
                            linked_server_name=resolved_linked_server_name,
                            status="ok",
                        )
                    )
                except Exception as exc:
                    self._logger.error(
                        "sync_failed source_host=%s source_database=%s target_host=%s target_database=%s model_name=%s error=%s",
                        target.source.host,
                        target.source.database_name,
                        target.target.host,
                        target.target.database_name,
                        execution_plan.model_name,
                        exc,
                    )
                    errors.append(
                        SyncExecutionError(
                            source_host=target.source.host,
                            source_database=target.source.database_name,
                            target_host=target.target.host,
                            target_database=target.target.database_name,
                            sync_flag=execution_plan.sync_flag,
                            model_name=execution_plan.model_name,
                            source_row=target.source_row,
                            error_message=str(exc),
                        )
                    )

        summary = SyncCommandSummary(
            servers_processed=len(targets),
            selected_models=len(execution_plans),
            model_runs_attempted=model_runs_attempted,
            successful_model_runs=successful_model_runs,
            error_count=len(errors),
            output_path=output_path,
        )
        self._report_writer.save(
            output_path=output_path,
            summary=summary,
            results=results,
            errors=errors,
        )
        return summary

    def _resolve_linked_server_name(
        self,
        *,
        source_database_name: str,
        explicit_linked_server_name: str | None,
    ) -> str | None:
        if explicit_linked_server_name:
            return explicit_linked_server_name
        specific_env_name = f"SYNC_DB_{self._normalize_env_name(source_database_name)}_LINKED_SERVER"
        return os.getenv(specific_env_name) or os.getenv("SYNC_DB_LINKED_SERVER")

    def _normalize_env_name(self, value: str) -> str:
        return "".join(
            character if character.isalnum() else "_"
            for character in value.strip().upper()
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sync SQL Server reference tables from source databases into target databases "
            "for multiple CSV/XLSX connection rows."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input server list (.xlsx or .csv).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output report (.xlsx or .json).",
    )
    parser.add_argument(
        "--source-database",
        default="online_db",
        help="Default source database name when the input row does not provide one.",
    )
    parser.add_argument(
        "--target-database",
        default="default",
        help="Default target database name when the input row does not provide one.",
    )
    parser.add_argument(
        "--linked-server-name",
        default=None,
        help="Optional explicit linked server name. Row value wins over CLI value.",
    )
    parser.add_argument(
        "--driver",
        default="ODBC Driver 18 for SQL Server",
        help="ODBC driver name for SQL Server connections.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        default=15,
        help="SQL Server connection timeout in seconds.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for staging-mode source reads.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level for the command.",
    )
    _add_sync_flag_arguments(parser)
    return parser


def _add_sync_flag_arguments(parser: argparse.ArgumentParser) -> None:
    for field_name in SyncDbPayload.model_fields:
        parser.add_argument(
            f"--{field_name.replace('_', '-')}",
            action="store_true",
            help=f"Enable {field_name}.",
        )


def build_payload_from_args(args: argparse.Namespace) -> SyncDbPayload:
    payload_data = {
        field_name: bool(getattr(args, field_name))
        for field_name in SyncDbPayload.model_fields
    }
    return SyncDbPayload.model_validate(payload_data)


def configure_logging(*, log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("sqlserver_reference_sync")


def format_summary(summary: SyncCommandSummary) -> str:
    return (
        "servers_processed="
        f"{summary.servers_processed}\n"
        f"selected_models={summary.selected_models}\n"
        f"model_runs_attempted={summary.model_runs_attempted}\n"
        f"successful_model_runs={summary.successful_model_runs}\n"
        f"error_count={summary.error_count}\n"
        f"output_file={summary.output_path}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = configure_logging(log_level=args.log_level)
    payload = build_payload_from_args(args)
    command = SyncDbMultiServerCommand(
        input_reader=SyncServerInputReader(),
        model_catalog=SyncModelCatalog(),
        executor=SqlServerModelSyncExecutor(
            engine_factory=SqlServerEngineFactory(
                driver=args.driver,
                connect_timeout=args.connect_timeout,
            ),
            metadata_loader=SqlServerMetadataLoader(),
            sync_plan_builder=SqlServerSyncPlanBuilder(),
            sql_builder=SqlServerSyncSqlBuilder(),
            batch_size=args.batch_size,
        ),
        report_writer=SyncReportWriter(),
        logger=logger,
    )
    summary = command.run(
        input_path=Path(args.input).resolve(),
        output_path=Path(args.output).resolve(),
        payload=payload,
        source_database=args.source_database,
        target_database=args.target_database,
        linked_server_name=args.linked_server_name,
    )
    summary_text = format_summary(summary)
    logger.info("sync_command_completed\n%s", summary_text)
    print(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
