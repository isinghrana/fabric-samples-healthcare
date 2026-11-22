# Installation Notebook: Plan

> **Status:** Built and tested. A clean install in a scratch workspace from branch `isr-fda-1`, with `p_quarters = 2004q1`, succeeded: the installer took 86 s on 1 executor; the pipeline then ran Download → Silver → Gold with every validation check passing, and a re-run skipped work already done. The default `p_github_branch = main` works once `isr-fda-1` is merged.
>
> **Goal:** A user downloads one notebook from GitHub, imports it into a Fabric workspace and runs it. With no manual steps, it creates the lakehouse, installs the notebooks and pipeline from GitHub, and starts the pipeline that downloads the openFDA data and builds Silver and Gold.

---

## 1. User experience

1. Download `nb_fda_install.ipynb` from the GitHub repository.
2. In a Fabric workspace that has a capacity assigned, select **Import → Notebook → From this computer**.
3. Open the notebook, optionally change the parameters cell, then select **Run all**. No lakehouse needs to be attached.
4. After a few minutes the notebook finishes and prints the items it created and a link to the running pipeline. The pipeline keeps running on its own (several hours for the full dataset).
5. The user follows progress in the pipeline's run view or the Monitoring hub.

Running the installer again is safe: existing items are updated instead of duplicated, and it won't start a second pipeline run while one is still running.

---

## 2. What gets installed

| Item | Type | Source in GitHub | Notes |
|---|---|---|---|
| `fda_adverse_events_lakehouse` (name is a parameter) | Lakehouse, schema-enabled | Created by the installer | Holds `Files/fda_ds`, `Files/fda_ds_unzipped` and the `silver` and `gold` schemas |
| `nb_fda_00_download_dataset` | Notebook | `fda_adverse_event_dataset/nb_fda_00_download_dataset.ipynb` | Default lakehouse set to the new lakehouse |
| `nb_fda_01_silver_load` | Notebook | `fda_adverse_event_dataset/nb_fda_01_silver_load.ipynb` | Default lakehouse set to the new lakehouse |
| `nb_fda_02_gold_build` | Notebook | `fda_adverse_event_dataset/nb_fda_02_gold_build.ipynb` | Default lakehouse set to the new lakehouse |
| `pl_fda_one_time_build` | Data pipeline | `fda_adverse_event_dataset/pl_fda_one_time_build.json` | Download → Load Silver → Build Gold, with this workspace's notebook IDs filled in |

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
| 2 | Download artifacts from GitHub | Reads `install-manifest.json` (§4) from `https://raw.githubusercontent.com/{repo}/{branch}/{folder}/`, then each file it lists. Checks HTTP 200 and that each file is valid JSON. Retries on transient errors. Nothing is written to Fabric until every file has downloaded. |
| 3 | Create or reuse the lakehouse | Works in the workspace the notebook runs in (`notebookutils.runtime.context["currentWorkspaceId"]`) and calls the Fabric REST API with the signed-in user's token (`notebookutils.credentials.getToken("pbi")`). Lists lakehouses and reuses an exact name match; otherwise `POST /v1/workspaces/{ws}/lakehouses` with `creationPayload.enableSchemas = true`, then polls the long-running operation. Fails if an existing lakehouse with that name is not schema-enabled. |
| 4 | Install the notebooks | For each notebook, rewrites `metadata.dependencies.lakehouse` (`default_lakehouse`, `default_lakehouse_name`, `default_lakehouse_workspace_id`, `known_lakehouses`) to the lakehouse from step 3. A new notebook is created with `POST /items` and an existing one is updated with `updateDefinition` (format `ipynb`). Both long-running operations are polled until done. |
| 5 | Install the pipeline | Replaces the placeholders in the pipeline JSON (§5) with the workspace ID and the notebook IDs from step 4. Fails if any `{{...}}` remains. Then creates the pipeline (part `pipeline-content.json`) or updates its definition. |
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

The manifest lists what to install, so the installer code doesn't change when artifacts are added. Each entry has a `name` (the Fabric item name), a `file` in the GitHub folder and a `description` for the Fabric item:

```json
{
  "notebooks": [
    { "name": "nb_fda_00_download_dataset", "file": "nb_fda_00_download_dataset.ipynb", "description": "..." },
    { "name": "nb_fda_01_silver_load",      "file": "nb_fda_01_silver_load.ipynb",      "description": "..." },
    { "name": "nb_fda_02_gold_build",       "file": "nb_fda_02_gold_build.ipynb",       "description": "..." }
  ],
  "pipelines": [
    { "name": "pl_fda_one_time_build", "file": "pl_fda_one_time_build.json", "description": "..." }
  ],
  "runPipeline": "pl_fda_one_time_build"
}
```

The lakehouse name comes from the `p_lakehouse_name` parameter, not from the manifest.

---

## 5. Changes to the existing artifacts

### 5.1 Pipeline `pl_fda_one_time_build.json`

| Change | Details |
|---|---|
| New first activity **Download Dataset** | Runs `nb_fda_00_download_dataset`. Timeout `1.00:00:00`, retry 1 (the notebook skips files already downloaded, so a retry only redoes failed files). **Load Silver** then depends on it succeeding. |
| Placeholders instead of hard-coded IDs | `notebookId` becomes `{{notebook:nb_fda_00_download_dataset}}`, `{{notebook:nb_fda_01_silver_load}}` or `{{notebook:nb_fda_02_gold_build}}`, and `workspaceId` becomes `{{workspace_id}}`. The installer and my deploy script fill them in. |
| New pipeline parameters | `p_max_parallel_downloads` (16), `p_max_parallel_unzips` (8), `p_overwrite_existing` (false), passed to the download notebook. `p_quarters` is passed to **both** Download and Load Silver, so a demo install downloads and loads the same quarters. |
| Description | Updated to: Download → Silver → Gold. |

### 5.2 Notebooks

| Notebook | Change | Why |
|---|---|---|
| `nb_fda_00_download_dataset` | No changes for now (it is being tested). Later, its header should say that it runs as the first pipeline step | Docs |
| `nb_fda_01_silver_load` | Fails with a clear message if `p_source_path` has no openFDA JSON files ("run `nb_fda_00_download_dataset` first"). Header notes its place in the pipeline and that the installer sets its lakehouse | Fresh installs |
| `nb_fda_02_gold_build` | Fails with a clear message if any Silver table is missing ("run `nb_fda_01_silver_load` first"). Header notes its place in the pipeline and that the installer sets its lakehouse | Fresh installs |
| All three notebooks | **No code changes for the lakehouse.** They already use relative paths (`Files/...`, `/lakehouse/default/...`) and unqualified schemas (`silver.*`, `gold.*`), so they work against whatever default lakehouse the installer sets | Requirement 3 |
| All three notebooks | The `.ipynb` files in GitHub keep this workspace's lakehouse binding; the installer overwrites it at install time | Keeps the repo files directly usable in the dev workspace |
| All three notebooks | `%%configure` stays as it is: none on the download notebook, and 8 fixed executors on Silver and Gold (an F64-class capacity is a prerequisite) | Only the installer gets a new `%%configure` |

### 5.3 Repository and dev tooling

- `nb_fda_install.ipynb`, `install-manifest.json` and this plan are in `fda_adverse_event_dataset/`.
- `README.md` has a **Quick install** section.
- The plan's §7 run guide describes the pipeline with its download step.
- The pipeline file in the repo contains placeholders, so it can't be pasted into a workspace as is. Install it with `nb_fda_install`, or fill in the placeholders the same way. The dev workspace's pipeline still has the earlier two-step version, because the download notebook there is bound to `fda_lh2` while it is being tested.
- **The artifacts must be on the branch the installer reads.** They are pushed to `isr-fda-1`; until that branch is merged to `main`, install with `p_github_branch = isr-fda-1`.

---

## 6. Prerequisites to document

| Prerequisite | Why |
|---|---|
| Fabric workspace on a capacity (F64 recommended) | Silver and Gold request 8 executors; smaller SKUs may queue or fail |
| Workspace role **Contributor** or higher | Create items and run jobs |
| About **700 GB** of OneLake storage for the full dataset | Zips about 115 GB plus JSON about 580 GB, plus Delta tables |
| Outbound internet from Spark to `raw.githubusercontent.com`, `api.fda.gov` and `download.open.fda.gov` | Artifact and data downloads. Workspaces with outbound access protection would block this |
| Run time | Download plus Silver plus Gold takes several hours for the full dataset; a `p_quarters` demo takes much less |

---

## 7. Testing plan

1. **Unit-level:** run the placeholder substitution and lakehouse rewrite locally against the repo files, and check the output definitions.
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
| 3 | `%%configure` on the other notebooks | Unchanged. Only the installer gets a new `%%configure` |
| 4 | Pipeline name | Keep `pl_fda_one_time_build` |
| 5 | Workspace folder | None; items are created at the workspace root |
