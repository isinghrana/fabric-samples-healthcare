# Power BI Semantic Model - Smart Prompt (AI-Guided Design)

## 🎯 What I Need

Enhance the existing bare bones semantic model with tables to production-ready Power BI semantic model for analyzing Medicare Part D prescription drug costs. The model should enable business users to analyze drug spending patterns across time, geography, providers, and drug types.


---

## Prepare environment
**Critical**: Make sure powerbi-modeling-mcp is available and is used for model development. If not, stop and prompt the user to install it. Learn about the powerbi-modeling-mcp tools and always prioritize using Batch tools. For example, when creating objects always try to create them in batches to minimize round-trips.


**Data Source Context:**  
CMS (Centers for Medicare & Medicaid Services) Part D prescription data showing drug costs by provider, geography, and year. Public dataset link - https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug
---


## 🎯 Business Requirements

### Analysis Goals
Users need to answer questions like:
- What are drug cost trends over time?
- Which states have highest drug costs?
- How do costs vary by provider specialty?
- What's the cost difference between brand and generic drugs?
- How efficiently are drugs being prescribed? (cost per claim, cost per day)

### Expected Users
- Healthcare analysts
- Policy researchers  
- Business intelligence teams
- Executive dashboards

---

## 🧠 Design Guidelines (AI: Use Your Expertise!)

### Relationships
- This is clearly a star schema pattern
- Detect the proper keys and create logical relationships
- Use appropriate cardinality and filter directions

### Table Naming
- Make table names busines-user friendly

### Column Naming & Visibility
- Make column names business-user friendly (no abbreviations like "Prscrbr")
- Hide technical columns (keys, flags, internal tracking fields)
- Show columns that provide business value
- Fact table measures should be hidden (use DAX measures instead)

### Data Types & Formatting
- Apply appropriate formats (currency, whole numbers, decimals)
- Set geographic data categories where applicable
- Format measures with proper decimal places and separators

### DAX Measures
Create useful measures that support the business goals:
- Basic aggregations (Total Claims, Total Cost, Total Beneficiaries, etc.)
- Calculated KPIs (Cost per Claim, Cost per Day, Days per Claim, etc.)
- Any other measures that would be helpful for drug cost analysis

### Best Practices
- Optimize for Direct Lake performance
- Ensure model is intuitive for self-service analytics
- Apply consistent naming conventions

---
## Other Critical Notes
- Columns starting with prefix GE65 are for Beneficiaries aged 65 or more and these can be safely ignored as there is no need for anaylsis of this category of information. No need to create measure
- I have observed conflicts in DAX measure names conflicting with columns so make sure to name measures appropriately from the begining so there is no need go back and forth fixing error because of name conflicts 
- I have observed "CalculationNeeded" error message when trying to use the newly created Semantic Model so please make sure model is approrpriately saved and ready to be used right away.
- Lastly save the details on exact work done to build out the model to a log file with name run_log.md