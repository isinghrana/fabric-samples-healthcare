# Fabric Power BI Direct Lake Connector with 220M+ Rows


## Scenario
The Fabric Direct Lake connector is a new technology for querying delta parquet files from Power BI without data caching or an intermediary relational database. Power BI datasets have been modernized so that the semantic layer containing metadata and query logic can directly query the Fabric Data Lake. Data for the demo is 220M+ rows of real healthcare data from the open data database titled **Medicare Part D Prescribers - by Provider and Drug**. Link here: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug 

## Scope
This demo is intended to provide experience with light data engineering tasks (data type conversions, appending columns, etc.) using Fabric Spark to build out Delta Parquet tables and then using the Direct Lake connector in Power BI to query large volumes of real data. The demo is not intended to represent the best possible arhitecture for the data model, or the best method to architect the delta parquet portion of the design. The demo will be updated in future interations to include a dimensional model, but the first version will be a simple flattened delta parquet table that can be queried directly from Power BI. 

![analytics-bi-directlake](./Images/DirectLake_Architecture.png) 

### Pre-Requisite
Fabric enabled Workspace is the pre-requisite to be able to setup and end to end demonstration in your own environment. The instricutions below are combination of Spark Notebook and some manual steps to create Power BI Dataset.

### Create Lakehouse, upload data to Lakehouse and create Delta Parquet Table using Fabric Spark
1. Open up your Fabric Workspace and switch to Data Engineering persona using the menu on bottom left corner
2. Create a new Lakehouse or use an existing one
3. Download [Load CMS Medicare PartD Data](./Load%20CMS%20Medicare%20Part%20D%20Data.ipynb) Spark Notebook from Github Repo to your local machine
4. Import the downloaded Notebook into Fabric Workspace
5. Open the Notebook once the import is successful, you might need to update the Lakehouse association of the Notebook
6. Spark Notebook has the subsequent instructions to download data files from [CMS Website](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug), then upload data files to Lakeshouse and then run Spark Notebook to create Delta Parquet tables to be used by Power BI in the next step.

A video walking you through all of these steps can be found [by clicking here](https://youtu.be/yblKEdmf1KE). 

If you want to manually upload the files to the Fabric Lakehouse before running the Notebook, a video of that process can be found at [this link](https://youtu.be/Ln4mpuknuco).


### Create the Direct Lake Power BI Dataset with DAX expressions and metadata
**Right now the easiest option for Git users is to manually create the Power BI Dataset. An automated option will be added when it becomes available in a way that is simple for end users.**
1. From the Fabric Lakehouse web interface, click "New Power BI dataset" per the instructions at this link: [Click Here](https://learn.microsoft.com/en-us/power-bi/enterprise/directlake-overview#to-create-a-basic-direct-lake-dataset-for-your-lakehouse)
2. Assign user-friendly names to the columns for user-facing values, and hide columns that will be displayed using Calculated Measures (Step 3):

 | Lakehouse Column Name | New Dataset Column Name | Is hidden | 
 | --------------------- | ----------------------- | --------- | 
 | Brnd_Name | Brand Name | No | 
 | GE65_Bene_Sprsn_Flag | 65 or Older Beneficiaries Suppression Flag | No | 
 | GE65_Sprsn_Flag | 65 or Older Suppression Flag | No | 
 | GE65_Tot_30day_Fills | 65 or Older Total 30 Day Fills | No | 
 | GE65_Tot_Benes | 65 or Older Total Beneficiaries | No | 
 | GE65_Tot_Clms | 65 or Older Total Claims | No | 
 | GE65_Tot_Day_Suply | 65 or Older Total Days Supply | No | 
 | GE65_Tot_Drug_Cst | 65 or Older Total Drug Cost | No | 
 | Gnrc_Name | Generic Name | No | 
 | Prscrbr_City | Prescriber City | No | 
 | Prscrbr_City_State | Prescriber City State | No | 
 | Prscrbr_First_Name | Prescriber First Name | No | 
 | Prscrbr_Full_Name | Prescriber Full Name | No | 
 | Prscrbr_Last_Org_Name | Prescriber Last Name | No | 
 | Prscrbr_NPI | Prescriber NPI | No | 
 | Prscrbr_State_Abrvtn | Prescriber State | No | 
 | Prscrbr_State_FIPS | Prescriber State FIPS | No | 
 | Prscrbr_Type | Prescriber Type | No | 
 | Prscrbr_Type_Src | Prescriber Type Source | No | 
 | Tot_30day_Fills | Tot_30day_Fills | Yes | 
 | Tot_Benes | Tot_Benes | Yes | 
 | Tot_Clms | Tot_Clms |  Yes | 
 | Tot_Day_Suply | Tot_Day_Suply | Yes | 
 | Tot_Drug_Cst | Tot_Drug_Cst | Yes |  
 | Year | Year | No | 
 
3. Add the following DAX espressions by clicking "New measure" in the edit Data Model view:

 | Measure name | DAX Syntax | Format | Percentage Format | Thousands seperator | Decimal places | Data category | 
 | ------------ | ---------- | ------ | ----------------- | ------------------- | -------------- | ------------- |
 | Brand Name Count | `Brand Name Count = DISTINCTCOUNT([Brand Name])` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Prescriber Count | `Prescriber Count = DISTINCTCOUNT([Prescriber NPI]`) | Whole Number | No | Yes | 0 | Uncategorized | 
 | Row Count | `Row Count = COUNTROWS('cms_provider_drug_costs')` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Claims | `Total Claims = SUM(cms_provider_drug_costs[Tot_Clms])` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Beneficiaries | `Total Beneficiaries = SUM(cms_provider_drug_costs[Tot_Benes])` | Whole Number | No | Yes | 0 | Uncategorized |  
 | Total 30 Day Fills | `Total 30 Day Fills = SUM(cms_provider_drug_costs[Tot_30day_Fills])` | Decimal | No | Yes | 1 | Uncategorized | 
 | Total Day Supply | `Total Days Supply = SUM([Tot_Day_Suply])` | Whole Number | No | Yes | 0 | Uncategorized | 
 | Total Drug Cost | `Total Drug Cost = SUM([Tot_Drug_Cst])` | Currency | No | Yes | 0 | Uncategorized | 
 | Cost per Claim | `Cost per Claim = DIVIDE([Total Drug Cost],[Total Claims])` | Currency | No | Yes | 0 | Uncategorized | 
 | Cost per Day | `Cost per Day = DIVIDE([Total Drug Cost],[Total Days Supply])` | Currency | No | Yes | 2 | Uncategorized | 
 | Days per Claim | `Days per Claim = DIVIDE([Total Days Supply],[Total Claims])` | Decimal | No | Yes | 1 | Uncategorized | 
  
4. Modify the following metadata changes to columns (that already exist in the dataset):

| Column name | Format | Percentage Format | Thousands seperator | Decimal places | Data category | 
 | ---------- | ------ | ----------------- | ------------------- | -------------- | ------------- |
 | City | Text | N/A | N/A | N/A | City | 
 | City State | Text | N/A | N/A | N/A | Place | 
 | Prescriber NPI | Whole Number | No | Yes | 0 | Uncategorized | 
 | State | Text | N/A | N/A | N/A | State or Province | 
 | Year | Whole Number | No | Yes | 0 | Uncategorized | 

5. The Power BI dataset now exists within Fabric, no caching or refreshing needed! You can go back to your Workspace and re-name the dataset, which shows up as a new artifact in the Fabric Workspace. Or, you can click "New report" and move to the next step.
6. A video walking you through these steps can be found at [this link](https://youtu.be/8K4vvy_o9j0).

### Create Reports using Power BI or Connect using Excel
**Right now the easiest option for Git users is to create your own reports. An automated option with a PBIX or PBIT file will be added when it becomes available in a way that is simple for end users.**

1. You can create a new Power BI report in Fabric by either clicking "New report" in the Data model view, clicking "Create report" from the ellipse in the Workspace view of the dataset, or by connecting to the Fabric Lakehouse using Power BI Desktop.
2. You can also use "Analyze in Excel" from the ellipse next to the dataset in the Fabric Workspace.
3. A video walking you through these steps can be found here: Click Here

![analytics-bi-directlake](./Images/DirectLake_PBI_Landing.png) 

![analytics-bi-directlake](./Images/DirectLake_PBI_QA.png) 
