CREATE PROCEDURE [dbo].[usp_CreateAndPopulateFactTable]
AS
BEGIN
    -- Step 1: Create Table
    -- Create cms_provider_drug_costs_star table
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='cms_provider_drug_costs_star' AND xtype='U')
    BEGIN
        CREATE TABLE [dbo].[cms_provider_drug_costs_star]
        (
           [GE65_Bene_Sprsn_Flag] [varchar](8000)  NULL,
	       [GE65_Sprsn_Flag] [varchar](8000)  NULL,
	       [GE65_Tot_30day_Fills] [decimal](10,2)  NULL,
	       [GE65_Tot_Benes] [bigint]  NULL,
	       [GE65_Tot_Clms] [bigint]  NULL,
	       [GE65_Tot_Day_Suply] [bigint]  NULL,
	       [GE65_Tot_Drug_Cst] [decimal](10,2)  NULL,
	       [Tot_30day_Fills] [decimal](10,2)  NULL,
	       [Tot_Benes] [bigint]  NULL,
	       [Tot_Clms] [bigint]  NULL,
	       [Tot_Day_Suply] [bigint]  NULL,
	       [Tot_Drug_Cst] [decimal](10,2)  NULL,
	       [Year] [int]  NULL,
	       [drug_key] [bigint]  NULL,
	       [geo_key] [bigint]  NULL,
	       [provider_key] [bigint]  NULL
        )
    END

    -- Step 2: Populate Table
    -- Populate cms_provider_drug_costs_star
    INSERT INTO [dbo].[cms_provider_drug_costs_star] 
    (
        [GE65_Bene_Sprsn_Flag], [GE65_Sprsn_Flag], [GE65_Tot_30day_Fills], [GE65_Tot_Benes], [GE65_Tot_Clms], [GE65_Tot_Day_Suply], [GE65_Tot_Drug_Cst], [Tot_30day_Fills], [Tot_Benes], [Tot_Clms], [Tot_Day_Suply], [Tot_Drug_Cst], [Year], [drug_key], [geo_key], [provider_key]
    )
    SELECT a.[GE65_Bene_Sprsn_Flag]
          ,a.[GE65_Sprsn_Flag]
          ,a.[GE65_Tot_30day_Fills]
          ,a.[GE65_Tot_Benes]
          ,a.[GE65_Tot_Clms]
          ,a.[GE65_Tot_Day_Suply]
          ,a.[GE65_Tot_Drug_Cst]
          ,a.[Tot_30day_Fills]
          ,a.[Tot_Benes]
          ,a.[Tot_Clms]
          ,a.[Tot_Day_Suply]
          ,a.[Tot_Drug_Cst]
          ,a.[Year]
          ,b.[drug_key]
          ,c.[geo_key]
          ,d.[provider_key]
    FROM [cms_lakehouse].[dbo].[cms_provider_drug_costs] a
    LEFT JOIN [cms_warehouse].[dbo].[cms_provider_dim_drug] b 
        ON a.[Brnd_Name] = b.[Brnd_Name] AND a.[Gnrc_Name] = b.[Gnrc_Name]
    LEFT JOIN [cms_warehouse].[dbo].[cms_provider_dim_geography] c 
        ON ISNULL(a.[Prscrbr_City_State],'XX') = c.[Prscrbr_City_State] 
    LEFT JOIN [cms_warehouse].[dbo].[cms_provider_dim_provider] d 
        ON ISNULL(a.[Prscrbr_Full_Name],'missing') = d.[Prscrbr_Full_Name] 
        AND a.[Prscrbr_NPI] = d.[Prscrbr_NPI] 
        AND ISNULL(a.[Prscrbr_Type],'missing') = d.[Prscrbr_Type] 
        AND a.[Prscrbr_Type_Src] = d.[Prscrbr_Type_Src]

END
GO
