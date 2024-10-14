CREATE PROCEDURE [dbo].[usp_CreateAndPopulateDimTables]
AS
BEGIN
    -- Step 1: Create Tables
    -- Create cms_provider_dim_drug table
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='cms_provider_dim_drug' AND xtype='U')
    BEGIN
        CREATE TABLE [dbo].[cms_provider_dim_drug]
        (
            [Brnd_Name] [varchar](8000)  NULL,
	        [Gnrc_Name] [varchar](8000)  NULL,
	        [Max_Year] [int]  NULL,
	        [Min_Year] [int]  NULL,
	        [drug_key] [bigint]  NULL
        )
    END

    -- Create cms_provider_dim_geography table
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='cms_provider_dim_geography' AND xtype='U')
    BEGIN
        CREATE TABLE [dbo].[cms_provider_dim_geography]
        (
	        [Prscrbr_City] [varchar](8000)  NULL,
	        [Prscrbr_City_State] [varchar](8000)  NULL,
	        [Prscrbr_State_Abrvtn] [varchar](8000)  NULL,
	        [Prscrbr_State_FIPS] [varchar](8000)  NULL,
	        [Max_Year] [int]  NULL,
	        [Min_Year] [int]  NULL,
	        [geo_key] [bigint]  NULL
        )
    END    
    
    -- Create cms_provider_dim_provider table
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='cms_provider_dim_provider' AND xtype='U')
    BEGIN
        CREATE TABLE [dbo].[cms_provider_dim_provider]
        (
	           [Prscrbr_First_Name] [varchar](8000)  NULL,
	           [Prscrbr_Full_Name] [varchar](8000)  NULL,
	           [Prscrbr_Last_Org_Name] [varchar](8000)  NULL,
	           [Prscrbr_NPI] [int]  NULL,
	           [Prscrbr_Type] [varchar](8000)  NULL,
	           [Prscrbr_Type_Src] [varchar](8000)  NULL,
	           [Max_Year] [int]  NULL,
	           [Min_Year] [int]  NULL,
	           [provider_key] [bigint]  NULL
        )
    END 

    -- Create cms_provider_dim_year table
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='cms_provider_dim_year' AND xtype='U')
    BEGIN
        CREATE TABLE [dbo].[cms_provider_dim_year]
        (
            [Year] [int]  NULL,
            [Year_Date_Key] [date]  NULL
        )
    END

    -- Step 2: Populate Tables
    -- Populate cms_provider_dim_drug
    INSERT INTO [dbo].[cms_provider_dim_drug] (Brnd_Name, Gnrc_Name, Max_Year, Min_Year, drug_key)
    SELECT [Brnd_Name]
          ,[Gnrc_Name]
          ,MAX([Year]) AS [Max_Year]
          ,MIN([Year]) AS [Min_Year]
          ,ROW_NUMBER() OVER (ORDER BY [Brnd_Name],[Gnrc_Name] ASC) AS [drug_key]
    FROM [cms_lakehouse].[dbo].[cms_provider_drug_costs]
    GROUP BY [Brnd_Name],[Gnrc_Name]

    -- Populate cms_provider_dim_geography
    INSERT INTO [dbo].[cms_provider_dim_geography] (Prscrbr_City, Prscrbr_City_State, Prscrbr_State_Abrvtn, Prscrbr_State_FIPS, Max_Year, Min_Year, geo_key)
    SELECT [Prscrbr_City]
          ,(CASE WHEN [Prscrbr_City_State] IS NULL THEN 'XX' ELSE [Prscrbr_City_State] END) AS [Prscrbr_City_State]
          ,[Prscrbr_State_Abrvtn]
          ,[Prscrbr_State_FIPS]
          ,MAX([Year]) AS [Max_Year]
          ,MIN([Year]) AS [Min_Year]
          ,row_number() OVER (ORDER BY [Prscrbr_State_Abrvtn],[Prscrbr_City_State] ASC) AS [geo_key]
FROM [cms_lakehouse].[dbo].[cms_provider_drug_costs]
GROUP BY [Prscrbr_City],[Prscrbr_City_State],[Prscrbr_State_Abrvtn],[Prscrbr_State_FIPS]

    -- Populate cms_provider_dim_provider
    INSERT INTO [dbo].[cms_provider_dim_provider] (Prscrbr_First_Name, Prscrbr_Full_Name, Prscrbr_Last_Org_Name, Prscrbr_NPI, Prscrbr_Type, Prscrbr_Type_Src, Max_Year, Min_Year, provider_key)
    SELECT [Prscrbr_First_Name]
          ,(CASE WHEN [Prscrbr_Full_Name] IS NULL THEN 'missing' ELSE [Prscrbr_Full_Name] END) AS [Prscrbr_Full_Name]
          ,[Prscrbr_Last_Org_Name]
          ,[Prscrbr_NPI]
          ,(CASE WHEN [Prscrbr_Type] IS NULL THEN 'missing' ELSE [Prscrbr_Type] END) AS [Prscrbr_Type] 
          ,[Prscrbr_Type_Src]
          ,MAX([Year]) AS [Max_Year]
          ,MIN([Year]) AS [Min_Year]
          ,row_number() OVER (ORDER BY [Prscrbr_Full_Name],[Prscrbr_NPI],[Prscrbr_Type],[Prscrbr_Type_Src] ASC) AS [provider_key]
FROM [cms_lakehouse].[dbo].[cms_provider_drug_costs]
GROUP BY [Prscrbr_First_Name],[Prscrbr_Full_Name],[Prscrbr_Last_Org_Name],[Prscrbr_NPI],[Prscrbr_Type],[Prscrbr_Type_Src]

    -- Populate cms_provider_dim_year
    INSERT INTO [dbo].[cms_provider_dim_year] (Year, Year_Date_Key)
    SELECT DISTINCT [Year]
          ,CAST(CONCAT('1-1-',CAST([Year] AS varchar)) AS date) AS [Year_Date_Key]
    FROM [cms_lakehouse].[dbo].[cms_provider_drug_costs]

END
GO
