# Direct Lake Connector with 220M+ Rows


## Scenario
The Fabric Direct Lake conenctor is a new technology for querying delta parquet files from Power BI without data caching or an intermediary relational database. Power BI datasets have been modified so that the semantic layer containing metadata and query logic can directly query the Fabric Data Lake. Data for the demo is 220M+ rows of real healthcare data from the open data database titled **Medicare Part D Prescribers - by Provider and Drug**. Link here: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug 

## Scope
Please note the intent of the tutorial is to demonstrate the Fabric tooling for Data Science Scenarios and might not represent the best data science techniques or algorithms used. Also, the dataset used only has a few hundred records so not meant to demonstrate scalable performance capabities of Microsoft Fabric.

Tutorial follows similar walkthrough experience as the tutorial in [public docuemntation](https://learn.microsoft.com/en-us/fabric/data-science/tutorial-data-science-introduction)

![Fabric Data Science](./data-science-scenario.png)

1. [Ingest Data for Sample Diabetest Dataset saved in this Github Repo itself](./01-Ingest-Diabetes-Dataset-to-Lakehouse.ipynb)
2. [Explore and Pre-Process Data](./02-data-analysis-preprocess.ipynb)
3. [Train and Registry Machine Learning Prediction Model](./03-Train-Register-DiabetesPredictionModel.ipynb) 
4. [Perform Batch Predictions on simliuation data](./04-Perform-Diabetes-Batch-Predictions.ipynb)
