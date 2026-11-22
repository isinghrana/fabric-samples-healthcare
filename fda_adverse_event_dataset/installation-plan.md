# Installation Notebook: Plan

> **Status:** Built and tested. A clean install in a scratch workspace from branch `isr-fda-1`, with `p_quarters = 2004q1`, succeeded. The installer took about 100 s on 1 executor and installed the items from the `workspace/` folder (Git integration layout). The pipeline then ran Download (on executors) → Silver → Gold in 12 minutes, with every validation check passing. The default `p_github_branch = main` works once `isr-fda-1` is merged.
>
> **Goal:** A user downloads one notebook from GitHub, imports it into a Fabric workspace and runs it. With no manual steps, it creates the lakehouse, installs the notebooks and pipeline from GitHub, and starts the pipeline that downloads the openFDA data and builds Silver and Gold.

---

## 1. User experience

1. Download `nb_fda_install.ipynb` from the GitHub repository.
2. In a Fabric workspace that has a capacity assigned, select **Import → Notebook → From this computer**.
3. Open the notebook, optionally change the parameters cell, then select **Run all**. No lakehouse needs to be attached.
4. After a few minutes the notebook finishes and prints the items it created and a link to the running pipeline. The pipeline keeps running on its own (an hour or more for the full dataset).
5. The user follows progress in the pipeline's run view or the Monitoring hub.

Running the installer again is safe: existing items are updated instead of duplicated, and it won't start a second pipeline run while one is still running.

---

## 2. What gets installed

| Item | Type | Source in GitHub | Notes |
|---|---|---|---|
| `fda_adverse_events_lakehouse` (name is a parameter) | Lakehouse, schema-enabled | Created by the installer | Holds `Files/fda_ds`, `Files/fda_ds_unzipped` and the `silver` and `gold` schemas |
| `nb_fda_00_download_dataset` | Notebook | `workspace/nb_fda_00_download_dataset.Notebook/notebook-content.py` | Default lakehouse set to the new lakehouse |
| `nb_fda_01_silver_load` | Notebook | `workspace/nb_fda_01_silver_load.Notebook/notebook-content.py` | Default lakehouse set to the new lakehouse |
| `nb_fda_02_gold_build` | Notebook | `workspace/nb_fda_02_gold_build.Notebook/notebook-content.py` | Default lakehouse set to the new lakehouse |
| `pl_fda_one_time_build` | Data pipeline | `workspace/pl_fda_one_time_build.DataPipeline/pipeline-content.json` | Download → Load Silver → Build Gold, with its activities pointed at the installed notebooks |

Source paths are relative to `fda_adverse_event_dataset/`. The `workspace/` folder uses the Fabric Git integration layout: one `<name>.<Type>` folder per item with a `.platform` file and the item's content file, exported from the development workspace with the Fabric CLI (§5.3).

Everything is created in the workspace the installer runs in. Item names are fixed, so the Silver and Gold notebooks, the pipeline and the docs match.

---

## 3. Installer notebook design: `nb_fda_install`

### 3.1 Compute: driver only

The installer only calls REST APIs and GitHub; it never uses Spark. Its first cell keeps the session as small as possible:

```json
%%configure
{
    "driverCores": 8,
    "driverMemory": "56g",
    "executorCores": 8,
    "executorMemory": "56g",
    "conf": {
        "spark.dynamicAllocation.minExecutors": "1",
        "spark.dynamicAllocation.maxExecutors": "1"
    }
}
```

- A Spark session always has a driver plus at least one executor, so 1 executor is the smallest possible.
- Node size matches the Starter Pool's Medium nodes (8 cores, 56 GB). Asking for a smaller size would need a custom session, which starts more slowly than the Starter Pool.
- Only the installer gets this cell. The download, Silver and Gold notebooks keep their current `%%configure` settings, or lack of one.

### 3.2 Parameters

| Parameter | Default | Purpose |
|---|---|---|
| `p_lakehouse_name` | `fda_adverse_events_lakehouse` | Lakehouse to create, or reuse if it exists |
| `p_github_repo` | `isinghrana/fabric-samples-healthcare` | Repository to download the artifacts from |
| `p_github_branch` | `main` | Branch to download the artifacts from, for example `isr-fda-1` to test unmerged work |
| `p_github_folder` | `fda_adverse_event_dataset` | Folder holding the artifacts and the manifest |
| `p_quarters` | `""` (all) | Passed to the pipeline. For example, `2025q1,2025q2` gives a small, fast demo install |
| `p_run_pipeline` | `True` | `False` installs the items without starting the pipeline |

### 3.3 Steps (one markdown cell plus one code cell each)

| # | Step | Details |
|---|---|---|
| 0 | `%%configure` | Driver-only session (§3.1) |
| 1 | Parameters | §3.2 |
| 2 | Download artifacts from GitHub | Reads `install-manifest.json` (§4) from `https://raw.githubusercontent.com/{repo}/{branch}/{folder}/`, then `notebook-content.py` and `pipeline-content.json` from each item folder it lists. Checks HTTP 200, that each notebook is a Fabric notebook source file and that the pipeline is valid JSON. Retries on transient errors. Nothing is written to Fabric until every file has downloaded. |
| 3 | Create or reuse the lakehouse | Works in the workspace the notebook runs in (`notebookutils.runtime.context["currentWorkspaceId"]`) and calls the Fabric REST API with the signed-in user's token (`notebookutils.credentials.getToken("pbi")`). Lists lakehouses and reuses an exact name match; otherwise `POST /v1/workspaces/{ws}/lakehouses` with `creationPayload.enableSchemas = true`, then polls the long-running operation. Fails if an existing lakehouse with that name is not schema-enabled. |
| 4 | Install the notebooks | For each notebook, rewrites the notebook-level `# META` block at the top of `notebook-content.py` so that `dependencies.lakehouse` (`default_lakehouse`, `default_lakehouse_name`, `default_lakehouse_workspace_id`, `known_lakehouses`) points to the lakehouse from step 3. A new notebook is created with `POST /items` and an existing one is updated with `updateDefinition` (part `notebook-content.py`). Both long-running operations are polled until done. |
| 5 | Install the pipeline | The exported pipeline refers to the development workspace's ID and notebook IDs. Using `sourceWorkspaceId` and each notebook's `sourceItemId` from the manifest, it replaces them with this workspace's ID and the notebook IDs from step 4, and fails if any source ID remains. Then it creates the pipeline (part `pipeline-content.json`) or updates its definition. |
| 6 | Start the pipeline (asynchronous) | If `p_run_pipeline` is true: first checks the pipeline's job instances. If a run is `NotStarted` or `InProgress`, it reports that run instead of starting another. Otherwise it calls `POST /v1/workspaces/{ws}/items/{pipelineId}/jobs/instances?jobType=Pipeline` with `p_quarters`. It reads the run ID from the `Location` header and **does not poll**. |
| 7 | Summary | Prints a table of the items with their IDs and links, the pipeline run ID, the expected duration, and how to check the status: the pipeline's **Run history** link (`https://app.fabric.microsoft.com/groups/{ws}/pipelines/{id}`) and the **Monitoring hub**. It also explains how to resume: rerun the pipeline, and completed work is skipped. |

### 3.4 Behaviour and safeguards

- **Idempotent:** items are matched by name and updated, never duplicated. The lakehouse and its data are never deleted.
- **All or nothing for downloads:** GitHub downloads finish and are validated before any Fabric item is touched.
- **Clear failures:** every REST error prints the call, the HTTP status and the error body, then stops.
- **No secrets:** it uses only the signed-in user's token; the GitHub repository is public, so no GitHub token is needed.
- **Runs as the user:** the pipeline run, and the notebooks inside it, run under the identity of whoever runs the installer.

---

## 4. `install-manifest.json`

The manifest lists what to install, so the installer code doesn't change when artifacts are added. `itemsFolder` is the folder holding the item folders. Each entry has a `name` (the Fabric item name), its `folder`, its `sourceItemId` in the development workspace and a `description` for the Fabric item. The export script (§5.3) fills in `sourceWorkspaceId` and the `sourceItemId` values:

```json
{
  "itemsFolder": "workspace",
  "sourceWorkspaceId": "<development workspace ID>",
  "notebooks": [
    { "name": "nb_fda_00_download_dataset", "folder": "nb_fda_00_download_dataset.Notebook", "sourceItemId": "...", "description": "..." },
    { "name": "nb_fda_01_silver_load",      "folder": "nb_fda_01_silver_load.Notebook",      "sourceItemId": "...", "description": "..." },
    { "name": "nb_fda_02_gold_build",       "folder": "nb_fda_02_gold_build.Notebook",       "sourceItemId": "...", "description": "..." }
  ],
  "pipelines": [
    { "name": "pl_fda_one_time_build", "folder": "pl_fda_one_time_build.DataPipeline", "sourceItemId": "...", "description": "..." }
  ],
  "runPipeline": "pl_fda_one_time_build"
}
```

The lakehouse name comes from the `p_lakehouse_name` parameter, not from the manifest.

---

## 5. Changes to the existing artifacts

### 5.1 Pipeline `pl_fda_one_time_build`

| Change | Details |
|---|---|
| New first activity **Download Dataset** | Runs `nb_fda_00_download_dataset`. Timeout `1.00:00:00`, retry 1 (the notebook skips files already downloaded, so a retry only redoes failed files). **Load Silver** then depends on it succeeding. |
| New pipeline parameters | `p_max_parallel_downloads` (16) and `p_overwrite_existing` (false), passed to the download notebook. `p_quarters` is passed to **both** Download and Load Silver, so a demo install downloads and loads the same quarters. |
| Description | Download → Silver → Gold. |

### 5.2 Notebooks

| Notebook | Change | Why |
|---|---|---|
| `nb_fda_00_download_dataset` | Downloads and unzips on the **Spark executors** instead of in driver threads. A `%%configure` cell holds 8 executors, like Silver and Gold, and the notebook waits up to 5 minutes for them to join. Downloads run as `p_max_parallel_downloads` tasks, with files grouped so each task gets a similar total size. Unzips run as one task per file, largest first. The lakehouse mount `/lakehouse/default` exists on every executor, so the tasks use plain file I/O. On 7 quarters (218 files) it downloaded 20.6 GB in 20 s and unzipped 107 GB in 36 s; driver-thread unzipping had taken over an hour for the full dataset. | Speed |
| `nb_fda_00_download_dataset` | Fails with a clear message if no default lakehouse is attached. Without this check, `/lakehouse/default/Files` would be created on the driver's local disk and the download would go there. The header notes that it is the first pipeline step and that the installer sets its lakehouse | Fresh installs |
| `nb_fda_01_silver_load` | Fails with a clear message if `p_source_path` has no openFDA JSON files ("run `nb_fda_00_download_dataset` first"). The header notes its place in the pipeline and that the installer sets its lakehouse | Fresh installs |
| `nb_fda_02_gold_build` | Fails with a clear message if any Silver table is missing ("run `nb_fda_01_silver_load` first"). The header notes its place in the pipeline and that the installer sets its lakehouse | Fresh installs |
| All three notebooks | **No code changes for the lakehouse.** They use relative paths (`Files/...`, `/lakehouse/default/...`) and unqualified schemas (`silver.*`, `gold.*`), so they work against whatever default lakehouse the installer sets | Requirement 3 |

### 5.3 Repository and export

- `fda_adverse_event_dataset/workspace/` holds the notebooks and the pipeline in the Fabric Git integration layout. It is produced with the Fabric CLI: `fab export "<workspace>.Workspace/<item>" -o <folder> -f`, with `--format .py` for notebooks, as Git integration stores them. Two steps follow the export:
  - each `.platform` gets a stable, unique `logicalId`, because the CLI writes all zeros and Git integration needs unique IDs;
  - the item IDs in the development workspace are written to `install-manifest.json`.
- The exported files keep the development workspace's IDs (the lakehouse binding in each notebook, and the notebook and workspace IDs in the pipeline). The installer replaces them at install time (§3.3).
- Known Fabric CLI 1.7.0 issue: `fab export --format .py` fails with `string indices must be integers` when a notebook's text contains the word "cells". The notebooks avoid that word.
- `nb_fda_install.ipynb`, `install-manifest.json` and this plan are in `fda_adverse_event_dataset/`. `README.md` has a **Quick install** section.
- **The artifacts must be on the branch the installer reads.** They are pushed to `isr-fda-1`; until that branch is merged to `main`, install with `p_github_branch = isr-fda-1`.

---

## 6. Prerequisites to document

| Prerequisite | Why |
|---|---|
| Fabric workspace on a capacity (F64 recommended) | The download, Silver and Gold notebooks each request 8 executors; smaller SKUs may queue or fail |
| Workspace role **Contributor** or higher | Create items and run jobs |
| About **700 GB** of OneLake storage for the full dataset | Zips about 115 GB plus JSON about 580 GB, plus Delta tables |
| Outbound internet from Spark to `raw.githubusercontent.com`, `api.fda.gov` and `download.open.fda.gov` | Artifact and data downloads. Workspaces with outbound access protection would block this |
| Run time | Download plus Silver plus Gold can take an hour or more for the full dataset; a `p_quarters` demo takes much less |

---

## 7. Testing plan

1. **Unit-level:** run the `# META` lakehouse rewrite and the pipeline ID remapping locally against the exported files, and check the output definitions.
2. **Fresh install, demo size:** create a test workspace on the same capacity, import the installer, run it with `p_quarters = "2004q1"` and `p_github_branch = isr-fda-1`. Check that:
   - the items are created;
   - each notebook's default lakehouse is the new lakehouse;
   - the pipeline starts and the installer returns without waiting;
   - the pipeline completes: download → Silver → Gold;
   - the validation output from Silver and Gold is clean.
3. **Re-run:** run the installer again while the pipeline is running. It should update the items and report the existing run instead of starting a new one.
4. **Existing lakehouse:** run against a workspace where the lakehouse already exists. It should reuse it.
5. **Failure paths:** a bad `p_github_branch` should stop before any Fabric change, and a non-schema lakehouse with the same name should give a clear error.
6. **Clean up** the test workspace.

---

## 8. Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Installer kernel | PySpark notebook with a driver-only `%%configure` (min = max = 1 executor) |
| 2 | GitHub source | Branch is a parameter: `p_github_branch`, default `main` |
| 3 | `%%configure` on the other notebooks | Silver and Gold are unchanged (8 executors). The download notebook also holds 8 executors, because it now unzips on the executors |
| 4 | Pipeline name | Keep `pl_fda_one_time_build` |
| 5 | Workspace folder | None; items are created at the workspace root |
