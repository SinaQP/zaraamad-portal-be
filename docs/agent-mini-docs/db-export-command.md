# DB Export Command Mini-Doc

## Scope
- File: `app/commands/export_db_results.py`
- Command purpose: scan SQL Server instances from an input list, discover non-system databases, run one SQL query per database, and write results/errors into an Excel workbook.

## Inputs
- `--input`: `.csv` or `.xlsx` with connection columns (`ip/host`, optional `port`, `username`, `password`).
- `--query` or `--query-file`: SQL text to run on each discovered database.
- `--output`: destination workbook path.
- `--database`: optional exact database name to run against on every server. When omitted, the command discovers and scans all non-system databases.

## Execution modes
- Default mode (read-only):
  - query is validated by `validate_read_only_query`.
  - transaction is always rolled back per database.
  - disallows write tokens such as `update`, `delete`, `insert`, `drop`, `create`.
- Write-enabled mode (`--allow-write`):
  - read-only validation is skipped.
  - transaction is committed per database after successful execution.
  - result rows include `scan_status=write_ok` and optional `affected_row_count` for non-row-returning statements.

## Person-name normalization SQL
- File: `docs/db_export/normalize_person_names.sql`.
- Purpose: normalize `[Cor].[Persons].[FirstName]` and `[LastName]` Persian/Arabic character variants and whitespace.
- Default is preview mode: `DECLARE @ApplyChanges bit = 0;`.
- The script intentionally emits one final result set only, with `RowsToUpdate`, `UpdatedRows`, and up to 50 preview rows. This keeps it compatible with `export_db_results`, which exports one result set per database.
- To apply real changes, review the preview workbook first, then set `@ApplyChanges = 1` and run the command with `--allow-write`.
- For this script, prefer passing `--database <name>` so the write path does not touch every non-system database on each server.

## Output workbook
- `results` sheet:
  - base columns: `server_ip`, `port`, `database_name`, `scan_status`
  - query columns are appended dynamically when the query returns rows
  - extra runtime columns (for example `affected_row_count`) are also appended dynamically
- `errors` sheet:
  - `server_ip`, `port`, `database_name`, `error_message`

## Summary counters
- `servers_processed`: number of valid input server rows attempted.
- `databases_scanned`: number of discovered databases attempted.
- `success_count`: per-database successful executions.
- `error_count`: input validation and execution failures.
