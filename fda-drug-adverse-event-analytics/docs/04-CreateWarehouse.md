## Create Fabric Warehouse to serve as a Gold layer data mart

Now you will create a Fabric Warehouse that will serve as a Gold layer for reporting. The premise for this Gold layer is that an analysts with SQL and Power BI skills was asked to report on the frequency of reports containing the reactions 'Fatigue' or 'Insomnia.' This use case is very simple, and only serves to provide you with a framework for developing your on unique use cases and data marts.

1. From your Fabric Workspace select **New** > **More options** > Warehouse as seen in the screenshot below:

![Run Pipeline Job](../images/Warehouse1.png)

2. Name the Warehouse as you choose, and select **+Warehouses** as seen below:

![Monitor Pipeline Job](../images/Warehouse2.png)

3. Select your Lakehouse and press **Confirm**.
4. From the top ribbon of the Warehouse, select **New SQL query** > **New SQL query**.
5. Paste in the SQL query linked here: [03-SQL-CreateWarehouseTable.sql](./scripts/03-SQL-CreateWarehouseTable.sql). Notice that the script accounts for discrepencies in capitalization. Make sure you replace the names of your Lakehouse where the query specifies **YOURLAKEHOUSENAME**
6. Select **Run**, and the query shouldn't take long to complete. Highlight the SQL Query and select **Save as table** as seen below:

![Monitor Pipeline Job](../images/Warehouse3.png)

7. Give the new Warehouse table a name, I used **fda_drug_event_fatiue_insomnia** as seen below:

![Monitor Pipeline Job](../images/Warehouse4.png)



***

Once the Job completes successfully you can browse to the Lakehouse to see the three tables as well as two folders in the files section of Lakehouse for zipped and unzipped raw files as shown in the screenshot below.

![Lakehouse with Tables and Raw files](../images/Lakehouse-PipelineJobComplete.jpg)

**Dataset Size Information**

* Raw Unzipped JSON File size on disk: 400+ GB, 1400+ Files
* Total Flattened Table size on disk (delta parquet are significantly compressed by their nature): 15-20 GB
* Three Delta Tables 
    * fda_drug_event Table - 17 Million+ Rows; Size 750 MB
    * fda_drug_event_patient_reaction Table - 50 Million+ Rows; Size 17 GB+ (1 to many from Drug Event table) 
    * Fda_drug_event_patient_drug Table - 62 Million+ Rows; Size 250 MB (1 to many from Drug Event table)

***

[Home](../Readme.md) | [Prevous](./03-RunPipeline.md) | Next




