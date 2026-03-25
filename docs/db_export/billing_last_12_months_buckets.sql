DECLARE @start_month date = DATEADD(MONTH, -11, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1));
DECLARE @current_month date = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
DECLARE @next_month date = DATEADD(MONTH, 1, @current_month);
DECLARE @other_label nvarchar(10) = NCHAR(1587) + NCHAR(1575) + NCHAR(1740) + NCHAR(1585);

/* Registered income by selected parent income codes for charting.
   Bills are treated as initially registered only when they have BillCode/Bill_code. */
;WITH target_roots AS (
    SELECT 1 AS sort_order, '110400' AS root_code
    UNION ALL SELECT 2, '110500'
    UNION ALL SELECT 3, '110300'
    UNION ALL SELECT 4, '110000'
    UNION ALL SELECT 5, '110200'
),
root_income_codes AS (
    SELECT
        tr.sort_order,
        tr.root_code,
        ic.[id] AS root_income_code_id,
        ic.[Desc] AS root_desc
    FROM target_roots tr
    LEFT JOIN [Cor].[IncomeCodes] ic
        ON ic.[Code] = tr.root_code
       AND ISNULL(ic.[IsDeleted], 0) = 0
),
income_tree AS (
    SELECT
        ric.sort_order,
        ric.root_code,
        ric.root_income_code_id AS income_code_id,
        0 AS distance_from_root
    FROM root_income_codes ric
    WHERE ric.root_income_code_id IS NOT NULL

    UNION ALL

    SELECT
        it.sort_order,
        it.root_code,
        child.[id] AS income_code_id,
        it.distance_from_root + 1 AS distance_from_root
    FROM income_tree it
    INNER JOIN [Cor].[IncomeCodes] child
        ON child.[ParentId] = it.income_code_id
       AND ISNULL(child.[IsDeleted], 0) = 0
),
selected_income_map AS (
    SELECT
        ranked.root_code,
        ranked.income_code_id
    FROM (
        SELECT
            it.root_code,
            it.income_code_id,
            ROW_NUMBER() OVER (
                PARTITION BY it.income_code_id
                ORDER BY it.distance_from_root ASC, it.sort_order ASC
            ) AS rn
        FROM income_tree it
    ) ranked
    WHERE ranked.rn = 1
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
bucketed_amounts AS (
    SELECT
        COALESCE(sim.root_code, @other_label) AS bucket_code,
        SUM(ISNULL(bd.[Creditor], 0) + ISNULL(bd.[Penalty], 0)) AS registered_income_amount_12m
    FROM [Cor].[BillDetails] bd
    INNER JOIN eligible_bills b
        ON b.[id] = bd.[BillId]
    LEFT JOIN selected_income_map sim
        ON sim.income_code_id = bd.[IncomeCodeId]
    WHERE ISNULL(bd.[IsDeleted], 0) = 0
    GROUP BY COALESCE(sim.root_code, @other_label)
),
other_income_code_amounts AS (
    SELECT
        ic.[id] AS income_code_id,
        ic.[Code] AS income_code,
        ic.[Desc] AS income_desc,
        SUM(ISNULL(bd.[Creditor], 0) + ISNULL(bd.[Penalty], 0)) AS registered_income_amount_12m
    FROM [Cor].[BillDetails] bd
    INNER JOIN eligible_bills b
        ON b.[id] = bd.[BillId]
    INNER JOIN [Cor].[IncomeCodes] ic
        ON ic.[id] = bd.[IncomeCodeId]
       AND ISNULL(ic.[IsDeleted], 0) = 0
    LEFT JOIN selected_income_map sim
        ON sim.income_code_id = bd.[IncomeCodeId]
    WHERE ISNULL(bd.[IsDeleted], 0) = 0
      AND sim.income_code_id IS NULL
    GROUP BY
        ic.[id],
        ic.[Code],
        ic.[Desc]
),
base_chart_rows AS (
    SELECT
        ric.sort_order,
        ric.root_code AS bucket_code,
        CASE
            WHEN ric.root_desc IS NULL OR LTRIM(RTRIM(ric.root_desc)) = ''
                THEN ric.root_code
            ELSE ric.root_code + N' - ' + ric.root_desc
        END AS chart_label,
        ISNULL(ba.registered_income_amount_12m, 0) AS registered_income_amount_12m
    FROM root_income_codes ric
    LEFT JOIN bucketed_amounts ba
        ON ba.bucket_code = ric.root_code
),
zero_root_slots AS (
    SELECT
        bcr.sort_order,
        ROW_NUMBER() OVER (ORDER BY bcr.sort_order) AS slot_no
    FROM base_chart_rows bcr
    WHERE bcr.registered_income_amount_12m = 0
),
replacement_candidates AS (
    SELECT
        ROW_NUMBER() OVER (
            ORDER BY oica.registered_income_amount_12m DESC, oica.income_code ASC
        ) AS slot_no,
        oica.income_code AS bucket_code,
        CASE
            WHEN oica.income_desc IS NULL OR LTRIM(RTRIM(oica.income_desc)) = ''
                THEN oica.income_code
            ELSE oica.income_code + N' - ' + oica.income_desc
        END AS chart_label,
        oica.registered_income_amount_12m
    FROM other_income_code_amounts oica
    WHERE oica.registered_income_amount_12m > 0
),
promoted_replacements AS (
    SELECT
        zrs.sort_order,
        rc.bucket_code,
        rc.chart_label,
        rc.registered_income_amount_12m
    FROM zero_root_slots zrs
    INNER JOIN replacement_candidates rc
        ON rc.slot_no = zrs.slot_no
),
other_totals AS (
    SELECT
        ISNULL(MAX(CASE WHEN ba.bucket_code = @other_label THEN ba.registered_income_amount_12m END), 0) AS other_total
    FROM bucketed_amounts ba
),
promoted_totals AS (
    SELECT
        ISNULL(SUM(pr.registered_income_amount_12m), 0) AS promoted_total
    FROM promoted_replacements pr
),
chart_rows AS (
    SELECT
        bcr.sort_order,
        ISNULL(pr.bucket_code, bcr.bucket_code) AS bucket_code,
        ISNULL(pr.chart_label, bcr.chart_label) AS chart_label,
        ISNULL(pr.registered_income_amount_12m, bcr.registered_income_amount_12m) AS registered_income_amount_12m
    FROM base_chart_rows bcr
    LEFT JOIN promoted_replacements pr
        ON pr.sort_order = bcr.sort_order
    UNION ALL

    SELECT
        999 AS sort_order,
        N'OTHER' AS bucket_code,
        @other_label AS chart_label,
        CASE
            WHEN ot.other_total - pt.promoted_total < 0 THEN 0
            ELSE ot.other_total - pt.promoted_total
        END AS registered_income_amount_12m
    FROM other_totals ot
    CROSS JOIN promoted_totals pt
)
SELECT
    bucket_code,
    chart_label,
    registered_income_amount_12m
FROM chart_rows
ORDER BY sort_order
OPTION (MAXRECURSION 100);
