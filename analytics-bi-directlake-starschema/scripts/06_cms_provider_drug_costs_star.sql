-- This query is used to create a View in the Warehouse for a fact table. The View will be used to populate a table in the Lakehouse for use with a Direct Lake connection.

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE VIEW [dbo].[cms_provider_drug_costs_star] AS (SELECT      [GE65_Bene_Sprsn_Flag]
            ,[GE65_Sprsn_Flag]
            ,[GE65_Tot_30day_Fills]
            ,[GE65_Tot_Benes]
            ,[GE65_Tot_Clms]
            ,[GE65_Tot_Day_Suply]
            ,[GE65_Tot_Drug_Cst]
            ,[Tot_30day_Fills]
            ,[Tot_Benes]
            ,[Tot_Clms]
            ,[Tot_Day_Suply]
            ,[Tot_Drug_Cst]
            ,[Year]
            ,b.[drug_key]
            ,c.[geo_key]
            ,d.[provider_key]
FROM [CMS_Warehouse].[dbo].[cms_provider_fact_no_null_key] a
LEFT JOIN [CMS_Warehouse].[dbo].[cms_provider_dim_drug] b ON a.[Brnd_Name] = b.[Brnd_Name] AND a.[Gnrc_Name] = b.[Gnrc_Name]
LEFT JOIN [CMS_Warehouse].[dbo].[cms_provider_dim_geography] c ON a.[Prscrbr_City_State] = c.[Prscrbr_City_State] 
LEFT JOIN [CMS_Warehouse].[dbo].[cms_provider_dim_provider] d ON a.[Prscrbr_Full_Name] = d.[Prscrbr_Full_Name] AND a.[Prscrbr_NPI] = d.[Prscrbr_NPI] AND a.[Prscrbr_Type] = d.[Prscrbr_Type] AND a.[Prscrbr_Type_Src] = d.[Prscrbr_Type_Src])

GO
