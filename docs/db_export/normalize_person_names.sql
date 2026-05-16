SET NOCOUNT ON;
SET XACT_ABORT ON;

/*
    Manual SQL equivalent for Django migration:
    apps/core/migrations/0042_normalize_person_names.py

    Target table:
        [Cor].[Persons]

    Target columns:
        [FirstName], [LastName]

    Set @ApplyChanges = 1 only after reviewing the preview output.
*/

DECLARE @ApplyChanges bit = 0;
DECLARE @BatchSize int = 500;

DECLARE @TextReplacements TABLE (
    [Step] int IDENTITY(1, 1) PRIMARY KEY,
    [FindText] nchar(1) NOT NULL,
    [ReplacementText] nvarchar(1) NOT NULL
);

INSERT INTO @TextReplacements ([FindText], [ReplacementText])
VALUES
    (NCHAR(0x0623), NCHAR(0x0627)),
    (NCHAR(0x0625), NCHAR(0x0627)),
    (NCHAR(0x0629), NCHAR(0x0647)),
    (NCHAR(0x0640), N''),
    (NCHAR(0x064A), NCHAR(0x06CC)),
    (NCHAR(0x0649), NCHAR(0x06CC)),
    (NCHAR(0x064B), N''),
    (NCHAR(0x064C), N''),
    (NCHAR(0x064D), N''),
    (NCHAR(0x064E), N''),
    (NCHAR(0x064F), N''),
    (NCHAR(0x0650), N''),
    (NCHAR(0x0651), N''),
    (NCHAR(0x0652), N''),
    (NCHAR(0x0653), N''),
    (NCHAR(0x0654), N''),
    (NCHAR(0x0655), N''),
    (NCHAR(0x0670), N''),
    (NCHAR(0x0671), NCHAR(0x0627)),
    (NCHAR(0x06BE), NCHAR(0x0647)),
    (NCHAR(0x06C0), NCHAR(0x0647)),
    (NCHAR(0x06C1), NCHAR(0x0647)),
    (NCHAR(0x06D2), NCHAR(0x06CC)),
    (NCHAR(0x06D5), NCHAR(0x0647)),
    (NCHAR(0x0643), NCHAR(0x06A9)),
    (NCHAR(0x200C), N' '),
    (NCHAR(0x200D), N''),
    (NCHAR(0x200E), N' '),
    (NCHAR(0x200F), N' '),
    (NCHAR(0x2060), N' '),
    (NCHAR(0xFEFF), N' '),
    (NCHAR(0x00A0), N' '),
    (NCHAR(0x0009), N' '),
    (NCHAR(0x000A), N' '),
    (NCHAR(0x000B), N' '),
    (NCHAR(0x000C), N' '),
    (NCHAR(0x000D), N' ');

IF OBJECT_ID('tempdb..#NormalizedPersons') IS NOT NULL
    DROP TABLE #NormalizedPersons;

BEGIN TRY
    SELECT
        p.[Id],
        p.[FirstName] AS [OldFirstName],
        p.[LastName] AS [OldLastName],
        CONVERT(NVARCHAR(60), p.[FirstName]) AS [NewFirstName],
        CONVERT(NVARCHAR(60), p.[LastName]) AS [NewLastName],
        CONVERT(bit, 0) AS [IsProcessed]
    INTO #NormalizedPersons
    FROM [Cor].[Persons] AS p;

    DECLARE @Step int = 1;
    DECLARE @MaxStep int = (SELECT MAX([Step]) FROM @TextReplacements);
    DECLARE @FindText nchar(1);
    DECLARE @ReplacementText nvarchar(1);

    WHILE @Step <= @MaxStep
    BEGIN
        SELECT
            @FindText = [FindText],
            @ReplacementText = [ReplacementText]
        FROM @TextReplacements
        WHERE [Step] = @Step;

        UPDATE #NormalizedPersons
        SET
            [NewFirstName] = REPLACE(
                [NewFirstName] COLLATE Latin1_General_100_BIN2,
                @FindText COLLATE Latin1_General_100_BIN2,
                @ReplacementText COLLATE Latin1_General_100_BIN2
            ),
            [NewLastName] = REPLACE(
                [NewLastName] COLLATE Latin1_General_100_BIN2,
                @FindText COLLATE Latin1_General_100_BIN2,
                @ReplacementText COLLATE Latin1_General_100_BIN2
            );

        SET @Step = @Step + 1;
    END;

    UPDATE #NormalizedPersons
    SET
        [NewFirstName] = CONVERT(NVARCHAR(60), LTRIM(RTRIM([NewFirstName]))),
        [NewLastName] = CONVERT(NVARCHAR(60), LTRIM(RTRIM([NewLastName])));

    WHILE EXISTS (
        SELECT 1
        FROM #NormalizedPersons
        WHERE [NewFirstName] LIKE N'%  %'
           OR [NewLastName] LIKE N'%  %'
    )
    BEGIN
        UPDATE #NormalizedPersons
        SET
            [NewFirstName] = REPLACE([NewFirstName], N'  ', N' '),
            [NewLastName] = REPLACE([NewLastName], N'  ', N' ')
        WHERE [NewFirstName] LIKE N'%  %'
           OR [NewLastName] LIKE N'%  %';
    END;

    UPDATE #NormalizedPersons
    SET
        [NewFirstName] = CONVERT(NVARCHAR(60), LTRIM(RTRIM([NewFirstName]))),
        [NewLastName] = CONVERT(NVARCHAR(60), LTRIM(RTRIM([NewLastName])));

    DELETE FROM #NormalizedPersons
    WHERE ISNULL([OldFirstName], N'') COLLATE Latin1_General_100_BIN2
          = ISNULL([NewFirstName], N'') COLLATE Latin1_General_100_BIN2
      AND ISNULL([OldLastName], N'') COLLATE Latin1_General_100_BIN2
          = ISNULL([NewLastName], N'') COLLATE Latin1_General_100_BIN2;

    CREATE UNIQUE CLUSTERED INDEX [IX_NormalizedPersons_Id]
        ON #NormalizedPersons ([Id]);

    SELECT COUNT_BIG(1) AS [RowsToUpdate]
    FROM #NormalizedPersons;

    SELECT TOP (50)
        [Id],
        [OldFirstName],
        [NewFirstName],
        [OldLastName],
        [NewLastName]
    FROM #NormalizedPersons
    ORDER BY [Id];

    IF @ApplyChanges = 1
    BEGIN
        DECLARE @UpdatedRows bigint = 0;
        DECLARE @BatchRows int = 1;

        WHILE @BatchRows > 0
        BEGIN
            BEGIN TRANSACTION;

            ;WITH BatchRows AS (
                SELECT TOP (@BatchSize)
                    [Id],
                    [NewFirstName],
                    [NewLastName]
                FROM #NormalizedPersons
                WHERE [IsProcessed] = 0
                ORDER BY [Id]
            )
            UPDATE p
            SET
                p.[FirstName] = b.[NewFirstName],
                p.[LastName] = b.[NewLastName]
            FROM [Cor].[Persons] AS p WITH (UPDLOCK, ROWLOCK)
            INNER JOIN BatchRows AS b ON b.[Id] = p.[Id];

            SET @BatchRows = @@ROWCOUNT;

            ;WITH BatchIds AS (
                SELECT TOP (@BatchSize) [Id]
                FROM #NormalizedPersons
                WHERE [IsProcessed] = 0
                ORDER BY [Id]
            )
            UPDATE n
            SET [IsProcessed] = 1
            FROM #NormalizedPersons AS n
            INNER JOIN BatchIds AS b ON b.[Id] = n.[Id];

            COMMIT TRANSACTION;

            SET @UpdatedRows = @UpdatedRows + @BatchRows;
        END;

        SELECT @UpdatedRows AS [UpdatedRows];
    END
    ELSE
    BEGIN
        SELECT CAST(0 AS int) AS [UpdatedRows];
    END;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;

IF OBJECT_ID('tempdb..#NormalizedPersons') IS NOT NULL
    DROP TABLE #NormalizedPersons;
