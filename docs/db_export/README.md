# DB Export Inputs

This folder contains ready-to-run inputs for:

```bash
python -m app.commands.export_db_results
```

Files:

- `servers_from_pdf.csv`
  extracted from `Converts3 (2).pdf`
  columns: `ip,port,username,password`
- `billing_last_12_months_monthly.sql`
  monthly 12-month billing result set
- `billing_last_12_months_summary.sql`
  total 12-month summary result set
- `billing_last_12_months_buckets.sql`
  income bucket result set
- `normalize_person_names.sql`
  preview/apply script for normalizing `[Cor].[Persons]` first and last names

Why the SQL was split:

- the original `billing_last_12_months_report.sql` contains 3 separate `SELECT` result sets
- the export command runs one query and writes one result set per database
- use one of the split files per run

Example commands:

```bash
python -m app.commands.export_db_results --input ./docs/db_export/servers_from_pdf.csv --query-file ./docs/db_export/billing_last_12_months_summary.sql --output ./docs/db_export/db_results_summary.xlsx
```

```bash
python -m app.commands.export_db_results --input ./docs/db_export/servers_from_pdf.csv --query-file ./docs/db_export/billing_last_12_months_monthly.sql --output ./docs/db_export/db_results_monthly.xlsx
```

```bash
python -m app.commands.export_db_results --input ./docs/db_export/servers_from_pdf.csv --query-file ./docs/db_export/billing_last_12_months_buckets.sql --output ./docs/db_export/db_results_buckets.xlsx
```

Preview person-name normalization across the configured SQL Server targets. Pass `--database` for the exact customer database name so the command does not scan every non-system database on each server:

```bash
python -m app.commands.export_db_results --input ./docs/db_export/servers_from_pdf.csv --database <database_name> --query-file ./docs/db_export/normalize_person_names.sql --output ./docs/db_export/normalize_person_names_preview.xlsx --allow-write
```

The normalization SQL defaults to `@ApplyChanges = 0`, so this command only writes temp tables and exports `RowsToUpdate`, `UpdatedRows`, and up to 50 preview rows per database. After reviewing the preview workbook, set `@ApplyChanges = 1` in `normalize_person_names.sql` and rerun with a new output file to apply the changes.
