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

# # FDA Drug Adverse Events: Load Silver from the JSON files
# 
# One-time load of the openFDA Drug Adverse Event (FAERS) bulk JSON files, which act as Bronze, into Silver Delta tables.
# 
# | Table | Grain |
# |---|---|
# | `silver.adverse_event_report` | One row per safety report, keeping the latest version after finalize |
# | `silver.adverse_event_drug` | One row per report × drug |
# | `silver.adverse_event_reaction` | One row per report × reaction |
# | `silver.drug_pharm_class` | One row per report × drug × pharmacologic class |
# | `silver.load_log` / `silver.dq_log` | Per-quarter load status and data-quality counts |
# 
# **How it runs**
# - A pruned explicit schema means only the fields kept in the plan are parsed. NDC, application number, SPL IDs and similar fields are never read.
# - Whole quarters are processed in batches of about `p_files_per_batch` files. Each multiline JSON file is parsed by one task, so a batch can use at most one core per file.
# - The session holds a fixed 8 executors (64 cores), so every batch's read runs fully in parallel instead of waiting for dynamic allocation to scale up.
# - Writes during the load skip V-Order and Optimize Write. The finalize `OPTIMIZE` rewrites every table once with V-Order and Z-ordering.
# - Tables are not partitioned; at a few GB, Z-ordering gives file skipping without the small-file overhead of partitions.
# - `adverse_event_report` records the source JSON file and the record's position in it (`_source_file`, `_source_record_index`) for lineage.
# - The notebook is restartable: quarters marked `Succeeded` in `load_log` are skipped, and partially loaded quarters are cleaned up before they are retried.
# - Finalize removes superseded report versions, then runs `OPTIMIZE`/`ZORDER` and `VACUUM`.
# - Silver tables contain no array, struct or map columns, so Direct Lake and the SQL analytics endpoint can read them.
# - Runs as the second step of the `pl_fda_one_time_build` pipeline, after `nb_fda_00_download_dataset`. Its default lakehouse is set when `nb_fda_install` installs it, so no lakehouse needs to be attached by hand.
# 
# See `medallion-architecture-plan.md` for the full design.


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

# PARAMETERS CELL ********************

p_quarters = ""            # comma-separated quarters to load, e.g. "2004q1,2025q4,all_other"; empty = every quarter found
p_files_per_batch = 128    # target JSON files per Spark batch (whole quarters are never split); ~2 read waves on 64 cores
p_finalize = True          # remove superseded report versions, then OPTIMIZE / VACUUM
p_reset = False            # drop all Silver tables first and reload from scratch
p_source_path = "Files/fda_ds_unzipped"
p_silver_schema = "silver"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import re
import uuid
import json
from datetime import datetime, timezone

from pyspark import StorageLevel
from pyspark.sql import functions as F, Window
from pyspark.sql.types import (StructType, StructField, StringType, LongType, ArrayType,
                               IntegerType, TimestampType, BooleanType)


def param(value, default):
    """Pipeline runs pass an empty parameter as None; treat None/blank as the default."""
    return default if value is None or str(value).strip() == "" else value


def as_bool(v, default):
    v = param(v, default)
    return v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "yes", "y")


p_quarters = str(param(p_quarters, ""))
p_files_per_batch = int(param(p_files_per_batch, 128))
p_finalize = as_bool(p_finalize, True)
p_reset = as_bool(p_reset, False)
p_source_path = str(param(p_source_path, "Files/fda_ds_unzipped"))
p_silver_schema = str(param(p_silver_schema, "silver"))

# Load phase is write-heavy: skip V-Order and Optimize Write; finalize OPTIMIZE applies V-Order once.
spark.conf.set("spark.sql.parquet.vorder.default", "false")
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "false")
spark.conf.set("spark.sql.adaptive.enabled", "true")

S = p_silver_schema
T_REPORT = f"{S}.adverse_event_report"
T_DRUG = f"{S}.adverse_event_drug"
T_REACTION = f"{S}.adverse_event_reaction"
T_PHARM = f"{S}.drug_pharm_class"
T_LOAD_LOG = f"{S}.load_log"
T_DQ_LOG = f"{S}.dq_log"
DATA_TABLES = [T_REPORT, T_DRUG, T_REACTION, T_PHARM]
RUN_ID = str(uuid.uuid4())

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {S}")
if p_reset:
    for t in DATA_TABLES + [T_LOAD_LOG, T_DQ_LOG]:
        spark.sql(f"DROP TABLE IF EXISTS {t}")
elif spark.catalog.tableExists(T_REPORT):
    # Tables built by an earlier layout (partitioned, no file lineage, old drug columns) can't be appended to.
    detail = spark.sql(f"DESCRIBE DETAIL {T_REPORT}").first()
    old_drug_layout = (spark.catalog.tableExists(T_DRUG)
                       and not {"drug_name_source", "unii_all"} <= set(spark.table(T_DRUG).columns))
    if detail.partitionColumns or "_source_file" not in spark.table(T_REPORT).columns or old_drug_layout:
        raise ValueError("Silver tables use an older table layout. Rerun with p_reset = True to rebuild Silver.")
print(f"run_id={RUN_ID} schema={S} finalize={p_finalize} reset={p_reset} files_per_batch={p_files_per_batch}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Pruned source schema
# The schema includes only the fields Silver keeps. Spark skips everything else while parsing.
# Excluded openFDA fields: `product_ndc`, `package_ndc`, `application_number`, `spl_id`, `spl_set_id`, `nui`, `unii`. `drugauthorizationnumb` is also excluded.

# CELL ********************

def _strings(*names):
    return [StructField(n, StringType()) for n in names]


OPENFDA_FIELDS = ["brand_name", "generic_name", "substance_name", "product_type",
                  "route", "rxcui", "unii", "pharm_class_epc", "pharm_class_moa", "pharm_class_pe", "pharm_class_cs"]

drug_schema = StructType(
    _strings("drugcharacterization", "medicinalproduct", "drugindication", "drugadministrationroute",
             "drugdosagetext", "drugdosageform", "actiondrug", "drugrecurreadministration",
             "drugstartdate", "drugenddate", "drugtreatmentduration", "drugtreatmentdurationunit")
    + [StructField("activesubstance", StructType(_strings("activesubstancename"))),
       StructField("openfda", StructType([StructField(n, ArrayType(StringType())) for n in OPENFDA_FIELDS]))])

reaction_schema = StructType(_strings("reactionmeddrapt", "reactionmeddraversionpt", "reactionoutcome"))

patient_schema = StructType(
    _strings("patientonsetage", "patientonsetageunit", "patientsex", "patientweight")
    + [StructField("patientdeath", StructType(_strings("patientdeathdate"))),
       StructField("reaction", ArrayType(reaction_schema)),
       StructField("drug", ArrayType(drug_schema))])

report_schema = StructType(
    _strings("safetyreportid", "safetyreportversion", "receivedate", "receiptdate", "transmissiondate",
             "reporttype", "serious", "seriousnessdeath", "seriousnesslifethreatening",
             "seriousnesshospitalization", "seriousnessdisabling", "seriousnesscongenitalanomali",
             "seriousnessother", "fulfillexpeditecriteria", "primarysourcecountry", "occurcountry",
             "companynumb", "duplicate")
    + [StructField("primarysource", StructType(_strings("qualification", "reportercountry"))),
       StructField("sender", StructType(_strings("sendertype", "senderorganization"))),
       # Object in older files, array of objects in newer ones: read as raw JSON text and parse both shapes.
       StructField("reportduplicate", StringType()),
       StructField("patient", patient_schema)])

file_schema = StructType([
    StructField("meta", StructType([StructField("results", StructType([StructField("total", LongType())]))])),
    StructField("results", ArrayType(report_schema)),
    StructField("_corrupt_record", StringType())])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Code lookups and cleansing helpers
# Code values come from the openFDA [`drugevent.yaml`](https://open.fda.gov/fields/drugevent.yaml) field definitions and ICH E2B(R2).

# CELL ********************

REPORT_TYPE = {"1": "Spontaneous", "2": "Report from study", "3": "Other", "4": "Not available to sender"}
QUALIFICATION = {"1": "Physician", "2": "Pharmacist", "3": "Other health professional", "4": "Lawyer",
                 "5": "Consumer or non-health professional"}
SENDER_TYPE = {"1": "Pharmaceutical company", "2": "Regulatory authority", "3": "Health professional",
               "4": "Regional pharmacovigilance center", "5": "WHO collaborating center", "6": "Other"}
SEX = {"0": "Unknown", "1": "Male", "2": "Female"}
AGE_UNIT_TO_YEARS = {"800": 10.0, "801": 1.0, "802": 1 / 12, "803": 1 / 52.1775, "804": 1 / 365.25, "805": 1 / 8766.0}
DRUG_ROLE = {"1": "Suspect", "2": "Concomitant", "3": "Interacting"}
ACTION_DRUG = {"1": "Drug withdrawn", "2": "Dose reduced", "3": "Dose increased", "4": "Dose not changed",
               "5": "Unknown", "6": "Not applicable"}
RECHALLENGE = {"1": "Yes - reaction recurred", "2": "No - reaction did not recur", "3": "Unknown"}
DURATION_UNIT_TO_DAYS = {"801": 365.25, "802": 30.4375, "803": 7.0, "804": 1.0, "805": 1 / 24, "806": 1 / 1440}
REACTION_OUTCOME = {"1": "Recovered/resolved", "2": "Recovering/resolving", "3": "Not recovered/not resolved",
                    "4": "Recovered with sequelae", "5": "Fatal", "6": "Unknown"}
ROUTE = {
    "001": "Auricular (otic)", "002": "Buccal", "003": "Cutaneous", "004": "Dental", "005": "Endocervical",
    "006": "Endosinusial", "007": "Endotracheal", "008": "Epidural", "009": "Extra-amniotic", "010": "Hemodialysis",
    "011": "Intra corpus cavernosum", "012": "Intra-amniotic", "013": "Intra-arterial", "014": "Intra-articular",
    "015": "Intra-uterine", "016": "Intracardiac", "017": "Intracavernous", "018": "Intracerebral",
    "019": "Intracervical", "020": "Intracisternal", "021": "Intracorneal", "022": "Intracoronary",
    "023": "Intradermal", "024": "Intradiscal (intraspinal)", "025": "Intrahepatic", "026": "Intralesional",
    "027": "Intralymphatic", "028": "Intramedullar (bone marrow)", "029": "Intrameningeal", "030": "Intramuscular",
    "031": "Intraocular", "032": "Intrapericardial", "033": "Intraperitoneal", "034": "Intrapleural",
    "035": "Intrasynovial", "036": "Intratumor", "037": "Intrathecal", "038": "Intrathoracic",
    "039": "Intratracheal", "040": "Intravenous bolus", "041": "Intravenous drip",
    "042": "Intravenous (not otherwise specified)", "043": "Intravesical", "044": "Iontophoresis", "045": "Nasal",
    "046": "Occlusive dressing technique", "047": "Ophthalmic", "048": "Oral", "049": "Oropharingeal",
    "050": "Other", "051": "Parenteral", "052": "Periarticular", "053": "Perineural", "054": "Rectal",
    "055": "Respiratory (inhalation)", "056": "Retrobulbar", "057": "Subconjunctival", "058": "Subcutaneous",
    "059": "Subdermal", "060": "Sublingual", "061": "Topical", "062": "Transdermal", "063": "Transmammary",
    "064": "Transplacental", "065": "Unknown", "066": "Urethral", "067": "Vaginal"}

NULL_TOKENS = ["", "UNK", "UNKNOWN", "N/A", "NA", "NULL", "NONE", "-"]


def lookup(mapping):
    return F.create_map([F.lit(x) for kv in mapping.items() for x in kv])


def code(c):
    return F.trim(c)


def decode(c, mapping, unknown="Unknown"):
    return F.coalesce(lookup(mapping)[code(c)], F.lit(unknown))


def is_unknown_code(c, mapping):
    """Raw code is present but not in the lookup (counted in dq_log)."""
    return code(c).isNotNull() & (code(c) != "") & lookup(mapping)[code(c)].isNull()


def clean_text(c):
    t = F.trim(F.regexp_replace(c, r"\s+", " "))
    return F.when(F.upper(t).isin(NULL_TOKENS), F.lit(None).cast("string")).otherwise(t)


def to_num(c):
    t = F.trim(c)
    return F.when(t.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), t.cast("double"))


def e2b_date(c):
    """Parse E2B dates (formats 102=yyyyMMdd, 610=yyyyMM, 602=yyyy); keep only 1900-01-01..today."""
    s = F.regexp_replace(F.trim(c), "[^0-9]", "")
    d = (F.when(F.length(s) == 8, F.try_to_timestamp(s, F.lit("yyyyMMdd")))
          .when(F.length(s) == 6, F.try_to_timestamp(s, F.lit("yyyyMM")))
          .when(F.length(s) == 4, F.try_to_timestamp(s, F.lit("yyyy")))).cast("date")
    return F.when((d >= F.lit("1900-01-01").cast("date")) & (d <= F.current_date()), d)


def bad_date(c):
    return F.trim(c).isNotNull() & (F.trim(c) != "") & e2b_date(c).isNull()


def safe_size(arr):
    return F.when(arr.isNull(), F.lit(0)).otherwise(F.size(arr))


def first_val(arr):
    return clean_text(F.try_element_at(arr, F.lit(1)))


def join_vals(arr):
    j = F.array_join(F.array_distinct(arr), "; ")
    return F.when(j != "", j)


def flag(c):
    return F.coalesce(F.trim(c) == "1", F.lit(False))


# Drug identification (see medallion-architecture-plan.md §3.5).
SALT_WORDS = ["HYDROCHLORIDE", "HCL", "SODIUM", "POTASSIUM", "CALCIUM", "MAGNESIUM",
              "BESYLATE", "CITRATE", "SULFATE", "MESYLATE"]
MINERALS = ["SODIUM", "POTASSIUM", "CALCIUM", "MAGNESIUM", "FERROUS", "ZINC"]
SALT_SUFFIX_RE = r"^(.+) (" + "|".join(SALT_WORDS) + r")$"
# Placeholder text reporters use instead of a drug name (UNSPECIFIED INGREDIENT, UNKNOWN DRUG, DRUG THERAPY NOS):
# a name that starts with UNKNOWN/UNSPECIFIED, or consists only of generic words. Qualifiers on a real drug
# (INSULIN NOS, MENTHOL, UNSPECIFIED FORM) are stripped first, so the drug name is kept.
QUALIFIER_SUFFIX_RE = r"(,?\s+UNSPECIFIED(\s+FORM)?|\s+NOS)$"
PLACEHOLDER_WORDS = ["UNKNOWN", "UNK", "UNSPECIFIED", "NOT", "SPECIFIED", "FURTHER", "NO", "NAME", "NOS", "OTHER",
                     "DRUG", "DRUGS", "MEDICATION", "MEDICATIONS", "MEDICINE", "MEDICINES", "INGREDIENT",
                     "INGREDIENTS", "PRODUCT", "PRODUCTS", "THERAPY", "THERAPIES", "AGENT", "AGENTS"]
PLACEHOLDER_RE = r"^(UNKNOWN|UNSPECIFIED)\b|^((" + "|".join(PLACEHOLDER_WORDS) + r")[\s,]*)+$"
UNKNOWN_DRUG = "UNKNOWN"


STRENGTH_UNITS = r"(%|MG|MCG|G|ML|L|IU|UNITS?|MEQ|MMOL)"


def normalize_drug_name(c):
    """Parentheses removed, split into ingredients, strengths, qualifiers and trailing salt words removed,
    placeholder ingredients dropped, ingredients sorted and joined with ' / '. Returns NULL when nothing is left."""
    text = F.regexp_replace(F.upper(clean_text(c)), r"\([^)]*\)", " ")
    parts = F.split(text, r"\s*(?:\\|/|\bAND\b)\s*")

    def trim_part(p):
        return F.trim(F.regexp_replace(F.regexp_replace(p, r"\s+", " "), r"[\s,.;:+\-]+$", ""))

    def remove_strength(p):
        # Numbers inside a name (5-FU, COVID-19, VITAMIN B12) are kept.
        p = F.regexp_replace(p, r"^[0-9.,]+\s*%\s*", "")                              # leading concentration: 0.9% ...
        p = F.regexp_replace(p, r"^[0-9.,]+\s*" + STRENGTH_UNITS + r"\b.*$", "")       # part that is only a strength: 0.8 ML PEN
        p = F.regexp_replace(p, r"^[0-9.,\s\-]+$", "")                                # part that is only a number: 00098801
        return F.regexp_replace(p, r"\s+[0-9].*$", "")                                # strength after a name: ASPIRIN 81 MG

    def clean_part(p):
        p = trim_part(remove_strength(F.trim(p)))
        p = trim_part(F.regexp_replace(p, QUALIFIER_SUFFIX_RE, ""))
        base = F.regexp_extract(p, SALT_SUFFIX_RE, 1)
        return F.when((base != "") & ~base.isin(MINERALS), base).otherwise(p)

    parts = F.filter(F.transform(parts, clean_part), lambda p: (p != "") & ~p.rlike(PLACEHOLDER_RE))
    name = F.array_join(F.array_sort(F.array_distinct(parts)), " / ")
    return F.when(name != "", name)


def shortest_value(arr):
    """Shortest non-empty value of an openFDA list (ties broken alphabetically)."""
    vals = F.filter(F.transform(arr, lambda x: F.upper(clean_text(x))), lambda x: x.isNotNull())
    ranked = F.array_sort(F.transform(vals, lambda x: F.struct(F.length(x).alias("len"), x.alias("val"))))
    return F.try_element_at(ranked, F.lit(1)).getField("val")


def duplicate_sources(raw):
    t = F.trim(raw)
    many = F.from_json(t, "array<struct<duplicatesource:string>>").getField("duplicatesource")
    one = F.from_json(t, "struct<duplicatesource:string>").getField("duplicatesource")
    return clean_text(F.when(t.startswith("["), F.array_join(F.array_distinct(many), "; ")).otherwise(one))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Discover files and plan batches

# CELL ********************

FILE_RE = re.compile(r"^(\d{4}q[1-4]|all_other)-drug-event-\d{4}-of-\d{4}\.json$")
files_by_quarter = {}
for f in notebookutils.fs.ls(p_source_path):
    m = FILE_RE.match(f.name)
    if m:
        files_by_quarter.setdefault(m.group(1), []).append(f.path)

if not files_by_quarter:
    raise ValueError(f"No openFDA JSON files found in {p_source_path}. Run nb_fda_00_download_dataset first.")
requested = [q.strip().lower() for q in p_quarters.split(",") if q.strip()]
unknown_quarters = sorted(set(requested) - set(files_by_quarter))
if unknown_quarters:
    raise ValueError(f"No source files found for quarters: {unknown_quarters}")
quarters = sorted(requested or files_by_quarter)

completed = set()
if spark.catalog.tableExists(T_LOAD_LOG):
    completed = {r.source_quarter for r in
                 spark.table(T_LOAD_LOG).where("status = 'Succeeded'").select("source_quarter").distinct().collect()}
todo = [q for q in quarters if q not in completed]

batches, current, n_files = [], [], 0
for q in todo:
    if current and n_files + len(files_by_quarter[q]) > p_files_per_batch:
        batches.append(current)
        current, n_files = [], 0
    current.append(q)
    n_files += len(files_by_quarter[q])
if current:
    batches.append(current)

print(f"{len(files_by_quarter)} quarters / {sum(map(len, files_by_quarter.values()))} files found")
print(f"{len(quarters)} requested, {len(quarters) - len(todo)} already loaded, {len(todo)} to load in {len(batches)} batches")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Transformations
# The transformations read the JSON, explode it into one row per report, and derive the four Silver tables. Columns prefixed `_dq_` count data-quality issues. They go to `dq_log` and are not written to the tables.

# CELL ********************

def read_reports(paths):
    raw = (spark.read.schema(file_schema)
           .option("multiLine", "true").option("mode", "PERMISSIVE")
           .option("columnNameOfCorruptRecord", "_corrupt_record")
           .json(paths))
    return (raw.select(F.col("_metadata.file_path").alias("_source_path"),
                       F.col("meta.results.total").alias("_meta_total"),
                       F.col("_corrupt_record").isNotNull().alias("_is_corrupt"),
                       F.posexplode_outer("results").alias("_pos", "r"))
               .withColumn("_source_file", F.regexp_extract("_source_path", r"([^/]+)$", 1))
               .withColumn("_source_quarter", F.regexp_extract("_source_file", r"^(\d{4}q[1-4]|all_other)-drug-event", 1))
               .withColumn("_report_uid", F.xxhash64("r.safetyreportid", "r.safetyreportversion", "_source_file", "_pos")))


def build_report(rep):
    r, p = F.col("r"), F.col("r.patient")
    age_years = to_num(p.patientonsetage) * lookup(AGE_UNIT_TO_YEARS)[code(p.patientonsetageunit)]
    age_ok = F.when((age_years >= 0) & (age_years <= 120), F.round(age_years, 2))
    weight = to_num(p.patientweight)
    weight_ok = F.when((weight > 0) & (weight <= 600), F.round(weight, 2))
    qual = code(r.primarysource.qualification)
    df = rep.select(
        F.trim(r.safetyreportid).alias("safetyreport_id"),
        F.when(F.trim(r.safetyreportversion).rlike(r"^[0-9]+$"), F.trim(r.safetyreportversion).cast("int")).alias("safetyreport_version"),
        clean_text(r.companynumb).alias("company_number"),
        e2b_date(r.receivedate).alias("receive_date"),
        # Kept within the first 32 columns so Delta collects file statistics for them (needed for Z-ordering).
        F.year(e2b_date(r.receivedate)).alias("receive_year"),
        F.when(e2b_date(r.receivedate).isNotNull(),
               F.concat(F.year(e2b_date(r.receivedate)), F.lit("-Q"), F.quarter(e2b_date(r.receivedate)))).alias("receive_quarter"),
        e2b_date(r.receiptdate).alias("receipt_date"),
        e2b_date(r.transmissiondate).alias("transmission_date"),
        decode(r.reporttype, REPORT_TYPE).alias("report_type"),
        flag(r.fulfillexpeditecriteria).alias("is_expedited"),
        flag(r.serious).alias("is_serious"),
        flag(r.seriousnessdeath).alias("is_death"),
        flag(r.seriousnesslifethreatening).alias("is_life_threatening"),
        flag(r.seriousnesshospitalization).alias("is_hospitalization"),
        flag(r.seriousnessdisabling).alias("is_disabling"),
        flag(r.seriousnesscongenitalanomali).alias("is_congenital_anomaly"),
        flag(r.seriousnessother).alias("is_other_serious"),
        F.upper(clean_text(r.primarysourcecountry)).alias("primary_source_country"),
        F.upper(clean_text(r.occurcountry)).alias("occur_country"),
        F.upper(clean_text(r.primarysource.reportercountry)).alias("reporter_country"),
        decode(r.primarysource.qualification, QUALIFICATION).alias("reporter_qualification"),
        F.coalesce(qual.isin("1", "2", "3"), F.lit(False)).alias("is_hcp_reported"),
        decode(r.sender.sendertype, SENDER_TYPE).alias("sender_type"),
        clean_text(r.sender.senderorganization).alias("sender_organization"),
        decode(p.patientsex, SEX).alias("patient_sex"),
        age_ok.alias("patient_age_years"),
        F.when(age_ok.isNull(), "Unknown").when(age_ok < 18, "0-17").when(age_ok < 45, "18-44")
         .when(age_ok < 65, "45-64").when(age_ok < 75, "65-74").otherwise("75+").alias("age_group"),
        weight_ok.alias("patient_weight_kg"),
        e2b_date(p.patientdeath.patientdeathdate).alias("patient_death_date"),
        flag(r.duplicate).alias("is_duplicate"),
        duplicate_sources(r.reportduplicate).alias("duplicate_source"),
        safe_size(p.drug).alias("drug_count"),
        F.when(p.drug.isNull(), F.lit(0))
         .otherwise(F.size(F.filter(p.drug, lambda d: F.trim(d.drugcharacterization) == "1"))).alias("suspect_drug_count"),
        safe_size(p.reaction).alias("reaction_count"),
        "_source_quarter",
        "_source_file",                                    # lineage: JSON file name in p_source_path
        F.col("_pos").alias("_source_record_index"),       # lineage: 0-based position in that file's results[]
        "_report_uid",
        # data-quality indicators (not persisted)
        bad_date(r.receivedate).alias("_dq_invalid_receive_date"),
        bad_date(r.receiptdate).alias("_dq_invalid_receipt_date"),
        (age_years.isNotNull() & age_ok.isNull()).alias("_dq_invalid_patient_age"),
        (weight.isNotNull() & weight_ok.isNull()).alias("_dq_invalid_patient_weight"),
        is_unknown_code(r.reporttype, REPORT_TYPE).alias("_dq_unknown_report_type_code"),
        is_unknown_code(r.primarysource.qualification, QUALIFICATION).alias("_dq_unknown_qualification_code"),
    )
    return df.withColumn("_loaded_ts", F.current_timestamp())


def explode_drugs(rep):
    return rep.select(F.trim("r.safetyreportid").alias("safetyreport_id"), "_report_uid", "_source_quarter",
                      F.posexplode("r.patient.drug").alias("_seq", "d"))


DRUG_COLUMNS = ["safetyreport_id", "drug_seq", "drug_role", "medicinal_product", "medicinal_product_std",
                "active_substance", "drug_name", "drug_name_source", "brand_names_all", "generic_names_all",
                "substance_names_all", "rxcui_all", "unii_all", "product_type", "drug_indication", "route", "dosage_text",
                "dosage_form", "action_taken", "rechallenge", "drug_start_date", "drug_end_date",
                "treatment_duration_days", "is_openfda_matched", "_source_quarter", "_report_uid",
                "_dq_unknown_drug_role_code", "_dq_unknown_route_code"]


def build_drug(drugs_raw):
    d, o = F.col("d"), F.col("d.openfda")
    product_std = F.regexp_replace(F.upper(clean_text(d.medicinalproduct)), r"[\s.]+$", "")
    active = F.upper(clean_text(d.activesubstance.activesubstancename))
    dur = to_num(d.drugtreatmentduration) * lookup(DURATION_UNIT_TO_DAYS)[code(d.drugtreatmentdurationunit)]
    route_code = F.lpad(code(d.drugadministrationroute), 3, "0")
    df = drugs_raw.select(
        "safetyreport_id",
        (F.col("_seq") + 1).alias("drug_seq"),
        decode(d.drugcharacterization, DRUG_ROLE).alias("drug_role"),
        clean_text(d.medicinalproduct).alias("medicinal_product"),
        product_std.alias("medicinal_product_std"),
        active.alias("active_substance"),
        # Name candidates, in order of preference (plan §3.5 step A), each normalized (step B).
        # openFDA: the generic name that matches the reported active substance, else the shortest generic name.
        normalize_drug_name(shortest_value(o.generic_name)).alias("_name_shortest"),
        F.filter(F.transform(o.generic_name, normalize_drug_name), lambda x: x.isNotNull()).alias("_generic_norms"),
        normalize_drug_name(d.activesubstance.activesubstancename).alias("_name_substance"),
        normalize_drug_name(d.medicinalproduct).alias("_name_product"),
        join_vals(o.brand_name).alias("brand_names_all"),
        join_vals(o.generic_name).alias("generic_names_all"),
        join_vals(o.substance_name).alias("substance_names_all"),
        join_vals(o.rxcui).alias("rxcui_all"),
        join_vals(o.unii).alias("unii_all"),
        first_val(o.product_type).alias("product_type"),
        clean_text(d.drugindication).alias("drug_indication"),
        F.when(d.drugadministrationroute.isNull(), F.lit(None).cast("string"))
         .otherwise(F.coalesce(lookup(ROUTE)[route_code], F.lit("Unknown"))).alias("route"),
        clean_text(d.drugdosagetext).alias("dosage_text"),
        clean_text(d.drugdosageform).alias("dosage_form"),
        F.when(d.actiondrug.isNull(), F.lit(None).cast("string")).otherwise(decode(d.actiondrug, ACTION_DRUG)).alias("action_taken"),
        F.when(d.drugrecurreadministration.isNull(), F.lit(None).cast("string"))
         .otherwise(decode(d.drugrecurreadministration, RECHALLENGE)).alias("rechallenge"),
        e2b_date(d.drugstartdate).alias("drug_start_date"),
        e2b_date(d.drugenddate).alias("drug_end_date"),
        F.when((dur >= 0) & (dur <= 36525), F.round(dur, 2)).alias("treatment_duration_days"),
        ((safe_size(o.generic_name) + safe_size(o.brand_name)) > 0).alias("is_openfda_matched"),
        "_source_quarter", "_report_uid",
        is_unknown_code(d.drugcharacterization, DRUG_ROLE).alias("_dq_unknown_drug_role_code"),
        (d.drugadministrationroute.isNotNull() & lookup(ROUTE)[route_code].isNull()).alias("_dq_unknown_route_code"),
    )
    # Use the generic name that matches the reported substance, unless it is just the shortest name plus
    # extra words such as an unlisted salt (CLOPIDOGREL BISULFATE vs CLOPIDOGREL); combinations always win.
    matched = F.when(F.array_contains("_generic_norms", F.col("_name_substance")), F.col("_name_substance"))
    just_longer = (matched.startswith(F.concat(F.col("_name_shortest"), F.lit(" "))) & ~matched.contains(" / "))
    df = (df.withColumn("_name_openfda", F.when(matched.isNotNull() & ~just_longer, matched).otherwise(F.col("_name_shortest")))
            .withColumn("drug_name", F.coalesce("_name_openfda", "_name_substance", "_name_product", F.lit(UNKNOWN_DRUG)))
            .withColumn("drug_name_source",
                        F.when(F.col("_name_openfda").isNotNull(), "openfda_generic")
                         .when(F.col("_name_substance").isNotNull(), "reported_substance")
                         .when(F.col("_name_product").isNotNull(), "product_text")
                         .otherwise("none")))
    # Fixed column order keeps drug_name within the first 32 columns (Delta stats, needed for Z-ordering).
    return df.select(*DRUG_COLUMNS)


def build_pharm_class(drugs_raw):
    classes = F.array(*[F.struct(F.lit(t).alias("class_type"), F.col(f"d.openfda.pharm_class_{t.lower()}").alias("vals"))
                        for t in ["EPC", "MOA", "PE", "CS"]])
    return (drugs_raw.select("safetyreport_id", (F.col("_seq") + 1).alias("drug_seq"), "_source_quarter", "_report_uid",
                             F.explode(classes).alias("c"))
            .select("safetyreport_id", "drug_seq", F.col("c.class_type").alias("class_type"),
                    F.explode("c.vals").alias("pharm_class"), "_source_quarter", "_report_uid")
            .withColumn("pharm_class", clean_text(F.col("pharm_class")))
            .where("pharm_class IS NOT NULL")
            .dropDuplicates(["_report_uid", "drug_seq", "class_type", "pharm_class"]))


def build_reaction(rep):
    x = F.col("x")
    return (rep.select(F.trim("r.safetyreportid").alias("safetyreport_id"), "_report_uid", "_source_quarter",
                       F.posexplode("r.patient.reaction").alias("_seq", "x"))
            .select("safetyreport_id",
                    (F.col("_seq") + 1).alias("reaction_seq"),
                    clean_text(x.reactionmeddrapt).alias("reaction_pt"),
                    clean_text(x.reactionmeddraversionpt).alias("meddra_version"),
                    F.when(x.reactionoutcome.isNull(), F.lit(None).cast("string"))
                     .otherwise(decode(x.reactionoutcome, REACTION_OUTCOME)).alias("reaction_outcome"),
                    F.coalesce(code(x.reactionoutcome) == "5", F.lit(False)).alias("is_fatal_outcome"),
                    "_source_quarter", "_report_uid",
                    is_unknown_code(x.reactionoutcome, REACTION_OUTCOME).alias("_dq_unknown_reaction_outcome_code")))


def dq_counts(df, table_name):
    """Sum every _dq_* flag per quarter and return long-format rows."""
    dq_cols = [c for c in df.columns if c.startswith("_dq_")]
    if not dq_cols:
        return []
    agg = df.groupBy("_source_quarter").agg(*[F.sum(F.col(c).cast("long")).alias(c) for c in dq_cols]).collect()
    return [(row["_source_quarter"], table_name, c[4:], int(row[c] or 0)) for row in agg for c in dq_cols]


def persisted(df):
    return df.drop(*[c for c in df.columns if c.startswith("_dq_")])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load batches
# Each batch writes the four Silver tables, then records counts in `load_log` and data-quality counts in `dq_log`. A failed batch can be rerun safely.

# CELL ********************

LOAD_LOG_SCHEMA = StructType([
    StructField("source_quarter", StringType()), StructField("file_count", IntegerType()),
    StructField("meta_total", LongType()), StructField("reports_in_files", LongType()),
    StructField("report_rows", LongType()), StructField("drug_rows", LongType()),
    StructField("reaction_rows", LongType()), StructField("pharm_class_rows", LongType()),
    StructField("corrupt_files", LongType()), StructField("count_matches", BooleanType()),
    StructField("status", StringType()), StructField("run_id", StringType()),
    StructField("started_ts", TimestampType()), StructField("ended_ts", TimestampType())])
DQ_LOG_SCHEMA = StructType([
    StructField("source_quarter", StringType()), StructField("table_name", StringType()),
    StructField("rule", StringType()), StructField("row_count", LongType()),
    StructField("run_id", StringType()), StructField("logged_ts", TimestampType())])


def append(df, table):
    df.write.format("delta").mode("append").saveAsTable(table)


def counts_by_quarter(df):
    return {r["_source_quarter"]: r["count"] for r in df.groupBy("_source_quarter").count().collect()}


# About 2 tasks per executor core (8 executors x 8 cores from %%configure); executors may still be starting here.
N_PARTITIONS = max(128, 2 * spark.sparkContext.defaultParallelism)
print(f"post-read partitions per batch: {N_PARTITIONS}")


for i, batch in enumerate(batches, start=1):
    started = datetime.now(timezone.utc)
    paths = [p for q in batch for p in files_by_quarter[q]]
    print(f"[{started:%H:%M:%S}] batch {i}/{len(batches)}: {batch} ({len(paths)} files)")

    # Each multiline JSON file is one partition, which would cap every later stage at one task per file.
    # Spread the parsed reports across all cores once, then reuse the cached result for every table.
    rep = read_reports(paths).repartition(N_PARTITIONS).persist(StorageLevel.MEMORY_AND_DISK)
    stats = {r["_source_quarter"]: r for r in rep.groupBy("_source_quarter").agg(
        F.max("_meta_total").alias("meta_total"),
        F.sum(F.col("r").isNotNull().cast("long")).alias("reports_in_files"),
        F.countDistinct(F.when(F.col("_is_corrupt"), F.col("_source_file"))).alias("corrupt_files"),
        F.sum((F.col("r").isNotNull() & (F.coalesce(F.trim("r.safetyreportid"), F.lit("")) == "")).cast("long"))
         .alias("missing_safetyreportid")).collect()}

    valid = rep.where(F.coalesce(F.trim("r.safetyreportid"), F.lit("")) != "")
    report_df = build_report(valid)
    drugs_raw = explode_drugs(valid)
    drug_df = build_drug(drugs_raw)
    pharm_df = build_pharm_class(drugs_raw)
    reaction_df = build_reaction(valid)

    # Remove rows left by an earlier failed attempt of these quarters, then append.
    quarter_list = ", ".join(f"'{q}'" for q in batch)
    for t in DATA_TABLES:
        if spark.catalog.tableExists(t):
            spark.sql(f"DELETE FROM {t} WHERE _source_quarter IN ({quarter_list})")
    append(persisted(report_df), T_REPORT)
    append(persisted(drug_df), T_DRUG)
    append(persisted(reaction_df), T_REACTION)
    append(pharm_df, T_PHARM)

    n_report, n_drug = counts_by_quarter(report_df), counts_by_quarter(drug_df)
    n_reaction, n_pharm = counts_by_quarter(reaction_df), counts_by_quarter(pharm_df)
    ended = datetime.now(timezone.utc)

    dq_rows = (dq_counts(report_df, T_REPORT) + dq_counts(drug_df, T_DRUG) + dq_counts(reaction_df, T_REACTION)
               + [(q, T_REPORT, "missing_safetyreportid", int(s["missing_safetyreportid"] or 0)) for q, s in stats.items()]
               + [(q, "source_files", "corrupt_files", int(s["corrupt_files"] or 0)) for q, s in stats.items()])
    spark.createDataFrame([(*row, RUN_ID, ended) for row in dq_rows], DQ_LOG_SCHEMA) \
        .write.format("delta").mode("append").saveAsTable(T_DQ_LOG)

    log_rows = []
    for q in batch:
        s = stats.get(q)
        meta_total = int(s["meta_total"]) if s and s["meta_total"] is not None else None
        in_files = int(s["reports_in_files"] or 0) if s else 0
        log_rows.append((q, len(files_by_quarter[q]), meta_total, in_files,
                         int(n_report.get(q, 0)), int(n_drug.get(q, 0)), int(n_reaction.get(q, 0)), int(n_pharm.get(q, 0)),
                         int(s["corrupt_files"] or 0) if s else 0, meta_total == in_files,
                         "Succeeded", RUN_ID, started, ended))
    spark.createDataFrame(log_rows, LOAD_LOG_SCHEMA).write.format("delta").mode("append").saveAsTable(T_LOAD_LOG)

    rep.unpersist()
    for row in log_rows:
        print(f"    {row[0]}: reports={row[4]:,} (meta_total={row[2]}, match={row[9]}) drugs={row[5]:,} "
              f"reactions={row[6]:,} pharm_classes={row[7]:,} corrupt_files={row[8]}")
    print(f"    batch finished in {(ended - started).total_seconds() / 60:.1f} min")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Finalize: keep the latest report version, then optimize
# Reports are ranked by highest `safetyreport_version`, then latest `receipt_date`, then latest source quarter. Superseded versions and their child rows are deleted.

# CELL ********************

superseded_count = None
if p_finalize and spark.catalog.tableExists(T_REPORT):
    # 'all_other' (openFDA reports outside the quarterly files) ranks below every real quarter.
    quarter_rank = F.when(F.col("_source_quarter") == "all_other", F.lit("0000q0")).otherwise(F.col("_source_quarter"))
    w = Window.partitionBy("safetyreport_id").orderBy(
        F.col("safetyreport_version").desc_nulls_last(), F.col("receipt_date").desc_nulls_last(),
        quarter_rank.desc(), F.col("_report_uid").desc())
    T_TMP = f"{S}._tmp_superseded_reports"
    (spark.table(T_REPORT)
        .select("safetyreport_id", "safetyreport_version", "receipt_date", "_source_quarter", "_report_uid")
        .withColumn("rn", F.row_number().over(w)).where("rn > 1").select("_report_uid")
        .write.format("delta").mode("overwrite").saveAsTable(T_TMP))
    superseded_count = spark.table(T_TMP).count()
    print(f"superseded report versions to remove: {superseded_count:,}")
    if superseded_count:
        for t in DATA_TABLES:
            spark.sql(f"MERGE INTO {t} AS t USING {T_TMP} AS s ON t._report_uid = s._report_uid WHEN MATCHED THEN DELETE")
    spark.sql(f"DROP TABLE IF EXISTS {T_TMP}")
    spark.createDataFrame([("ALL", T_REPORT, "superseded_versions_removed", int(superseded_count), RUN_ID,
                            datetime.now(timezone.utc))], DQ_LOG_SCHEMA) \
        .write.format("delta").mode("append").saveAsTable(T_DQ_LOG)

    # Rewrite each table once, read-optimized: V-Order plus Z-ordering on the most common filter and join columns.
    spark.conf.set("spark.sql.parquet.vorder.default", "true")
    spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
    for t, zcols in [(T_REPORT, "receive_year, safetyreport_id"), (T_DRUG, "drug_name, safetyreport_id"),
                     (T_REACTION, "reaction_pt, safetyreport_id"), (T_PHARM, "pharm_class, safetyreport_id")]:
        spark.sql(f"OPTIMIZE {t} ZORDER BY ({zcols})")
        spark.sql(f"VACUUM {t}")
        print(f"optimized {t}")
    for t in (T_LOAD_LOG, T_DQ_LOG):
        spark.sql(f"OPTIMIZE {t}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Validate

# CELL ********************

summary = {"run_id": RUN_ID, "batches_loaded": len(batches), "superseded_removed": superseded_count}
if spark.catalog.tableExists(T_REPORT):
    rpt = spark.table(T_REPORT)
    counts = rpt.agg(F.count("*").alias("rows"), F.countDistinct("safetyreport_id").alias("ids")).first()
    summary.update({
        "report_rows": counts["rows"], "distinct_report_ids": counts["ids"],
        "drug_rows": spark.table(T_DRUG).count(), "reaction_rows": spark.table(T_REACTION).count(),
        "pharm_class_rows": spark.table(T_PHARM).count(),
        "orphan_drug_rows": spark.table(T_DRUG).join(rpt, "_report_uid", "left_anti").count(),
        "orphan_reaction_rows": spark.table(T_REACTION).join(rpt, "_report_uid", "left_anti").count(),
        "reports_without_source_file": rpt.where("_source_file IS NULL OR _source_file = ''").count(),
        "distinct_drug_names": spark.table(T_DRUG).select("drug_name").distinct().count(),
        "drug_rows_by_name_source": {r.drug_name_source: r["count"] for r in
                                     spark.table(T_DRUG).groupBy("drug_name_source").count().collect()},
        "quarters_with_count_mismatch": [r.source_quarter for r in spark.table(T_LOAD_LOG)
                                         .where("status = 'Succeeded' AND NOT count_matches").select("source_quarter").collect()],
        # A corrupt file still loads, but at least one field did not match the schema and was set to NULL.
        "quarters_with_corrupt_files": [r.source_quarter for r in spark.table(T_LOAD_LOG)
                                        .where("status = 'Succeeded' AND corrupt_files > 0").select("source_quarter").collect()],
    })
    print(json.dumps(summary, indent=2, default=str))
    if p_finalize and counts["rows"] != counts["ids"]:
        raise AssertionError("Duplicate safetyreport_id values remain after finalize")
    if summary["orphan_drug_rows"] or summary["orphan_reaction_rows"]:
        raise AssertionError("Child rows without a parent report found")
    if summary["reports_without_source_file"]:
        raise AssertionError("Reports without source-file lineage found")
    print("Top 25 suspect drugs by rows (spot-check for leftover splits):")
    (spark.table(T_DRUG).where("drug_role = 'Suspect'").groupBy("drug_name").count()
        .orderBy(F.desc("count")).show(25, truncate=False))
    spark.table(T_LOAD_LOG).orderBy("source_quarter").show(200, truncate=False)

notebookutils.notebook.exit(json.dumps(summary, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
