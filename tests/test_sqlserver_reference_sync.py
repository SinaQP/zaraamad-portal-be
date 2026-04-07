from app.common.services.sqlserver_reference_sync import (
    SqlServerColumnMetadata,
    SqlServerSyncSqlBuilder,
    SqlServerTableReference,
    SqlServerTableSyncPlan,
)


def _build_plan() -> SqlServerTableSyncPlan:
    primary_key = SqlServerColumnMetadata(
        name="Id",
        type_name="int",
        is_nullable=False,
        is_primary_key=True,
        primary_key_ordinal=1,
        is_identity=True,
    )
    title = SqlServerColumnMetadata(
        name="Title",
        type_name="nvarchar",
        is_nullable=True,
        is_primary_key=False,
        primary_key_ordinal=None,
        is_identity=False,
    )
    is_active = SqlServerColumnMetadata(
        name="IsActive",
        type_name="bit",
        is_nullable=True,
        is_primary_key=False,
        primary_key_ordinal=None,
        is_identity=False,
    )
    table = SqlServerTableReference(
        model_name="Menus",
        schema_name="dbo",
        table_name="Menus",
    )
    return SqlServerTableSyncPlan(
        table=table,
        source_columns=(primary_key, title, is_active),
        target_columns=(primary_key, title, is_active),
        sync_columns=(primary_key, title, is_active),
        primary_key_columns=(primary_key,),
    )


def test_stage_merge_query_is_insert_update_only() -> None:
    builder = SqlServerSyncSqlBuilder()

    query = builder.build_stage_merge_query(_build_plan())

    assert "WHEN NOT MATCHED BY TARGET THEN INSERT" in query
    assert "WHEN NOT MATCHED BY SOURCE THEN DELETE" not in query
    assert "COLLATE DATABASE_DEFAULT" in query
    assert "CAST(target.[IsActive] AS INT)" in query


def test_linked_server_merge_query_uses_four_part_name() -> None:
    builder = SqlServerSyncSqlBuilder()

    query = builder.build_linked_server_merge_query(
        plan=_build_plan(),
        linked_server_name="REMOTE_SYNC",
        source_database_name="online_db",
    )

    assert "[REMOTE_SYNC].[online_db].[dbo].[Menus]" in query
