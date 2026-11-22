# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "cf5ef8dc-25a3-40c5-b969-736356b758c4",
# META       "default_lakehouse_name": "fda_adverse_events_lakehouse",
# META       "default_lakehouse_workspace_id": "13e6d67e-3693-4f4a-898b-5d0949b4aa9c"
# META     }
# META   }
# META }

# MARKDOWN ********************

# # FDA Drug Adverse Events: Download the openFDA bulk files
# 
# The [openFDA](https://open.fda.gov/data/downloads/) website publishes its datasets as zipped JSON files that can be downloaded manually or programmatically. This notebook downloads every file of the **Human Drug Adverse Event** dataset ([FAERS](https://open.fda.gov/apis/drug/event/)) and unzips it into the lakehouse.
# 
# After a successful run the default lakehouse has two folders:
# 
# | Folder | Contents |
# |---|---|
# | `Files/fda_ds` | The zipped files exactly as downloaded from openFDA, named `{quarter}-{file}`, for example `2025q4-drug-event-0001-of-0029.json.zip` |
# | `Files/fda_ds_unzipped` | One JSON file per zip, for example `2025q4-drug-event-0001-of-0029.json`. These raw JSON files are the Bronze layer read by `nb_fda_01_silver_load` |
# 
# **Size and run time**
# - The dataset has about 1,800 files: one folder per quarter since 2004 plus an `all_other` folder.
# - The zipped files total about 115 GB and the unzipped JSON about 580 GB.
# - Downloading and unzipping both run as Spark tasks spread across the executors, so the work is shared by every node instead of only the driver. Running it from a pipeline (or as a scheduled notebook run) avoids keeping an interactive session open.
# 
# **How it runs**: this is the first step of the `pl_fda_one_time_build` pipeline (Download Dataset → Load Silver → Build Gold). It writes to the notebook's default lakehouse, which `nb_fda_install` sets when it installs the notebook, so no lakehouse needs to be attached by hand. If no default lakehouse is attached, the notebook stops with an error instead of writing to the driver's local disk.
# 
# **Re-running is safe**: files that are already downloaded or unzipped are skipped, and incomplete files from an interrupted run are cleaned up and redone.

# MARKDOWN ********************

# ## Session size
# 
# Like the Silver and Gold notebooks, the session holds a fixed 8 executors (64 cores), so the unzip tasks run fully in parallel from the start instead of waiting for dynamic allocation to add nodes. This must be the first code cell.

# CELL ********************

# MAGIC %%configure
# MAGIC {
# MAGIC     "driverCores": 8,
# MAGIC     "driverMemory": "56g",
# MAGIC     "executorCores": 8,
# MAGIC     "executorMemory": "56g",
# MAGIC     "conf": {
# MAGIC         "spark.dynamicAllocation.minExecutors": "8",
# MAGIC         "spark.dynamicAllocation.maxExecutors": "8"
# MAGIC     }
# MAGIC }

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Parameters
# 
# `p_max_parallel_downloads` is the number of download tasks, and so the number of files downloaded at the same time. Unzipping has no limit of its own: it uses every executor core.

# PARAMETERS CELL ********************

p_quarters = ""                  # comma-separated quarters to process, e.g. "2004q1,2025q4,all_other"; empty = every file
p_max_parallel_downloads = 16    # concurrent downloads; try 24-32 if no 429/503 retries appear, lower it if they do
p_overwrite_existing = False     # True re-downloads and re-unzips files that already exist (use when openFDA republishes)
p_download_folder = "fda_ds"
p_unzip_folder = "fda_ds_unzipped"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Settings and helpers
# 
# Pipelines pass an empty parameter as `None`, so `param()` falls back to the default for blank values. Files are written through the default lakehouse's mount, `/lakehouse/default`. That mount exists on the driver **and on every executor**, so the Spark tasks can use plain Python file I/O against OneLake. The cell stops if no default lakehouse is attached. It also waits (up to 5 minutes) for the 8 executors to join, so the work is spread across all of them from the start.

# CELL ********************

import os
import shutil
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests


def param(value, default):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    return value


def as_bool(value):
    return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "1", "yes")


QUARTERS = {q.strip().lower() for q in (param(p_quarters, "") or "").split(",") if q.strip()}
MAX_PARALLEL_DOWNLOADS = max(1, int(param(p_max_parallel_downloads, 16)))
OVERWRITE_EXISTING = as_bool(param(p_overwrite_existing, False))

LAKEHOUSE_ROOT = Path("/lakehouse/default/Files")
if not LAKEHOUSE_ROOT.is_dir():
    raise RuntimeError("This notebook has no default lakehouse. Install it with nb_fda_install, "
                       "or attach a lakehouse as the default lakehouse and run it again.")
DOWNLOAD_DIRECTORY = LAKEHOUSE_ROOT / param(p_download_folder, "fda_ds")
UNZIP_DIRECTORY = LAKEHOUSE_ROOT / param(p_unzip_folder, "fda_ds_unzipped")
DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
UNZIP_DIRECTORY.mkdir(parents=True, exist_ok=True)

METADATA_URL = "https://api.fda.gov/download.json"
MAX_RETRIES = 5
CONNECT_TIMEOUT_SECONDS = 30
READ_TIMEOUT_SECONDS = 300
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024   # 8 MB
UNZIP_CHUNK_SIZE = 16 * 1024 * 1024     # 16 MB


def format_rate(total_bytes, seconds):
    gb = total_bytes / 1024**3
    mb_per_second = total_bytes / 1024**2 / seconds if seconds > 0 else 0
    return f"{gb:,.1f} GB in {seconds / 60:,.1f} min ({mb_per_second:,.0f} MB/s)"


def summarize(step, results, start, done_status):
    """Print counts and throughput for one step; fail the notebook if any file failed."""
    counts = {}
    for _, status, _, _ in results:
        counts[status] = counts.get(status, 0) + 1
    done_bytes = sum(size for _, status, size, _ in results if status == done_status)
    failures = [(name, error) for name, status, _, error in results if status == "failed"]

    print(f"\n{step} summary")
    print(f"{done_status.capitalize():<11} {counts.get(done_status, 0):,}  ({format_rate(done_bytes, time.time() - start)})")
    print(f"Skipped:    {counts.get('skipped', 0):,}")
    print(f"Failed:     {len(failures):,}")
    if failures:
        for name, error in failures[:20]:
            print(f"- {name}: {error}")
        raise RuntimeError(f"{len(failures)} file(s) failed in the {step.lower()} step; re-run the notebook to retry them")


def wait_for_executors(timeout_seconds=300):
    """Wait until the executors requested in %%configure have joined, so the first tasks don't all land on one node."""
    expected = int(sc.getConf().get("spark.dynamicAllocation.minExecutors", "1"))   # spark.conf.get doesn't show the session value
    deadline = time.time() + timeout_seconds
    while True:
        joined = sc._jsc.sc().getExecutorMemoryStatus().size() - 1   # the count includes the driver
        if joined >= expected or time.time() > deadline:
            return joined, expected
        time.sleep(10)


executors_joined, executors_expected = wait_for_executors()
print(f"Quarters:           {', '.join(sorted(QUARTERS)) if QUARTERS else 'all'}")
print(f"Parallel downloads: {MAX_PARALLEL_DOWNLOADS}")
print(f"Executors:          {executors_joined} of {executors_expected} joined")
print(f"Overwrite existing: {OVERWRITE_EXISTING}")
print(f"Download folder:    {DOWNLOAD_DIRECTORY}")
print(f"Unzip folder:       {UNZIP_DIRECTORY}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Step 1: Read the openFDA file list
# 
# openFDA publishes a metadata file, [download.json](https://api.fda.gov/download.json), that lists every downloadable file for every dataset. For the drug adverse event dataset, `results.drug.event.partitions` holds one entry per zip file with its URL and size. The quarter is taken from the URL folder (for example `.../drug/event/2025q4/drug-event-0001-of-0029.json.zip`) and prefixed to the file name, because file names repeat across quarters.
# 
# The cell stops with an error if the metadata can't be read, so the later steps never run on an empty list.

# CELL ********************

response = requests.get(METADATA_URL, timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS))
response.raise_for_status()
download_metadata_json = response.json()

event_metadata = download_metadata_json["results"]["drug"]["event"]
partitions = event_metadata["partitions"]
print(f"openFDA export date: {event_metadata.get('export_date', 'n/a')}")
print(f"Files listed:        {len(partitions):,}")


def build_download_item(partition):
    """Build the source URL and lakehouse file names for one openFDA file."""
    file_url = partition["file"]
    url_path = urlparse(file_url).path.strip("/").split("/")
    file_name, quarter = url_path[-1], url_path[-2]
    zip_name = f"{quarter}-{file_name}"
    return {
        "url": file_url,
        "quarter": quarter.lower(),
        "size_mb": float(partition.get("size_mb") or 0),
        "zip_name": zip_name,
        "zip_path": str(DOWNLOAD_DIRECTORY / zip_name),
        "json_path": str(UNZIP_DIRECTORY / (zip_name[:-4] if zip_name.lower().endswith(".zip") else zip_name)),
    }


download_items = [build_download_item(p) for p in partitions]
if QUARTERS:
    download_items = [item for item in download_items if item["quarter"] in QUARTERS]
    missing = QUARTERS - {item["quarter"] for item in download_items}
    if missing:
        raise ValueError(f"Quarters not found in the openFDA file list: {sorted(missing)}")

if not download_items:
    raise ValueError("No files to process")
print(f"Files selected:      {len(download_items):,}  ({sum(i['size_mb'] for i in download_items) / 1024:,.1f} GB zipped)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Step 2: Download the zip files on the executors
# 
# The files are split into `p_max_parallel_downloads` groups of about equal total size (using the sizes in `download.json`), and each group is downloaded by one Spark task. So that many files download at once, spread across the executor nodes:
# - **One HTTP session per task** with automatic retries. Timeouts, 429 (Too Many Requests) and 5xx errors are retried up to 5 times with exponential back-off, and the server's `Retry-After` header is honoured.
# - **Streaming in 8 MB chunks**, so a large file is never held in memory.
# - **Safe writes**: data goes to a `.partial` file that is renamed only after the full file (checked against `Content-Length`) has arrived, so the unzip step never sees a half-downloaded zip.
# - **Restartable**: files that already exist are skipped unless `p_overwrite_existing` is `True`.
# 
# A task records a failed file and moves on to its next file, instead of failing the whole Spark job. The cell fails at the end if any file could not be downloaded. Re-run it to retry only the failed files.

# CELL ********************

def make_http_session():
    """Create a retry-enabled HTTP session (one per Spark task)."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_policy = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[408, 425, 429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_policy, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "fabric-samples-healthcare/1.0 (FDA dataset download)"})
    return session


def download_file(session, item):
    """Stream one file to a .partial file, then rename it once complete."""
    destination_path = item["zip_path"]
    partial_path = destination_path + ".partial"

    if not OVERWRITE_EXISTING and os.path.exists(destination_path) and os.path.getsize(destination_path) > 0:
        return "skipped", os.path.getsize(destination_path)

    if os.path.exists(partial_path):
        os.remove(partial_path)

    try:
        with session.get(item["url"], stream=True, timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                         allow_redirects=True) as response:
            response.raise_for_status()
            expected_size = response.headers.get("Content-Length")
            expected_size = int(expected_size) if expected_size else None

            downloaded_size = 0
            with open(partial_path, "wb") as output_file:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        output_file.write(chunk)
                        downloaded_size += len(chunk)

            if expected_size is not None and downloaded_size != expected_size:
                raise IOError(f"Incomplete download: expected {expected_size:,} bytes, received {downloaded_size:,}")

        os.replace(partial_path, destination_path)
        return "downloaded", downloaded_size
    except Exception:
        if os.path.exists(partial_path):
            os.remove(partial_path)
        raise


def download_group(items):
    """Spark task: download a group of files, returning (file, status, bytes, error) for each."""
    session = make_http_session()
    results = []
    for item in items:
        try:
            status, size = download_file(session, item)
            results.append((item["zip_name"], status, size, None))
        except Exception as error:
            results.append((item["zip_name"], "failed", 0, repr(error)))
    return results


# Largest file first into the group with the smallest total, so every task gets a similar amount of data.
groups = [[] for _ in range(min(MAX_PARALLEL_DOWNLOADS, len(download_items)))]
group_mb = [0.0] * len(groups)
for item in sorted(download_items, key=lambda i: i["size_mb"], reverse=True):
    target = group_mb.index(min(group_mb))
    groups[target].append(item)
    group_mb[target] += item["size_mb"]

start = time.time()
sc.setJobDescription(f"Download {len(download_items):,} openFDA files in {len(groups)} tasks")
download_results = sc.parallelize(groups, len(groups)).flatMap(download_group).collect()
summarize("Download", download_results, start, "downloaded")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Step 3: Unzip the files on the executors
# 
# Each zip becomes its own Spark task, and the tasks are queued largest first so the biggest files don't finish last. With 8 executors, 64 files are unzipped at the same time.
# 
# Each zip is expected to hold exactly one JSON file. A zip with zero or several files is reported as failed, so a change in the openFDA format is noticed instead of silently loading the wrong file. Extraction streams the JSON in 16 MB chunks, so even files of close to 1 GB are never fully loaded into memory. Like the download, output goes to a `.partial` file that is renamed when complete, and JSON files that already exist are skipped.

# CELL ********************

def unzip_file(item):
    """Spark task: extract the single JSON file from one zip, returning (file, status, bytes, error)."""
    output_path = item["json_path"]
    partial_path = output_path + ".partial"
    try:
        if not OVERWRITE_EXISTING and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return item["zip_name"], "skipped", os.path.getsize(output_path), None

        if os.path.exists(partial_path):
            os.remove(partial_path)

        with zipfile.ZipFile(item["zip_path"], "r") as zip_ref:
            members = [m for m in zip_ref.infolist() if not m.is_dir()]
            if len(members) != 1:
                raise ValueError(f"Expected 1 file in the zip, found {len(members)}: {[m.filename for m in members][:5]}")
            with zip_ref.open(members[0], "r") as source, open(partial_path, "wb") as destination:
                shutil.copyfileobj(source, destination, length=UNZIP_CHUNK_SIZE)

        os.replace(partial_path, output_path)
        return item["zip_name"], "unzipped", os.path.getsize(output_path), None
    except Exception as error:
        if os.path.exists(partial_path):
            os.remove(partial_path)
        return item["zip_name"], "failed", 0, repr(error)


unzip_items = sorted(download_items, key=lambda i: i["size_mb"], reverse=True)

start = time.time()
sc.setJobDescription(f"Unzip {len(unzip_items):,} openFDA files")
unzip_results = sc.parallelize(unzip_items, len(unzip_items)).map(unzip_file).collect()
summarize("Unzip", unzip_results, start, "unzipped")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Step 4: Check the result
# 
# Confirms that every selected openFDA file has a zip and a JSON file in the lakehouse and that no `.partial` files were left behind, and reports the total size per folder.

# CELL ********************

missing_zips = [item["zip_name"] for item in download_items if not os.path.exists(item["zip_path"])]
missing_json = [os.path.basename(item["json_path"]) for item in download_items if not os.path.exists(item["json_path"])]
leftover_partials = [p.name for folder in (DOWNLOAD_DIRECTORY, UNZIP_DIRECTORY) for p in folder.glob("*.partial")]

zip_bytes = sum(os.path.getsize(item["zip_path"]) for item in download_items if os.path.exists(item["zip_path"]))
json_bytes = sum(os.path.getsize(item["json_path"]) for item in download_items if os.path.exists(item["json_path"]))

print(f"Files expected:     {len(download_items):,}")
print(f"Zip files present:  {len(download_items) - len(missing_zips):,}  ({zip_bytes / 1024**3:,.1f} GB)")
print(f"JSON files present: {len(download_items) - len(missing_json):,}  ({json_bytes / 1024**3:,.1f} GB)")
print(f"Leftover .partial:  {len(leftover_partials):,}")

problems = missing_zips + missing_json + leftover_partials
if problems:
    raise RuntimeError(f"Download is incomplete; first problems: {problems[:10]}")
print("\nAll files downloaded and unzipped.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
