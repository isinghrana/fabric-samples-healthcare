## Create the Direct Lake Power BI Star Schema Semantic Model with DAX expressions and metadata


1. From the Fabric Lakehouse web interface, click "New Power BI Semantic Model" per the instructions at this link: [Click Here](https://learn.microsoft.com/en-us/power-bi/enterprise/directlake-overview#to-create-a-basic-direct-lake-dataset-for-your-lakehouse)
2. Create relationships between the dimension tables and the fact table **cms_provider_drug_costs_star**:

 | Lakehouse Table Name | Dim Table Primary Key | Fact Table Foreign Key | Cardinality | Cross Filter Direction |
 | -------------------- | --------------------- | ---------------------- | ----------- | ---------------------- | 
 | cms_provider_dim_year | Year | Year | One to Many | Single | 
 | cms_provider_dim_drug | drug_key | drug_key | One to Many | Single | 
 | cms_provider_dim_geography | geo_key | geo_key | One to Many | Single | 
 | cms_provider_dim_provider | provider_key | provider_key | One to Many | Single | 

 Your Data Model should now look like this:
 ![analytics-bi-directlake-warehouse-starschema](../Images/Relationships.png)

3. Assign user-friendly names to the columns for user-facing values, and hide columns that will be built into Calculated Measures (Step 3). All columns on the fact table are hidden since the filter values are now in dimensions:

 | Lakehouse Table Name | Lakehouse Table Column Name | New Dataset Column Name | Is hidden | 
 | -------------------- | --------------------------- | ----------------------- | --------- | 
 | cms_provider_dim_year | Year | Year | No | 
 | cms_provider_dim_year | Year_Date_Key | Year_Date_Key | Yes | 
 | cms_provider_dim_drug | Brnd_Name | Brand Name | No | 
 | cms_provider_dim_drug | Gnrc_Name | Generic Name | No | 
 | cms_provider_dim_drug | Max_Year | Max_Year_drug | Yes | 
 | cms_provider_dim_drug | Min_Year | Min_Year_drug | Yes | 
 | cms_provider_dim_drug | drug_key | drug_key | Yes | 
 | cms_provider_dim_geography | Prscrbr_City | Prescriber City | No |
 | cms_provider_dim_geography | Prscrbr_City_State | Prescriber City State | No | 
 | cms_provider_dim_geography | Prscrbr_State_Abrvtn | Prescriber State | No | 
 | cms_provider_dim_geography | Prscrbr_State_FIPS | Prescriber State FIPS | Yes | 
 | cms_provider_dim_geography | Max_Year | Max_Year_geo | Yes | 
 | cms_provider_dim_geography | Min_Year | Min_Year_geo | Yes | 
 | cms_provider_dim_geography | geo_key | geo_key | Yes | 
 | cms_provider_dim_provider | Prscrbr_First_Name | Prescriber First Name | Yes | 
 | cms_provider_dim_provider | Prscrbr_Full_Name | Prescriber Full Name | No | 
 | cms_provider_dim_provider | Prscrbr_Last_Org_Name | Prescriber Last Name | Yes |
 | cms_provider_dim_provider | Prscrbr_NPI | Prescriber NPI | No |
 | cms_provider_dim_provider | Prscrbr_Type | Prescriber Type | No |
 | cms_provider_dim_provider | Prscrbr_Type_Src | Prescriber Type Source | Yes |
 | cms_provider_dim_provider | Max_Year | Max_Year_provider | Yes | 
 | cms_provider_dim_provider | Min_Year | Min_Year_provider | Yes | 
 | cms_provider_dim_provider | provider_key | provider_key | Yes | 
 | dbo.cms_provider_drug_costs_star | GE65_Bene_Sprsn_Flag | 65 or Older Beneficiaries Suppression Flag | Yes | 
 | dbo.cms_provider_drug_costs_star | GE65_Sprsn_Flag | 65 or Older Suppression Flag | Yes | 
 | dbo.cms_provider_drug_costs_star | GE65_Tot_30day_Fills | 65 or Older Total 30 Day Fills | Yes |
 | dbo.cms_provider_drug_costs_star | GE65_Tot_Benes | 65 or Older Total Beneficiaries | Yes |
 | dbo.cms_provider_drug_costs_star | GE65_Tot_Clms | 65 or Older Total Claims | Yes | 
 | dbo.cms_provider_drug_costs_star | GE65_Tot_Day_Suply | 65 or Older Total Days Supply | Yes | 
 | dbo.cms_provider_drug_costs_star | GE65_Tot_Drug_Cst | 65 or Older Total Drug Cost | Yes | 
 | dbo.cms_provider_drug_costs_star | Tot_30day_Fills | Tot_30day_Fills | Yes |
 | dbo.cms_provider_drug_costs_star | Tot_Benes | Tot_Benes | Yes | 
 | dbo.cms_provider_drug_costs_star | Tot_Clms | Tot_Clms |  Yes | 
 | dbo.cms_provider_drug_costs_star | Tot_Day_Suply | Tot_Day_Suply | Yes | 
 | dbo.cms_provider_drug_costs_star | Tot_Drug_Cst | Tot_Drug_Cst | Yes | 
 | dbo.cms_provider_drug_costs_star | Year | Year | Yes |
 | dbo.cms_provider_drug_costs_star | drug_key | drug_key | Yes | 
 | dbo.cms_provider_drug_costs_star | geo_key | geo_key | Yes | 
 | dbo.cms_provider_drug_costs_star | provider_key | provider_key | Yes | 
 
4. Add the following DAX espressions by clicking "New measure" in the edit Data Model view:

 | Measure name | DAX Syntax | Format | Percentage Format | Thousands seperator | Decimal places | Data category | 
 | ------------ | ---------- | ------ | ----------------- | ------------------- | -------------- | ------------- |
 | Row Count | `Row Count = COUNTROWS('cms_provider_drug_costs_star')` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Claims | `Total Claims = SUM(cms_provider_drug_costs_star[Tot_Clms])` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Beneficiaries | `Total Beneficiaries = SUM(cms_provider_drug_costs_star[Tot_Benes])` | Whole Number | No | Yes | 0 | Uncategorized |  
 | Total 30 Day Fills | `Total 30 Day Fills = SUM(cms_provider_drug_costs_star[Tot_30day_Fills])` | Decimal | No | Yes | 1 | Uncategorized | 
 | Total Day Supply | `Total Days Supply = SUM(cms_provider_drug_costs_star[Tot_Day_Suply])` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Drug Cost | `Total Drug Cost = SUM(cms_provider_drug_costs_star[Tot_Drug_Cst])` | Currency | No | Yes | 0 | Uncategorized | 
 | Cost per Claim | `Cost per Claim = DIVIDE([Total Drug Cost],[Total Claims])` | Currency | No | Yes | 0 | Uncategorized | 
 | Cost per Day | `Cost per Day = DIVIDE([Total Drug Cost],[Total Days Supply])` | Currency | No | Yes | 2 | Uncategorized | 
 | Days per Claim | `Days per Claim = DIVIDE([Total Days Supply],[Total Claims])` | Decimal | No | Yes | 1 | Uncategorized | 
  
5. Modify the following metadata changes to columns (that already exist in the dataset):

 | Table Name | Column name | Format | Percentage Format | Thousands seperator | Decimal places | Data category | 
 | ---------- | ----------- | ------ | ----------------- | ------------------- | -------------- | ------------- |
 | cms_provider_dim_geography | Prescriber City | Text | N/A | N/A | N/A | City | 
 | cms_provider_dim_geography | Prescriber City State | Text | N/A | N/A | N/A | Place | 
 | cms_provider_dim_provider | Prescriber NPI | Whole Number | No | No | 0 | Uncategorized | 
 | cms_provider_dim_geography | Prescriber State | Text | N/A | N/A | N/A | State or Province | 
 | cms_provider_dim_year | Year | Whole Number | No | No | 0 | Uncategorized | 

6. The Power BI dataset now exists within Fabric, no caching or refreshing needed! You can go back to your Workspace and re-name the dataset, which shows up as a new artifact in the Fabric Workspace. Now you can adjust some settings for the dataset to potentially enable better performance:
  - From the Workspace, click on the ellipse next to the dataset name.
  - Choose **Settings**
  - Seelct **Query caching** > **On** to cache reporting results and improve perofmance for end users
  - Turn on **Q&A** for natural language queries in the Power BI report
  - Turn on **Large dataset storage format** which may help with the large data volumes in the fact table
  
8. A video walking you through these steps can be found at [this link](https://youtu.be/8K4vvy_o9j0).


[Back to main Readme](../manual-setup.md#step-2-download-raw-files-and-build-out-silver-and-gold-layer-tables-star-schema-to-be-used-for-reporting) | [Next](./4-CreatePBIReport.md)
