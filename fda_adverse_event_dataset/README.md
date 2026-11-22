# FDA Human Drug Adverse Events: Medallion Architecture on Microsoft Fabric

This sample builds a medallion lakehouse over the openFDA Drug Adverse Event (FAERS) bulk JSON dataset. The raw JSON files are Bronze, and Silver and Gold are Delta tables. Gold serves a Direct Lake semantic model for Power BI, a Fabric Data Agent, and a Rayfin app.

- **Plan and run guide:** [medallion-architecture-plan.md](./medallion-architecture-plan.md)
- **Installer design:** [installation-plan.md](./installation-plan.md)
- **Data dictionary and lineage:** [data-dictionary.html](./data-dictionary.html) lists every Silver and Gold table and column, with its source JSON field or derivation
- **Notebooks and pipeline**, in the [workspace/](./workspace) folder. It uses the Fabric Git integration layout (one `<name>.<Type>` folder per item, exported with the Fabric CLI):
  - [nb_fda_00_download_dataset.Notebook](./workspace/nb_fda_00_download_dataset.Notebook): downloads and unzips the openFDA bulk files on the Spark executors (pipeline step 1)
  - [nb_fda_01_silver_load.Notebook](./workspace/nb_fda_01_silver_load.Notebook): loads the JSON files into Silver
  - [nb_fda_02_gold_build.Notebook](./workspace/nb_fda_02_gold_build.Notebook): builds Gold from Silver
  - [pl_fda_one_time_build.DataPipeline](./workspace/pl_fda_one_time_build.DataPipeline): runs Download Dataset → Load Silver → Build Gold
- **Installer:** [nb_fda_install.ipynb](./nb_fda_install.ipynb) installs everything in the `workspace/` folder, as listed in [install-manifest.json](./install-manifest.json) (see Quick install below)
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

Follow the pipeline in its **Run history** or in the **Monitoring hub**. The full dataset can take an hour or more. For a quick demo, set `p_quarters` in the parameters cell to a few quarters (for example `2025q1,2025q2`). Use `p_github_branch` to install from another branch. Running the installer again updates the items and does not start a second pipeline run while one is in progress.

## Updating the items in the repository

The `workspace/` folder is exported from the development workspace with the [Fabric CLI](https://aka.ms/fabric-cli), for example `fab export "<workspace>.Workspace/nb_fda_01_silver_load.Notebook" -o workspace --format .py -f`. The pipeline in it still refers to the development workspace's notebook and workspace IDs. Those IDs are recorded in `install-manifest.json` (`sourceWorkspaceId`, `sourceItemId`), and the installer swaps them for the IDs of the items it installs.

Known Fabric CLI 1.7.0 issue: `fab export --format .py` fails with `string indices must be integers` for a notebook whose text contains the word "cells". Rephrase that text, or export as `.ipynb`.

> FAERS reports are unvalidated and cannot establish causality or incidence, and drug names are derived by simple demo-level rules. See the full [disclaimer](./medallion-architecture-plan.md#8-disclaimer).
