# 220M+ row Star Schema Fabric Power BI Direct Lake Dataset designed with Fabric Data Warehouse and a Pipeline


## Scenario
Another solution in this Git repo in the folder **analytics_bi_directlake_warehouse** enabled the ingestion of 220+ million rows of data from CMS into a Fabric Lakehouse using Spark Notebooks. The data was transformed into a normalized table in the Lakehouse, and a Power BI dataset in Direct Lake mode was built on top of it. The solution can be found at this link: https://github.com/isinghrana/fabric-samples-healthcare/tree/main/analytics-bi-directlake 

This new solution takes you a step further by transforming that normalized table of data into a star schema design that is optimized for complicated analytic queries and fast query performance. The normalized table of CMS data is redesigned as dimensions and a fact table using the Fabric Warehouse, and then a Fabric Pipeline (Azure Data Factory in Fabric) is used to orchestrate writing the dimensions and fact table to a Fabric Lakehouse. Instructions are then provided for creating a new Power BI dataset in Direct Lake mode that uses the star schema design in the Fabric Lakehouse.

The Fabric Direct Lake connector is a new technology for querying delta parquet files from Power BI without data caching or an intermediary relational database. Power BI datasets have been modernized so that the semantic layer containing metadata and query logic can directly query the Fabric Data Lake. Data for the demo is 220M+ rows of real healthcare data from the open data database titled **Medicare Part D Prescribers - by Provider and Drug**. Link here: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug 

## Scope
This demo is intended to provide experience with creating a star schema design for a Power BI Direct Lake dataset. You will lear how to design dimension and fact tables in the Fabric Data Warehouse, and then write the new tables to a Fabric Data Lakehouse gold layer for use with the Direct Lake Power BI dataset.  

![analytics-bi-directlake-warehouse-starschema](./Logical_Diagram_Star.png) 

### Pre-Requisite
Fabric enabled Workspace is the pre-requisite to be able to setup and end to end demonstration in your own environment. The instructions below are combination of SQL statements, a Fabric Pipeline, and a Power BI Direct Lake dataset.

### Complete the ingestion and initial prep of the data
Complete the solution in this Git repo which ingests and preps the CMS data. The steps can be found at this link: https://github.com/isinghrana/fabric-samples-healthcare/tree/main/analytics-bi-directlake 

### Create Warehouse and add SQL scripts
1. Open up your Fabric Workspace and switch to Data Engineering persona using the menu on bottom left corner
2. Create a new Warehouse or use an existing one
3. Download [Load CMS Medicare PartD Data](./Load%20CMS%20Medicare%20Part%20D%20Data.ipynb) Spark Notebook from Github Repo to your local machine
4. Import the downloaded Notebook into Fabric Workspace
5. Open the Notebook once the import is successful, you might need to update the Lakehouse association of the Notebook
6. Spark Notebook has the subsequent instructions to download data files from [CMS Website](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug), then upload data files to Lakeshouse and then run Spark Notebook to create Delta Parquet tables to be used by Power BI in the next step.