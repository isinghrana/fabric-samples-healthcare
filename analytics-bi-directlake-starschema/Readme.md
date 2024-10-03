# Fabric Power BI Direct Lake Connector with 220M+ Rows


## Scenario
The Fabric Direct Lake connector is a new technology for querying delta parquet files from Power BI without data caching or an intermediary relational database. Power BI datasets have been modernized so that the semantic layer containing metadata and query logic can directly query the Fabric Data Lake. Data for the demo is 220M+ rows of real healthcare data from the open data database titled **Medicare Part D Prescribers - by Provider and Drug**. Link here: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug . An end-to-end demo of this solution module can be viewed at this link: https://youtu.be/2tLIGVZ4c8E 

## Scope
This demo is intended to provide experience with data engineering tasks using Fabric Spark and/or Data Pipelines to build out Delta Parquet tables and then use the Direct Lake connector in Power BI to query large volumes of real data. The medallion lakehouse architecture is followed in this sample where raw CSV files are loaded to Bronze Layer, then Silver Layer flat table built using Delta Parquet format and lastly Gold Layer tables serve up the star schema model for a Direct Lake Power BI dataset. 

![analytics-bi-directlake](./Images/Logical_Diagram_Star_new.png)

### Pre-Requisite
Fabric enabled Workspace is the pre-requisite to be able to setup and end to end demonstration in your own environment. The instructions below are combination of Spark Notebook and a few manual steps to create Power BI Dataset and corresponding report.

***

### Step 1: Create Lakehouse and setup Spark Notebooks

In this step you will create Lakehouse and setup Spark Notebooks to be used for downloading csv files and creation of Lakehouse Tables (Delta Parquet) from those files 

1. Open your Fabric Workspace and switch to Data Engineering persona using the menu on bottom left corner (the screenshot below shows the buttons for Lakehouse creation and Notebook Import) 
   
    ![Fabric Data Engineering Persona](./Images/FabricDataEngineeringHome.jpg)

2. Create a new Lakehouse with name **cms_lakehouse** if not using an existing Lakehouse.

3. In the GitHub Repo open [01-DownloadCMSDataCsvFiles](./01-DownloadCMSDataCsvFiles.ipynb) Spark Notebook and download to local machine using the *Download Raw File* button on top right corner as shown in the screenshot below

    ![Downlaod Notebook](./Images/DownloadNotebook.jpg)

4. Repeat download step for [02-CreateCMSDataTable](./02-CreateCMSDataTable.ipynb) and [03-CreateCMSStarSchemaTables](./03-CreateCMSStarSchemaTables.ipynb) Spark Notebooks
   
5. Import the three downloaded Notebooks into Fabric Workspace (screenshot in Step 1 for *Import Notebook* button)

6. Once the import is successful Open **01-DownloadCMSDataCsvFiles** Notebook, you will need to select Lakehouse option and then **fix the Lakehouse association of the Notebook** by first clicking **Remove All Lakehouses** button then adding the Lakehouse created in Step 2 using **Add Lakehouse** button
    
    ![Open Notebook and select Lakehouse ooptino](./Images/FabricSparkNotebookLakehouseAssociation1.jpg)

    ![Fix Lakehouse Association](./Images/FabricSparkNotebookLakehouseAssociation2.jpg)

7. Repeat Step 6 for **02-CreateCMSDataTable** and **03-CreateCMSStarSchemaTables** Notebooks

***

### Step 2: Download Raw Files and build out Silver and Gold Layer Tables (Star Schema) to be used for Reporting
**Two methods are documented and available for this step and only one of the two needs to be implemented.** The choice on which method to use is more of a preference based on your skill set. Microsoft Fabric is a broad platform and allows end users to pick tools of their preference hence choice here demonstrates verstaility of the platform. In this step Bronze, Silver and Gold Layers of Medallion architecture are built using slightly different methods, the biggest difference is whether Gold Layer Star Schema Tables to be used for reporting are created in a Lakehouse or a Warehouse. 

**Note**: Fabric Data Factory Pipeline implementation steps are manual for now but we will look into making it easier using automation in future. **Both options 2a and 2b are manual but Step 2a is going to be a little less effort to setup because it uses Spark Notebooks which can be easily imported for use in your Fabric workspace. Step 2b will require little extra effort to setup Pipeline activities for T-SQL execution**


**2a. Gold Layer in Fabric Lakehouse** - A Fabric Data Factory Pipeline is implemented to use Spark Notebooks for building out all three layers - Bronze, Silver and Gold Layers in a Fabric Lakehouse.

[Setup Pipeline with Gold Layer in Fabric Lakehouse](./docs/2a-SetupPipeline-GoldLayerFabricLakehouse.md)

Skip to Step 3 if Step 2a was chosen and successfully executed to create star schema tables.

**2b. Gold Layer in Fabric Warehouse** - Fabric Data Factory Pipeline is implemented to use Spark Notebooks for building Bronze and Silver Layers in a Lakehouse but T-SQL scripts for building out the final Gold Layer persisted in Fabric Warehouse.

You will need the Lakehouse name from Step 1 and if you used the suggested name **cms_lakehouse** it will be easier otherwise few edits in T-SQL scripts will be required.

[Setup Pipeline with Gold Layer in Fabric Warehouse](./docs/2b-SetupPipeline-GoldLayerFabricWarehouse.md)

***

### Step 3: Create the Direct Lake Power BI Star Schema Dataset with DAX expressions and metadata
**Right now the easiest option for Git users is to manually create the Power BI Dataset. An automated option will be added when it becomes available in a way that is simple for end users.**
1. From the Fabric Lakehouse web interface, click "New Power BI dataset" per the instructions at this link: [Click Here](https://learn.microsoft.com/en-us/power-bi/enterprise/directlake-overview#to-create-a-basic-direct-lake-dataset-for-your-lakehouse)
2. Create relationships between the dimension tables and the fact table **cms_provider_drug_costs_star**:

 | Lakehouse Table Name | Dim Table Primary Key | Fact Table Foreign Key | Cardinality | Cross Filter Direction |
 | -------------------- | --------------------- | ---------------------- | ----------- | ---------------------- | 
 | cms_provider_dim_year | Year | Year | One to Many | Single | 
 | cms_provider_dim_drug | drug_key | drug_key | One to Many | Single | 
 | cms_provider_dim_geography | geo_key | geo_key | One to Many | Single | 
 | cms_provider_dim_provider | provider_key | provider_key | One to Many | Single | 

 Your Data Model should now look like this:
 ![analytics-bi-directlake-warehouse-starschema](./Images/Relationships.png)

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
 | cms_provider_dim_geography | City | Text | N/A | N/A | N/A | City | 
 | cms_provider_dim_geography | City State | Text | N/A | N/A | N/A | Place | 
 | cms_provider_dim_provider | Prescriber NPI | Whole Number | No | Yes | 0 | Uncategorized | 
 | cms_provider_dim_geography | State | Text | N/A | N/A | N/A | State or Province | 
 | cms_provider_dim_year | Year | Whole Number | No | Yes | 0 | Uncategorized | 

6. The Power BI dataset now exists within Fabric, no caching or refreshing needed! You can go back to your Workspace and re-name the dataset, which shows up as a new artifact in the Fabric Workspace. Now you can adjust some settings for the dataset to potentially enable better performance:
  - From the Workspace, click on the ellipse next to the dataset name.
  - Choose **Settings**
  - Seelct **Query caching** > **On** to cache reporting results and improve perofmance for end users
  - Turn on **Q&A** for natural language queries in the Power BI report
  - Turn on **Large dataset storage format** which may help with the large data volumes in the fact table
  
8. A video walking you through these steps can be found at [this link](https://youtu.be/8K4vvy_o9j0).

***

### Step 4: Create Reports using Power BI or Connect using Excel
**Right now the easiest option for Git users is to create your own reports. An automated option with a PBIX or PBIT file will be added when it becomes available in a way that is simple for end users.**

1. You can create a new Power BI report in Fabric by either clicking "New report" in the Data model view, clicking "Create report" from the ellipse in the Workspace view of the dataset, or by connecting to the Fabric Lakehouse using Power BI Desktop.
2. You can also use "Analyze in Excel" from the ellipse next to the dataset in the Fabric Workspace.
3. You can use the existing report template by downloading a copy of the Power BI Report template from the file in this repo at [analytics-bi-directlake-warehouse-starschema](./CMS%20Medicare%20Part%20D%20Star%20Schema%20Template.pbix)
  - Open the file using Power BI Desktop
  - Connect to your Fabric Lakehouse
  - Publish the Power BI report to your Fabric Workspace
The Power BI Report that connects to the Direct Lake Semantic Model shoul look like this, and be ready for use with Power BI Copilot:
![analytics-bi-directlake](./Images/ReportExample.png) 
