# Manual Setup - Fabric Power BI Direct Lake Connector with 275 Million Rows

**Pre-Requisite**: Fabric-enabled Workspace

## Steps to setup demo in your own environment

### Step 1: [Create Lakehouse and setup Spark Notebooks](./docs/1-CreateLakehouse-SetupSparkNotebooks.md) 
Click the link above for instructions on setting up your Lakehouse and importing the Spark Notebooks.

***

### Step 2: Download Raw Files and build out Silver and Gold Layer Tables (Star Schema) to be used for Reporting
**Two methods are documented and available for this step and only one of the two needs to be implemented.** The choice on which method to use is more of a preference based on your skill set. Microsoft Fabric is a broad platform and allows end users to pick tools of their preference hence choice here demonstrates verstaility of the platform. In this step Bronze, Silver and Gold Layers of Medallion architecture are built using slightly different methods, the biggest difference is whether Gold Layer Star Schema Tables to be used for reporting are created in a Lakehouse or a Warehouse. 

**Note**: Fabric Data Factory Pipeline implementation steps are manual for now but we will look into making it easier using automation in future. **Both options 2a and 2b are manual but Step 2a is going to be a little less effort to setup because it uses Spark Notebooks which can be easily imported for use in your Fabric workspace. Step 2b will require little extra effort to setup Pipeline activities for SQL Stored Procedures, but in return the Gold Layer will be in the Fabric Warehouse instead of the Lakehouse (folks from a SQL background may prefer this option).**

**2a. Gold Layer in Fabric Lakehouse** - A Fabric Data Factory Pipeline is implemented to use Spark Notebooks for building out all three layers - Bronze, Silver and Gold Layers in a Fabric Lakehouse. Click the link below for instructions in this GitHub Repo, and you can also watch a video reviewing the 2a process at this link: https://youtu.be/TG03mkJKq4k

**[Setup Pipeline with Gold Layer in Fabric Lakehouse](./docs/2a-SetupPipeline-GoldLayerFabricLakehouse.md)**

Skip to Step 3 if Step 2a was chosen and successfully executed to create star schema tables.

**2b. Gold Layer in Fabric Warehouse** - Fabric Data Factory Pipeline is implemented to use Spark Notebooks for building Bronze and Silver Layers in a Lakehouse but SQL Stored Procedures for building out the final Gold Layer persisted in Fabric Warehouse. A video detailing the creation and deployment of these Stored Procedures can be found at this link: https://youtu.be/G6t4d5FU0zI 

You will need the Lakehouse name from Step 1 and if you used the suggested name **cms_lakehouse** it will be easier otherwise a few edits in T-SQL scripts will be required.

**[Setup Pipeline with Gold Layer in Fabric Warehouse](./docs/2b-SetupPipeline-GoldLayerFabricWarehouse.md)**

***

### Step 3: [Create the Direct Lake Power BI Star Schema Semantic Model with DAX expressions and metadata](./docs/3-CreatePBISemanticModel.md) 
Steps are manual at this time but in the future we plan to automate for quick setup.

***

### Step 4: [Create Reports using Power BI or Connect using Excel](./docs/4-CreatePBIReport.md) 
Steps are manual at this time but in future plan to automate for quick setup. We do have a .pbix file in this repo that can connect to the Semantic Model if the metadata matches the naming conventions in Step 3.

***

### Step 5: [Create Fabric Data Agent and query from Azure AI Foundry Agent](./docs/5-CreateAISkill.md) 
Create a Fabric Data Agent that uses the new star schema design in the Lakehouse or Warehouse. The Data Agent will enable natural language queries with text-to-SQL for your new end-to-end Fabric solution. Optionally, instructions for querying the Fabric Data Agent from an Azure AI Foundry Agent are at the end of this section.

