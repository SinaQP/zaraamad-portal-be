/*
12-month billing report for Persian year 1404

Metrics:
1. Registered income
2. Collection rate of issued bills
3. Issued bills count

Assumptions:
- Only active records are included.
- For reporting, both [IsDeleted] and [Invalid] must be 0.
- Bills are treated as initially registered only when they have BillCode/Bill_code.
- Registered income = SUM([Creditor] + [Penalty]) from bill details.
- Collection rate = paid bills / issued bills * 100

Persian year 1404:
1404/01/01 = 2025-03-21
1405/01/01 = 2026-03-21
*/

DECLARE @start_date date = '2025-03-21'; -- 1404/01/01
DECLARE @end_date   date = '2026-03-21'; -- exclusive upper bound (1405/01/01)

/* Monthly breakdown for Persian year 1404 */
;WITH months AS (
    SELECT CAST('2025-03-21' AS date) AS month_start, CAST('2025-04-21' AS date) AS next_month_start, N'1404/01' AS month_label
    UNION ALL SELECT '2025-04-21', '2025-05-22', N'1404/02'
    UNION ALL SELECT '2025-05-22', '2025-06-22', N'1404/03'
    UNION ALL SELECT '2025-06-22', '2025-07-23', N'1404/04'
    UNION ALL SELECT '2025-07-23', '2025-08-23', N'1404/05'
    UNION ALL SELECT '2025-08-23', '2025-09-23', N'1404/06'
    UNION ALL SELECT '2025-09-23', '2025-10-23', N'1404/07'
    UNION ALL SELECT '2025-10-23', '2025-11-22', N'1404/08'
    UNION ALL SELECT '2025-11-22', '2025-12-22', N'1404/09'
    UNION ALL SELECT '2025-12-22', '2026-01-21', N'1404/10'
    UNION ALL SELECT '2026-01-21', '2026-02-20', N'1404/11'
    UNION ALL SELECT '2026-02-20', '2026-03-21', N'1404/12'
),
source_bills AS (
    SELECT
        b.[id],
        b.[CreationDateTime],
        COALESCE(
            NULLIF(
                LTRIM(RTRIM(bill_xml.bill_row_xml.value('string((/row/@BillCode)[1])', 'nvarchar(255)'))),
                N''
            ),
            NULLIF(
                LTRIM(RTRIM(bill_xml.bill_row_xml.value('string((/row/@Bill_code)[1])', 'nvarchar(255)'))),
                N''
            )
        ) AS bill_code
    FROM [Cor].[Bills] b
    CROSS APPLY (
        SELECT (SELECT b.* FOR XML RAW('row'), TYPE) AS bill_row_xml
    ) bill_xml
    WHERE ISNULL(b.[IsDeleted], 0) = 0
      AND ISNULL(b.[Invalid], 0) = 0
      AND b.[CreationDateTime] >= @start_date
      AND b.[CreationDateTime] < @end_date
),
eligible_bills AS (
    SELECT
        sb.[id],
        sb.[CreationDateTime]
    FROM source_bills sb
    WHERE sb.bill_code IS NOT NULL
),
bill_facts AS (
    SELECT
        b.[id] AS bill_id,
        m.month_label,
        SUM(ISNULL(bd.[Creditor], 0) + ISNULL(bd.[Penalty], 0)) AS registered_income_amount,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM [Cor].[Payments] p
                WHERE p.[BillId] = b.[id]
                  AND ISNULL(p.[IsDeleted], 0) = 0
            ) THEN 1
            ELSE 0
        END AS is_paid
    FROM eligible_bills b
    INNER JOIN [Cor].[BillDetails] bd
        ON bd.[BillId] = b.[id]
       AND ISNULL(bd.[IsDeleted], 0) = 0
    INNER JOIN months m
        ON b.[CreationDateTime] >= m.month_start
       AND b.[CreationDateTime] < m.next_month_start
    GROUP BY
        b.[id],
        m.month_label
),
monthly AS (
    SELECT
        month_label,
        COUNT(*) AS issued_bills_count,
        SUM(registered_income_amount) AS registered_income_amount,
        SUM(is_paid) AS paid_bills_count
    FROM bill_facts
    GROUP BY month_label
)
SELECT
    m.month_label AS [month],
    ISNULL(x.registered_income_amount, 0) AS registered_income_amount,
    ISNULL(x.issued_bills_count, 0) AS issued_bills_count,
    ISNULL(x.paid_bills_count, 0) AS paid_bills_count,
    CAST(
        CASE
            WHEN ISNULL(x.issued_bills_count, 0) = 0 THEN 0
            ELSE 100.0 * x.paid_bills_count / x.issued_bills_count
        END
        AS decimal(5,2)
    ) AS collection_rate_percent
FROM months m
LEFT JOIN monthly x
    ON x.month_label = m.month_label
ORDER BY m.month_start;
