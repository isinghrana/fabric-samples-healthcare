# FDA Human Drug Adverse Events: Medallion Architecture on Microsoft Fabric

This sample builds a medallion lakehouse over the openFDA Drug Adverse Event (FAERS) bulk JSON dataset. The raw JSON files are Bronze, and Silver and Gold are Delta tables. Gold serves a Direct Lake semantic model for Power BI, a Fabric Data Agent, and a Rayfin app.

- **Plan and run guide:** [medallion-architecture-plan.md](./medallion-architecture-plan.md)
- **Installer design:** [installation-plan.md](./installation-plan.md)
- **Data dictionary and lineage:** [data-dictionary.html](./data-dictionary.html) lists every Silver and Gold table and column, with its source JSON field or derivation
- **Notebooks:**
  - [nb_fda_install.ipynb](./nb_fda_install.ipynb): one-step installer (see Quick install below)
  - [nb_fda_00_download_dataset.ipynb](./nb_fda_00_download_dataset.ipynb): downloads and unzips the openFDA bulk files (pipeline step 1)
  - [nb_fda_01_silver_load.ipynb](./nb_fda_01_silver_load.ipynb): loads the JSON files into Silver
  - [nb_fda_02_gold_build.ipynb](./nb_fda_02_gold_build.ipynb): builds Gold from Silver
- **Pipeline:** [pl_fda_one_time_build.json](./pl_fda_one_time_build.json) runs Download Dataset → Load Silver → Build Gold. Its notebook and workspace IDs are placeholders filled in by the installer
- **Source data:** [openFDA downloads](https://open.fda.gov/data/downloads/) · [Drug adverse event API](https://open.fda.gov/apis/drug/event/)

## Quick install

**Prerequisites:**
- A Fabric workspace on a capacity (F64 recommended)
- The Contributor role or higher
- About 700 GB of OneLake storage for the full dataset

1. Download [nb_fda_install.ipynb](./nb_fda_install.ipynb).
2. In the workspace, select **Import → Notebook → From this computer** and pick the file.
3. Open the notebook and select **Run all**. You don't need to attach a lakehouse.

The installer:
- creates the `fda_adverse_events_lakehouse` lakehouse;
- installs the three notebooks and the pipeline from this repository;
- starts the pipeline, then finishes without waiting for it.

Follow the pipeline in its **Run history** or in the **Monitoring hub**. The full dataset takes several hours. For a quick demo, set `p_quarters` in the parameters cell to a few quarters (for example `2025q1,2025q2`). Use `p_github_branch` to install from another branch. Running the installer again updates the items and does not start a second pipeline run while one is in progress.

> FAERS reports are unvalidated and cannot establish causality or incidence, and drug names are derived by simple demo-level rules. See the full [disclaimer](./medallion-architecture-plan.md#8-disclaimer).
