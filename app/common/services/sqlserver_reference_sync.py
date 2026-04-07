from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import URL, create_engine, text

DEFAULT_SQL_SERVER_PORT = 1433
READ_ONLY_SOURCE_QUERY_TEMPLATE = "SELECT {columns} FROM {table_name}"
SYNC_STAGE_TABLE_NAME = "#sync_stage"
SYNC_ACTIONS_TABLE_NAME = "#sync_actions"
TEXT_TYPE_NAMES = {
    "char",
    "nchar",
    "ntext",
    "nvarchar",
    "text",
    "varchar",
}
UNSUPPORTED_SYNC_TYPE_NAMES = {"rowversion", "timestamp"}


@dataclass(frozen=True)
class SqlServerConnectionSettings:
    host: str
    port: int
    username: str
    password: str
    database_name: str


@dataclass(frozen=True)
class SqlServerTableReference:
    model_name: str
    schema_name: str
    table_name: str


@dataclass(frozen=True)
class SqlServerColumnMetadata:
    name: str
    type_name: str
    is_nullable: bool
    is_primary_key: bool
    primary_key_ordinal: int | None
    is_identity: bool

    @property
    def normalized_type_name(self) -> str:
        return self.type_name.lower()


@dataclass(frozen=True)
class SqlServerTableSyncPlan:
    table: SqlServerTableReference
    source_columns: tuple[SqlServerColumnMetadata, ...]
    target_columns: tuple[SqlServerColumnMetadata, ...]
    sync_columns: tuple[SqlServerColumnMetadata, ...]
    primary_key_columns: tuple[SqlServerColumnMetadata, ...]

    @property
    def identity_primary_key(self) -> SqlServerColumnMetadata | None:
        for column in self.primary_key_columns:
            if column.is_identity:
                return column
        return None

    @property
    def updatable_columns(self) -> tuple[SqlServerColumnMetadata, ...]:
        primary_key_names = {column.name for column in self.primary_key_columns}
        return tuple(
            column for column in self.sync_columns if column.name not in primary_key_names
        )


@dataclass(frozen=True)
class SqlServerModelSyncStats:
    mode: str
    inserted_count: int
    updated_count: int
    source_row_count: int | None


@dataclass(frozen=True)
class SqlServerSyncTableOverride:
    schema_name: str = "dbo"
    table_name: str | None = None
    column_names: tuple[str, ...] | None = None
    primary_key_columns: tuple[str, ...] | None = None


class SqlServerReferenceSyncError(Exception):
    pass


class SqlServerConnectionError(SqlServerReferenceSyncError):
    pass


class SqlServerMetadataError(SqlServerReferenceSyncError):
    pass


class SqlServerEngineFactory:
    def __init__(self, *, driver: str, connect_timeout: int) -> None:
        self._driver = driver
        self._connect_timeout = connect_timeout

    def create_engine(self, settings: SqlServerConnectionSettings):
        self._ensure_pyodbc_available()
        url = URL.create(
            "mssql+pyodbc",
            username=settings.username,
            password=settings.password,
            host=settings.host,
            port=settings.port,
            database=settings.database_name,
            query={
                "driver": self._driver,
                "TrustServerCertificate": "yes",
                "Encrypt": "no",
            },
        )
        return create_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"timeout": self._connect_timeout},
        )

    def _ensure_pyodbc_available(self) -> None:
        try:
            import pyodbc  # noqa: F401
        except ImportError as exc:
            raise SqlServerConnectionError(
                "pyodbc is required for SQL Server connections. Install project dependencies first."
            ) from exc


class SqlServerMetadataLoader:
    _COLUMN_METADATA_QUERY = text(
        """
        SELECT
            column_metadata.column_name,
            column_metadata.type_name,
            column_metadata.is_nullable,
            column_metadata.is_primary_key,
            column_metadata.primary_key_ordinal,
            column_metadata.is_identity
        FROM (
            SELECT
                columns_table.column_id,
                columns_table.name AS column_name,
                TYPE_NAME(columns_table.user_type_id) AS type_name,
                columns_table.is_nullable,
                CASE
                    WHEN primary_key_columns.column_id IS NULL THEN 0
                    ELSE 1
                END AS is_primary_key,
                primary_key_columns.key_ordinal AS primary_key_ordinal,
                COLUMNPROPERTY(columns_table.object_id, columns_table.name, 'IsIdentity')
                    AS is_identity
            FROM sys.tables AS tables_table
            INNER JOIN sys.schemas AS schemas_table
                ON schemas_table.schema_id = tables_table.schema_id
            INNER JOIN sys.columns AS columns_table
                ON columns_table.object_id = tables_table.object_id
            LEFT JOIN sys.indexes AS primary_key_index
                ON primary_key_index.object_id = tables_table.object_id
               AND primary_key_index.is_primary_key = 1
            LEFT JOIN sys.index_columns AS primary_key_columns
                ON primary_key_columns.object_id = tables_table.object_id
               AND primary_key_columns.index_id = primary_key_index.index_id
               AND primary_key_columns.column_id = columns_table.column_id
            WHERE schemas_table.name = :schema_name
              AND tables_table.name = :table_name
              AND columns_table.is_computed = 0
              AND TYPE_NAME(columns_table.user_type_id) NOT IN ('timestamp', 'rowversion')
        ) AS column_metadata
        ORDER BY column_metadata.column_id
        """
    )

    def load(self, connection, table: SqlServerTableReference) -> tuple[SqlServerColumnMetadata, ...]:
        rows = (
            connection.execute(
                self._COLUMN_METADATA_QUERY,
                {
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                },
            )
            .mappings()
            .all()
        )
        if not rows:
            raise SqlServerMetadataError(
                f"Table '{table.schema_name}.{table.table_name}' was not found."
            )
        columns = tuple(
            SqlServerColumnMetadata(
                name=str(row["column_name"]),
                type_name=str(row["type_name"]),
                is_nullable=bool(row["is_nullable"]),
                is_primary_key=bool(row["is_primary_key"]),
                primary_key_ordinal=(
                    int(row["primary_key_ordinal"])
                    if row["primary_key_ordinal"] is not None
                    else None
                ),
                is_identity=bool(row["is_identity"]),
            )
            for row in rows
        )
        if not any(column.is_primary_key for column in columns):
            raise SqlServerMetadataError(
                f"Table '{table.schema_name}.{table.table_name}' must define a primary key."
            )
        return columns


class SqlServerSyncPlanBuilder:
    def build(
        self,
        *,
        table: SqlServerTableReference,
        source_columns: Sequence[SqlServerColumnMetadata],
        target_columns: Sequence[SqlServerColumnMetadata],
        override: SqlServerSyncTableOverride | None,
    ) -> SqlServerTableSyncPlan:
        source_lookup = {column.name: column for column in source_columns}
        target_lookup = {column.name: column for column in target_columns}

        selected_column_names = self._resolve_selected_column_names(
            source_lookup=source_lookup,
            target_lookup=target_lookup,
            target_columns=target_columns,
            override=override,
            table=table,
        )
        primary_key_names = self._resolve_primary_key_names(
            source_lookup=source_lookup,
            target_lookup=target_lookup,
            selected_column_names=selected_column_names,
            override=override,
            table=table,
        )
        sync_columns = tuple(target_lookup[name] for name in selected_column_names)
        primary_key_columns = tuple(target_lookup[name] for name in primary_key_names)
        return SqlServerTableSyncPlan(
            table=table,
            source_columns=tuple(source_lookup[name] for name in selected_column_names),
            target_columns=tuple(target_lookup[name] for name in selected_column_names),
            sync_columns=sync_columns,
            primary_key_columns=primary_key_columns,
        )

    def _resolve_selected_column_names(
        self,
        *,
        source_lookup: dict[str, SqlServerColumnMetadata],
        target_lookup: dict[str, SqlServerColumnMetadata],
        target_columns: Sequence[SqlServerColumnMetadata],
        override: SqlServerSyncTableOverride | None,
        table: SqlServerTableReference,
    ) -> tuple[str, ...]:
        if override and override.column_names:
            explicit_column_names = tuple(override.column_names)
            self._validate_requested_columns(
                requested_column_names=explicit_column_names,
                available_source_columns=source_lookup,
                available_target_columns=target_lookup,
                table=table,
            )
            return explicit_column_names

        common_column_names = tuple(
            column.name for column in target_columns if column.name in source_lookup
        )
        if not common_column_names:
            raise SqlServerMetadataError(
                f"Table '{table.schema_name}.{table.table_name}' has no common columns between source and target."
            )
        return common_column_names

    def _resolve_primary_key_names(
        self,
        *,
        source_lookup: dict[str, SqlServerColumnMetadata],
        target_lookup: dict[str, SqlServerColumnMetadata],
        selected_column_names: Sequence[str],
        override: SqlServerSyncTableOverride | None,
        table: SqlServerTableReference,
    ) -> tuple[str, ...]:
        if override and override.primary_key_columns:
            explicit_primary_key_names = tuple(override.primary_key_columns)
            self._validate_requested_columns(
                requested_column_names=explicit_primary_key_names,
                available_source_columns=source_lookup,
                available_target_columns=target_lookup,
                table=table,
            )
            missing_from_sync = [
                column_name
                for column_name in explicit_primary_key_names
                if column_name not in selected_column_names
            ]
            if missing_from_sync:
                raise SqlServerMetadataError(
                    f"Primary key override for '{table.schema_name}.{table.table_name}' must be part of the sync columns."
                )
            return explicit_primary_key_names

        primary_key_names = tuple(
            column.name
            for column in sorted(
                target_lookup.values(),
                key=lambda column: (
                    column.primary_key_ordinal if column.primary_key_ordinal is not None else 0,
                    column.name,
                ),
            )
            if column.is_primary_key and column.name in selected_column_names
        )
        if not primary_key_names:
            raise SqlServerMetadataError(
                f"Table '{table.schema_name}.{table.table_name}' has no shared primary key columns."
            )
        missing_source_primary_keys = [
            column_name
            for column_name in primary_key_names
            if not source_lookup[column_name].is_primary_key
        ]
        if missing_source_primary_keys:
            raise SqlServerMetadataError(
                f"Source table '{table.schema_name}.{table.table_name}' is missing primary key metadata for: "
                + ", ".join(missing_source_primary_keys)
            )
        return primary_key_names

    def _validate_requested_columns(
        self,
        *,
        requested_column_names: Sequence[str],
        available_source_columns: dict[str, SqlServerColumnMetadata],
        available_target_columns: dict[str, SqlServerColumnMetadata],
        table: SqlServerTableReference,
    ) -> None:
        missing_columns = [
            column_name
            for column_name in requested_column_names
            if column_name not in available_source_columns
            or column_name not in available_target_columns
        ]
        if missing_columns:
            raise SqlServerMetadataError(
                f"Requested columns for '{table.schema_name}.{table.table_name}' were not found in both source and target: "
                + ", ".join(missing_columns)
            )


class SqlServerSyncSqlBuilder:
    def build_source_select_query(self, plan: SqlServerTableSyncPlan) -> str:
        column_list = self._format_column_list(plan.sync_columns)
        source_table_name = self._format_table_name(
            schema_name=plan.table.schema_name,
            table_name=plan.table.table_name,
        )
        order_by_clause = self._build_order_by_clause(plan.primary_key_columns)
        return (
            READ_ONLY_SOURCE_QUERY_TEMPLATE.format(
                columns=column_list,
                table_name=source_table_name,
            )
            + order_by_clause
        )

    def build_stage_table_query(self, plan: SqlServerTableSyncPlan) -> str:
        target_table_name = self._format_table_name(
            schema_name=plan.table.schema_name,
            table_name=plan.table.table_name,
        )
        column_list = self._format_column_list(plan.sync_columns)
        return (
            f"SELECT TOP 0 {column_list} INTO {SYNC_STAGE_TABLE_NAME} "
            f"FROM {target_table_name};"
        )

    def build_stage_insert_query(self, plan: SqlServerTableSyncPlan) -> str:
        column_list = self._format_column_list(plan.sync_columns)
        placeholder_list = ", ".join("?" for _ in plan.sync_columns)
        return (
            f"INSERT INTO {SYNC_STAGE_TABLE_NAME} ({column_list}) "
            f"VALUES ({placeholder_list})"
        )

    def build_stage_merge_query(self, plan: SqlServerTableSyncPlan) -> str:
        return self._build_merge_query(
            plan=plan,
            source_dataset=SYNC_STAGE_TABLE_NAME,
            source_alias="source",
        )

    def build_linked_server_merge_query(
        self,
        *,
        plan: SqlServerTableSyncPlan,
        source_database_name: str,
        linked_server_name: str,
    ) -> str:
        source_dataset = (
            "(SELECT "
            f"{self._format_column_list(plan.source_columns)} "
            "FROM "
            f"{self._format_linked_server_table_name(linked_server_name=linked_server_name, source_database_name=source_database_name, table=plan.table)})"
        )
        return self._build_merge_query(
            plan=plan,
            source_dataset=source_dataset,
            source_alias="source",
        )

    def build_identity_insert_toggle_query(
        self,
        *,
        plan: SqlServerTableSyncPlan,
        enabled: bool,
    ) -> str:
        target_table_name = self._format_table_name(
            schema_name=plan.table.schema_name,
            table_name=plan.table.table_name,
        )
        toggle_value = "ON" if enabled else "OFF"
        return f"SET IDENTITY_INSERT {target_table_name} {toggle_value};"

    def _build_merge_query(
        self,
        *,
        plan: SqlServerTableSyncPlan,
        source_dataset: str,
        source_alias: str,
    ) -> str:
        target_table_name = self._format_table_name(
            schema_name=plan.table.schema_name,
            table_name=plan.table.table_name,
        )
        merge_lines = [
            f"CREATE TABLE {SYNC_ACTIONS_TABLE_NAME} ([action] nvarchar(10) NOT NULL);",
            f"MERGE {target_table_name} AS target",
            f"USING {source_dataset} AS {source_alias}",
            f"ON {self._build_primary_key_join(plan.primary_key_columns)}",
        ]
        update_assignments = self._build_update_assignments(plan.updatable_columns)
        update_condition = self._build_update_condition(plan.updatable_columns)
        if update_assignments and update_condition:
            merge_lines.append(
                f"WHEN MATCHED AND ({update_condition}) THEN UPDATE SET {update_assignments}"
            )
        merge_lines.append(
            "WHEN NOT MATCHED BY TARGET THEN INSERT "
            f"({self._format_column_list(plan.sync_columns)}) VALUES "
            f"({self._format_source_column_list(plan.sync_columns, source_alias=source_alias)})"
        )
        merge_lines.append(f"OUTPUT $action INTO {SYNC_ACTIONS_TABLE_NAME};")
        merge_lines.append(
            "SELECT "
            "SUM(CASE WHEN [action] = 'INSERT' THEN 1 ELSE 0 END) AS inserted_count, "
            "SUM(CASE WHEN [action] = 'UPDATE' THEN 1 ELSE 0 END) AS updated_count "
            f"FROM {SYNC_ACTIONS_TABLE_NAME};"
        )
        return "\n".join(merge_lines)

    def _build_primary_key_join(
        self,
        primary_key_columns: Sequence[SqlServerColumnMetadata],
    ) -> str:
        return " AND ".join(
            f"target.{self._quote_identifier(column.name)} = source.{self._quote_identifier(column.name)}"
            for column in primary_key_columns
        )

    def _build_update_assignments(
        self,
        updatable_columns: Sequence[SqlServerColumnMetadata],
    ) -> str:
        return ", ".join(
            f"target.{self._quote_identifier(column.name)} = source.{self._quote_identifier(column.name)}"
            for column in updatable_columns
        )

    def _build_update_condition(
        self,
        updatable_columns: Sequence[SqlServerColumnMetadata],
    ) -> str:
        return " OR ".join(
            self._build_column_difference_condition(column)
            for column in updatable_columns
        )

    def _build_column_difference_condition(
        self,
        column: SqlServerColumnMetadata,
    ) -> str:
        quoted_name = self._quote_identifier(column.name)
        if column.normalized_type_name in TEXT_TYPE_NAMES:
            return (
                "("
                f"(target.{quoted_name} IS NULL AND source.{quoted_name} IS NOT NULL) OR "
                f"(target.{quoted_name} IS NOT NULL AND source.{quoted_name} IS NULL) OR "
                f"(target.{quoted_name} COLLATE DATABASE_DEFAULT <> "
                f"source.{quoted_name} COLLATE DATABASE_DEFAULT)"
                ")"
            )
        if column.normalized_type_name == "bit":
            return (
                f"ISNULL(CAST(target.{quoted_name} AS INT), -1) "
                f"<> ISNULL(CAST(source.{quoted_name} AS INT), -1)"
            )
        return (
            "("
            f"(target.{quoted_name} IS NULL AND source.{quoted_name} IS NOT NULL) OR "
            f"(target.{quoted_name} IS NOT NULL AND source.{quoted_name} IS NULL) OR "
            f"(target.{quoted_name} <> source.{quoted_name})"
            ")"
        )

    def _build_order_by_clause(
        self,
        primary_key_columns: Sequence[SqlServerColumnMetadata],
    ) -> str:
        if not primary_key_columns:
            return ""
        return " ORDER BY " + ", ".join(
            self._quote_identifier(column.name) for column in primary_key_columns
        )

    def _format_column_list(self, columns: Sequence[SqlServerColumnMetadata]) -> str:
        return ", ".join(self._quote_identifier(column.name) for column in columns)

    def _format_source_column_list(
        self,
        columns: Sequence[SqlServerColumnMetadata],
        *,
        source_alias: str,
    ) -> str:
        return ", ".join(
            f"{source_alias}.{self._quote_identifier(column.name)}" for column in columns
        )

    def _format_linked_server_table_name(
        self,
        *,
        linked_server_name: str,
        source_database_name: str,
        table: SqlServerTableReference,
    ) -> str:
        return ".".join(
            [
                self._quote_identifier(linked_server_name),
                self._quote_identifier(source_database_name),
                self._quote_identifier(table.schema_name),
                self._quote_identifier(table.table_name),
            ]
        )

    def _format_table_name(self, *, schema_name: str, table_name: str) -> str:
        return ".".join(
            [self._quote_identifier(schema_name), self._quote_identifier(table_name)]
        )

    def _quote_identifier(self, name: str) -> str:
        return f"[{name.replace(']', ']]')}]"


class SqlServerModelSyncExecutor:
    def __init__(
        self,
        *,
        engine_factory: SqlServerEngineFactory,
        metadata_loader: SqlServerMetadataLoader,
        sync_plan_builder: SqlServerSyncPlanBuilder,
        sql_builder: SqlServerSyncSqlBuilder,
        batch_size: int = 1000,
    ) -> None:
        self._engine_factory = engine_factory
        self._metadata_loader = metadata_loader
        self._sync_plan_builder = sync_plan_builder
        self._sql_builder = sql_builder
        self._batch_size = batch_size

    def check_connections(
        self,
        *,
        source_settings: SqlServerConnectionSettings,
        target_settings: SqlServerConnectionSettings,
    ) -> None:
        self._check_connection(settings=source_settings)
        self._check_connection(settings=target_settings)

    def execute(
        self,
        *,
        source_settings: SqlServerConnectionSettings,
        target_settings: SqlServerConnectionSettings,
        table: SqlServerTableReference,
        linked_server_name: str | None = None,
        override: SqlServerSyncTableOverride | None = None,
    ) -> SqlServerModelSyncStats:
        source_engine = self._engine_factory.create_engine(source_settings)
        target_engine = self._engine_factory.create_engine(target_settings)
        try:
            with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
                source_columns = self._metadata_loader.load(source_connection, table)
                target_columns = self._metadata_loader.load(target_connection, table)
                plan = self._sync_plan_builder.build(
                    table=table,
                    source_columns=source_columns,
                    target_columns=target_columns,
                    override=override,
                )
                if linked_server_name:
                    return self._execute_linked_server_merge(
                        target_connection=target_connection,
                        plan=plan,
                        linked_server_name=linked_server_name,
                        source_database_name=source_settings.database_name,
                    )
                return self._execute_staging_merge(
                    source_connection=source_connection,
                    target_connection=target_connection,
                    plan=plan,
                )
        finally:
            source_engine.dispose()
            target_engine.dispose()

    def _check_connection(self, *, settings: SqlServerConnectionSettings) -> None:
        engine = self._engine_factory.create_engine(settings)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise SqlServerConnectionError(
                f"Could not connect to {settings.host}:{settings.port}/{settings.database_name}: {exc}"
            ) from exc
        finally:
            engine.dispose()

    def _execute_staging_merge(
        self,
        *,
        source_connection,
        target_connection,
        plan: SqlServerTableSyncPlan,
    ) -> SqlServerModelSyncStats:
        target_connection.exec_driver_sql(self._sql_builder.build_stage_table_query(plan))
        source_result = source_connection.execution_options(stream_results=True).exec_driver_sql(
            self._sql_builder.build_source_select_query(plan)
        )
        source_row_count = 0
        try:
            stage_insert_query = self._sql_builder.build_stage_insert_query(plan)
            while True:
                rows = source_result.fetchmany(self._batch_size)
                if not rows:
                    break
                source_row_count += len(rows)
                target_connection.exec_driver_sql(
                    stage_insert_query,
                    [tuple(row) for row in rows],
                )
        finally:
            source_result.close()
        stats = self._run_merge_query(
            target_connection=target_connection,
            plan=plan,
            merge_query=self._sql_builder.build_stage_merge_query(plan),
        )
        return SqlServerModelSyncStats(
            mode="staging",
            inserted_count=stats.inserted_count,
            updated_count=stats.updated_count,
            source_row_count=source_row_count,
        )

    def _execute_linked_server_merge(
        self,
        *,
        target_connection,
        plan: SqlServerTableSyncPlan,
        linked_server_name: str,
        source_database_name: str,
    ) -> SqlServerModelSyncStats:
        stats = self._run_merge_query(
            target_connection=target_connection,
            plan=plan,
            merge_query=self._sql_builder.build_linked_server_merge_query(
                plan=plan,
                linked_server_name=linked_server_name,
                source_database_name=source_database_name,
            ),
        )
        return SqlServerModelSyncStats(
            mode="linked_server",
            inserted_count=stats.inserted_count,
            updated_count=stats.updated_count,
            source_row_count=None,
        )

    def _run_merge_query(
        self,
        *,
        target_connection,
        plan: SqlServerTableSyncPlan,
        merge_query: str,
    ) -> SqlServerModelSyncStats:
        identity_primary_key = plan.identity_primary_key
        if identity_primary_key is not None:
            target_connection.exec_driver_sql(
                self._sql_builder.build_identity_insert_toggle_query(
                    plan=plan,
                    enabled=True,
                )
            )
        try:
            row = target_connection.exec_driver_sql(merge_query).mappings().one()
        finally:
            if identity_primary_key is not None:
                target_connection.exec_driver_sql(
                    self._sql_builder.build_identity_insert_toggle_query(
                        plan=plan,
                        enabled=False,
                    )
                )
        inserted_count = int(row["inserted_count"] or 0)
        updated_count = int(row["updated_count"] or 0)
        return SqlServerModelSyncStats(
            mode="merge",
            inserted_count=inserted_count,
            updated_count=updated_count,
            source_row_count=None,
        )
