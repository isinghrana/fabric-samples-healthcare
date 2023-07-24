# Direct Lake Connector with 220M+ Rows


## Scenario
The Fabric Direct Lake conenctor is a new technology for querying delta parquet files from Power BI without data caching or an intermediary relational database. Power BI datasets have been modernized so that the semantic layer containing metadata and query logic can directly query the Fabric Data Lake. Data for the demo is 220M+ rows of real healthcare data from the open data database titled **Medicare Part D Prescribers - by Provider and Drug**. Link here: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug 

## Scope
This demo is intended to provide experience with using the Direct Lake connector in Power BI to query large volumes of real data. The demo is not intended to represent the best possible arhitecture for the data model, or the best method to architect the delta parquet portion of the design. The demo will be updated in future interations to include a dimensional model, but the first version will be a simple flattened delta parquet table that can be queried directly from Power BI. 

Tutorial follows similar walkthrough experience as the tutorial in [public docuemntation](https://learn.microsoft.com/en-us/fabric/data-science/tutorial-data-science-introduction)

![Fabric Data Science](./directlake-architecture.png)  ![analytics-bi-directlake](./Images/DirectLake_Architecture.png) 

1. [Ingest Data for Sample Diabetest Dataset saved in this Github Repo itself](./01-Ingest-Diabetes-Dataset-to-Lakehouse.ipynb)
2. [Explore and Pre-Process Data](./02-data-analysis-preprocess.ipynb)
3. [Train and Registry Machine Learning Prediction Model](./03-Train-Register-DiabetesPredictionModel.ipynb) 
4. [Perform Batch Predictions on simliuation data](./04-Perform-Diabetes-Batch-Predictions.ipynb)
