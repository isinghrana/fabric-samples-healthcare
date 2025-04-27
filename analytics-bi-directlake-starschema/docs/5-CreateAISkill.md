## Create Fabric Data Agent

A video walking through the process below and giving a demonstration of the capabilities of a Data Agent using the contents of this repo can be found here:  (Note Data Agents were previously named "AI Skills". Any reference to "AI Skills" in this video refer to "Data Agents")    https://youtu.be/ftout8UX4lg 

1. You can create a new Fabric Data Agent while in your Workspace by clicking **+ New item** > **Data Agent (preview)**. Give the Data Agent a name and click **Create**.
2. Next, select the Fabric Lakehouse or Warehouse that you would like to query using the Data Agent. If you followed step 2a and deployed a star schema in the Lakehouse select **cms_lakehouse**, and if you followed step 2b and deployed a star schema in the warehouse select **cms_warehouse.** Then click **Confirm.**
3. In the vertical panel on the left hand side of the screen, select the five tables **cms_provider_dim_drug**, **cms_provider_dim_provider**, **cms_provider_dim_geography**, **cms_provider_dim_year**, and **cms_provider_drug_costs_star**. The boxes next to the table names should be checked green. Click **Get Started** in the middle of the screen.
5. Click the button at the top of the screen,  **Data Agent instructions**.   This will open a window where you can give instructions to the LLM that provide context or metadata for the queries. This text is similar to a System message in Azure AI Foundry Chat. Paste in text from the example in the repo [AI_Skills_01_NotesForModel.txt](../scripts/AI_Skills_01_NotesForModel.txt) for initial testing. This example text has been modified and optimized a few times, but you can also experiment with changing it and improving the results. Testing and new iterations may produce better results with a richer vocabulary. If you make significant improvements, please let us know and pass them along! Press **Data Agent instructions** again to hide the window.  
6. Download the .json file [AI_Skills_02_SQL_Examples.json](../scripts/AI_Skills_02_SQL_Examples.json)
7. Now press the **Example SQL queries** button at the top to enable the option for supplying sample sql queries. Click the pencil icon next to that heading. Click **Import from json** and Upload the file you just downloaded at [AI_Skills_02_SQL_Examples.json](../scripts/AI_Skills_02_SQL_Examples.json)   Click the X to close this window and the X again to cloes the Data Agent window.
8. Your Fabric Data Agent is now ready to test with natural language queries, and should look like this.  Red highlights show the 6 tables we selected and the Data Agent Instructions and Example Queries options we used.


![image](https://github.com/user-attachments/assets/d8bd2e1a-160f-48fa-9bd0-56cd18f77ef6)

9. A few examples of queries to try include.  Copy and paste these into the agent query box to try them.
   - Show the top 10 quinolone drugs prescribed by internists in florida in 2022
   - Show the Top 20 internists in Maine prescribing ace inhibitors in 2021
   - Show the top 5 doctors prescribing ARBs in Atlanta Georgia with the last name Smith in the year 2019
10. Words that the Data Agent demo will understand can be found in the text you pasted in **Notes for model** such as ace inhibitors, ARBs, quinolones, internists, etc.
11. Fabric Data Agents can be queried from Azure AI Foundry Agents to provide good math within Agentic solutions. The video at the following link walks you through the process for connecting to the Microsoft Fabric Data Agent created in this repo from an Azure AI SKill Agent: https://youtu.be/yQkbd1f6JFk  

*** 
[Back to main Readme](../Readme.md#step-5-create-AI-skill)
