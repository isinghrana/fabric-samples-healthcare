SELECT DISTINCT [Year]
,CAST(CONCAT('1-1-',CAST([Year] AS varchar)) AS date) AS [Year_Date_Key] 
FROM [CMS_Lakehouse].[dbo].[cms_provider_drug_costs]
