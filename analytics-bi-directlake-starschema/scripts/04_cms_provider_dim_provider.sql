-- This query is used to create a View in the Warehouse for a Provider dimension

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE VIEW [dbo].[cms_provider_dim_provider] AS 
(
SELECT [Prscrbr_First_Name]
,(CASE WHEN [Prscrbr_Full_Name] IS NULL THEN 'missing' ELSE [Prscrbr_Full_Name] END) AS [Prscrbr_Full_Name]
,[Prscrbr_Last_Org_Name]
,[Prscrbr_NPI]
,(CASE WHEN [Prscrbr_Type] IS NULL THEN 'missing' ELSE [Prscrbr_Type] END) AS [Prscrbr_Type] 
,[Prscrbr_Type_Src]
,MAX([Year]) AS [Max_Year]
,MIN([Year]) AS [Min_Year]
,row_number() OVER (ORDER BY [Prscrbr_Full_Name],[Prscrbr_NPI],[Prscrbr_Type],[Prscrbr_Type_Src] ASC) AS [provider_key]
FROM [CMS_Lakehouse].[dbo].[cms_provider_drug_costs]
GROUP BY [Prscrbr_First_Name],[Prscrbr_Full_Name],[Prscrbr_Last_Org_Name],[Prscrbr_NPI],[Prscrbr_Type],[Prscrbr_Type_Src]
)

GO
