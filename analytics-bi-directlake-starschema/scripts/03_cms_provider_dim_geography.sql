-- This query is used to create a View in the Warehouse for a Geography dimension

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE VIEW [dbo].[cms_provider_dim_geography] AS (SELECT       [Prscrbr_City]
            ,(CASE WHEN [Prscrbr_City_State] IS NULL THEN 'XX' ELSE [Prscrbr_City_State] END) AS [Prscrbr_City_State]
            ,[Prscrbr_State_Abrvtn]
            ,[Prscrbr_State_FIPS]
            ,MAX([Year]) AS [Max_Year]
            ,MIN([Year]) AS [Min_Year]
            ,row_number() OVER (ORDER BY [Prscrbr_State_Abrvtn],[Prscrbr_City_State] ASC) AS [geo_key]
FROM [CMS_Lakehouse].[dbo].[cms_provider_drug_costs]
GROUP BY [Prscrbr_City],[Prscrbr_City_State],[Prscrbr_State_Abrvtn],[Prscrbr_State_FIPS])

GO
