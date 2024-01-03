-- This query is used to create a View in the Warehouse for a Drug dimension

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE VIEW [dbo].[cms_provider_dim_drug] AS 
(
SELECT [Brnd_Name]
,[Gnrc_Name]
,MAX([Year]) AS [Max_Year]
,MIN([Year]) AS [Min_Year]
,row_number() OVER (ORDER BY [Brnd_Name],[Gnrc_Name] ASC) AS [drug_key]
FROM [CMS_Lakehouse].[dbo].[cms_provider_drug_costs]
GROUP BY [Brnd_Name],[Gnrc_Name]
)

GO
