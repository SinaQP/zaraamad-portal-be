/*
12-month billing report

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
*/

DECLARE @start_month date = DATEADD(MONTH, -11, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1));
DECLARE @current_month date = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
DECLARE @next_month date = DATEADD(MONTH, 1, @current_month);
DECLARE @other_label nvarchar(10) = NCHAR(1587) + NCHAR(1575) + NCHAR(1740) + NCHAR(1585);

/* Total summary for the last 12 months */
;WITH source_bills AS (
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
      AND b.[CreationDateTime] >= @start_month
      AND b.[CreationDateTime] < @next_month
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
    GROUP BY b.[id]
)
SELECT
    SUM(registered_income_amount) AS registered_income_amount_12m,
    COUNT(*) AS issued_bills_count_12m,
    SUM(is_paid) AS paid_bills_count_12m,
    CAST(
        CASE
            WHEN COUNT(*) = 0 THEN 0
            ELSE 100.0 * SUM(is_paid) / COUNT(*)
        END
        AS decimal(5,2)
    ) AS collection_rate_percent_12m
FROM bill_facts;
