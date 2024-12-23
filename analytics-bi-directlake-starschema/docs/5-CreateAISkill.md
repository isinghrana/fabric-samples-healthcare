## Create Fabric AI Skill

1. You can create a new Fabric AI Skill while in your Workspace by clicking **+ New item** > **AI Skill (preview)**. Give the AI Skill a name and click **Create**.
2. Next, select the Fabric LAkehouse or Warehouse that you would like to query using the AI Skill. If you followed step 2a and deployed a star schema in the Lakehouse select **cms_lakehouse**, and if you followed step 2b and deployed a star schema in the warehouse select **cms_warehouse.** Then click **Confirm.**
3. In the vertical panel on the left hand side of the screen, select the five tables **cms_provider_dim_drug**, **cms_provider_dim_provider**, **cms_provider_dim_drug**, **cms_provider_dim_geography**, **year**, and **cms_provider_drug_costs_star**. The boxes next to the table names should be checked green. Click **Get Started** in the middle of the screen.
4. In the column on the right side of the page named **Model behavior** you will see a setting for **SQL query variations** at the top. I usually leave it at the default setting of **3** but you can theoretically 1) increase it for more back-end iterations of query versions from the underlying LLM (Azure OpenAI **L**arge **L**anguage **M**odel), or 2) decrease it for fewer query variations. Fabric CU compute usage will theoretically go up and down as you change the values, too.
5. The setting on the right hand side for **Notes for model** will give instructions to the LLM that provide context or metadata for the queries. This text is similar to a System message in Azure AI Foundry Chat. Paste in text from the example from the repo [AI_Skills_01_NotesForModel.txt](../scripts/AI_Skills_01_NotesForModel.txt) for initial testing. This example text was modified and optimized over the course of a few hours, but you can also experiment with changing it and improving the results. If you make significant improvements, please let us know and pass them along! 
6. Download the .json file from the repo at this link: 
7. The last setting in the right hand column is titled **Example SQL queries**. Click the pencil icon next to that heading. 
8. You can also use "Analyze in Excel" from the ellipse next to the dataset in the Fabric Workspace.
9. You can use the existing report template by downloading a copy of the Power BI Report template from the file in this repo at [analytics-bi-directlake-warehouse-starschema](../CMS%20Medicare%20Part%20D%20Star%20Schema%20Template.pbix)
    - Open the file using Power BI Desktop
  - Connect to your Fabric Lakehouse
  - Publish the Power BI report to your Fabric Workspace
The Power BI Report that connects to the Direct Lake Semantic Model shoul look like this, and be ready for use with Power BI Copilot:
![analytics-bi-directlake](../Images/ReportExample.png) 

*** 
[Back to main Readme](../Readme.md#step-4-create-reports-using-power-bi-or-connect-using-excel----steps-are-manual-at-this-time-but-in-future-plan-to-automate-for-quick-setup-) 
