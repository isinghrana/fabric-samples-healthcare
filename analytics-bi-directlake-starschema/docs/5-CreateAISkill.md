## Create Fabric AI Skill

1. You can create a new Fabric AI Skill while in your Workspace by clicking **+ New item** > **AI Skill (preview)**. Give the AI Skill a name and click **Create**.
2. Next, select the Fabric LAkehouse or Warehouse that you would like to query using the AI Skill. If you followed step 2a and deployed a star schema in the Lakehouse select **cms_lakehouse**, and if you followed step 2b and deployed a star schema in the warehouse select **cms_warehouse.** Then click **Confirm.**
3. In the vertical panel on the left hand side of the screen, select the five tables **cms_provider_dim_drug**, **cms_provider_dim_provider**, **cms_provider_dim_drug**, **cms_provider_dim_geography**, **year**, and **cms_provider_drug_costs_star**. The check boxes next to the table names should be green. Click **Get Started** in the middle of the screen.
4. 
5. You can also use "Analyze in Excel" from the ellipse next to the dataset in the Fabric Workspace.
6. You can use the existing report template by downloading a copy of the Power BI Report template from the file in this repo at [analytics-bi-directlake-warehouse-starschema](../CMS%20Medicare%20Part%20D%20Star%20Schema%20Template.pbix)
  - Open the file using Power BI Desktop
  - Connect to your Fabric Lakehouse
  - Publish the Power BI report to your Fabric Workspace
The Power BI Report that connects to the Direct Lake Semantic Model shoul look like this, and be ready for use with Power BI Copilot:
![analytics-bi-directlake](../Images/ReportExample.png) 

*** 
[Back to main Readme](../Readme.md#step-4-create-reports-using-power-bi-or-connect-using-excel----steps-are-manual-at-this-time-but-in-future-plan-to-automate-for-quick-setup-) 
