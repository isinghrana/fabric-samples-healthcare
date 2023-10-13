-- This query is used to create a View in the Warehouse that replaces blank values for columns that will be used for joins to build a fact table

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE VIEW [dbo].[cms_provider_fact_no_null_key] AS (SELECT [Brnd_Name]
            ,[GE65_Bene_Sprsn_Flag]
            ,[GE65_Sprsn_Flag]
            ,[GE65_Tot_30day_Fills]
            ,[GE65_Tot_Benes]
            ,[GE65_Tot_Clms]
            ,[GE65_Tot_Day_Suply]
            ,[GE65_Tot_Drug_Cst]
            ,[Gnrc_Name]
            ,[Prscrbr_City]
            ,(CASE WHEN [Prscrbr_City_State] IS NULL THEN 'XX' ELSE [Prscrbr_City_State] END) AS [Prscrbr_City_State]
            ,[Prscrbr_First_Name]
            ,(CASE WHEN [Prscrbr_Full_Name] IS NULL THEN 'missing' ELSE [Prscrbr_Full_Name] END) AS [Prscrbr_Full_Name]
            ,[Prscrbr_Last_Org_Name]
            ,[Prscrbr_NPI]
            ,[Prscrbr_State_Abrvtn]
            ,[Prscrbr_State_FIPS]
            ,(CASE WHEN [Prscrbr_Type] IS NULL THEN 'missing' ELSE [Prscrbr_Type] END) AS [Prscrbr_Type]
            ,[Prscrbr_Type_Src]
            ,[Tot_30day_Fills]
            ,[Tot_Benes]
            ,[Tot_Clms]
            ,[Tot_Day_Suply]
            ,[Tot_Drug_Cst]
            ,[Year]
FROM [CMS_Lakehouse].[dbo].[cms_provider_drug_costs])

GO
