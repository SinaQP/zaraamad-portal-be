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
