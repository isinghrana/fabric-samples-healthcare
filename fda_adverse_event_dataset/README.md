# FDA Human Drug Adverse Events: Medallion Architecture on Microsoft Fabric

This sample builds a medallion lakehouse over the openFDA Drug Adverse Event (FAERS) bulk JSON dataset. The raw JSON files are Bronze, and Silver and Gold are Delta tables. Gold serves a Direct Lake semantic model for Power BI, a Fabric Data Agent, and a Rayfin app.

- **Plan and run guide:** [medallion-architecture-plan.md](./medallion-architecture-plan.md)
- **Data dictionary and lineage:** [data-dictionary.html](./data-dictionary.html) lists every Silver and Gold table and column, with its source JSON field or derivation
- **Notebooks:**
  - [nb_fda_01_silver_load.ipynb](./nb_fda_01_silver_load.ipynb): loads the JSON files into Silver
  - [nb_fda_02_gold_build.ipynb](./nb_fda_02_gold_build.ipynb): builds Gold from Silver
- **Pipeline:** [pl_fda_one_time_build.json](./pl_fda_one_time_build.json) runs Silver, then Gold
- **Source data:** [openFDA downloads](https://open.fda.gov/data/downloads/) · [Drug adverse event API](https://open.fda.gov/apis/drug/event/)

> FAERS reports are unvalidated and cannot establish causality or incidence, and drug names are derived by simple demo-level rules. See the full [disclaimer](./medallion-architecture-plan.md#8-disclaimer).
