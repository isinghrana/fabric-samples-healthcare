# Diabetes Prediction


## Scenario
Diabetes is a chronic disease that affects millions of people worldwide. Early detection and diagnosis of diabetes can help prevent complications and improve patient outcomes. In this sample we will use sample dataset with attributes like glucose, blood pressure, age, etc. to bulid a Machine Learning model to predict likelihood of catching diabetes which can be helpful in taking pro-active measures to reduce the risk. 

## Scope
Please note the intent of the tutorial is to demonstrate the Fabric tooling for Data Science Scenarios and might not represent the best data science techniques or algorithms used. Also, the dataset used only has a few hundred records so not meant to demonstrate scalable performance capabities of Microsoft Fabric.

Tutorial follows similar walkthrough experience as the tutorial in [public docuemntation](https://learn.microsoft.com/en-us/fabric/data-science/tutorial-data-science-introduction)

![Fabric Data Science](./data-science-scenario.png)

1. [Ingest Data for Sample Diabetest Dataset saved in this Github Repo itself](./01-Ingest-Diabetes-Dataset-to-Lakehouse.ipynb)
2. [Explore and Pre-Process Data](./02-data-analysis-preprocess.ipynb)
3. [Train and Registry Machine Learning Prediction Model](./03-Train-Register-DiabetesPredictionModel.ipynb) 
4. [Perform Batch Predictions on simliuation data](./04-Perform-Diabetes-Batch-Predictions.ipynb)