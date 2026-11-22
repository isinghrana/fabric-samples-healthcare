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

# # FDA Drug Adverse Events: Build Gold
# 
# Builds the Gold star schema and the pre-computed insight tables from Silver.
# 
# | Table | Grain |
# |---|---|
# | `gold.dim_date`, `gold.dim_drug`, `gold.dim_reaction`, `gold.dim_country`, `gold.dim_pharm_class` | Dimensions |
# | `gold.bridge_drug_pharm_class` | Drug × pharmacologic class |
# | `gold.fact_report` | One row per report |
# | `gold.fact_report_drug` | One row per report × drug |
# | `gold.fact_report_reaction` | One row per report × reaction |
# | `gold.agg_report_trend_monthly` | Month × country × report type × reporter qualification |
# | `gold.agg_drug_summary` | Suspect drug × period |
# | `gold.agg_drug_reaction` | Suspect drug × reaction × period (reports ≥ `p_min_cases`) |
# | `gold.agg_drug_reaction_signal` | Disproportionality metrics: PRR, ROR, chi-square and an Evans signal flag |
# 
# **Design notes**
# - `dim_drug` has one row per rule-based `drug_name` from Silver (plan §3.5). Manufacturer and RxCUI columns are not included.
# - The dataset disclaimer is documented in the plan (§8), not stored as a table.
# - Surrogate keys are deterministic `xxhash64` values of the natural key, so facts get their keys without joining to dimensions.
# - Drugs and reactions connect only through the report. FAERS does not link a specific drug to a specific reaction.
# - Gold tables contain no array, struct or map columns, for Direct Lake, the SQL analytics endpoint, Data Agent and Rayfin.
# - FAERS reports are unvalidated. Signals are for generating hypotheses and do not establish causality or incidence.
# - The session holds a fixed 8 executors (64 cores) so the large joins and aggregations don't wait on dynamic allocation.
# - Runs as the last step of the `pl_fda_one_time_build` pipeline. Its default lakehouse is set when `nb_fda_install` installs it, so no lakehouse needs to be attached by hand.

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

p_silver_schema = "silver"
p_gold_schema = "gold"
p_min_cases = 3            # minimum co-reported cases (a) for agg_drug_reaction and signals
p_recent_years = 3         # length of the recent-period window, ending at the latest receive date

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
from datetime import date

from pyspark import StorageLevel
from pyspark.sql import functions as F, Window

def param(value, default):
    """Pipeline runs pass an empty parameter as None; treat None/blank as the default."""
    return default if value is None or str(value).strip() == "" else value


p_silver_schema = str(param(p_silver_schema, "silver"))
p_gold_schema = str(param(p_gold_schema, "gold"))
p_min_cases = int(param(p_min_cases, 3))
p_recent_years = int(param(p_recent_years, 3))
RECENT = f"last_{p_recent_years}_years"

spark.conf.set("spark.sql.parquet.vorder.default", "true")
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.databricks.delta.optimizeWrite.binSize", "1g")
spark.conf.set("spark.sql.adaptive.enabled", "true")

S, G = p_silver_schema, p_gold_schema
missing_silver = [t for t in ("adverse_event_report", "adverse_event_drug", "adverse_event_reaction", "drug_pharm_class")
                  if not spark.catalog.tableExists(f"{S}.{t}")]
if missing_silver:
    raise ValueError(f"Silver tables not found in schema '{S}': {missing_silver}. Run nb_fda_01_silver_load first.")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {G}")

report = spark.table(f"{S}.adverse_event_report")
drug = spark.table(f"{S}.adverse_event_drug")
reaction = spark.table(f"{S}.adverse_event_reaction")
pharm = spark.table(f"{S}.drug_pharm_class")

row_counts = {}


def hkey(*cols):
    return F.xxhash64(*cols)


def save(df, name, zorder=None):
    table = f"{G}.{name}"
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    spark.sql(f"OPTIMIZE {table}" + (f" ZORDER BY ({', '.join(zorder)})" if zorder else ""))
    row_counts[name] = spark.table(table).count()
    print(f"{table}: {row_counts[name]:,} rows")


def most_frequent(df, key, col, alias=None):
    """Most frequent non-null value of `col` per `key` (ties broken alphabetically)."""
    w = Window.partitionBy(key).orderBy(F.col("_n").desc(), F.col(col))
    return (df.where(F.col(col).isNotNull()).groupBy(key, col).agg(F.count("*").alias("_n"))
              .withColumn("_rk", F.row_number().over(w)).where("_rk = 1")
              .select(key, F.col(col).alias(alias or col)))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Dimensions

# CELL ********************

bounds = report.agg(F.min("receive_date").alias("lo"), F.max("receive_date").alias("hi")).first()
max_receive_date = bounds["hi"]
start = min(bounds["lo"] or date(2004, 1, 1), date(2004, 1, 1))
end = date((max_receive_date or date.today()).year, 12, 31)

dim_date = (spark.sql(f"SELECT explode(sequence(DATE'{start}', DATE'{end}', INTERVAL 1 DAY)) AS date")
            .select(F.date_format("date", "yyyyMMdd").cast("int").alias("date_key"), "date",
                    F.year("date").alias("year"), F.quarter("date").alias("quarter"), F.month("date").alias("month"),
                    F.date_format("date", "MMMM").alias("month_name"), F.date_format("date", "MMM").alias("month_short"),
                    F.concat(F.year("date"), F.lit("-Q"), F.quarter("date")).alias("year_quarter"),
                    F.date_format("date", "yyyy-MM").alias("year_month"),
                    F.trunc("date", "month").alias("month_start_date"),
                    F.date_format("date", "EEEE").alias("day_of_week")))
save(dim_date, "dim_date")

# Drug dimension: one row per drug_name (rule-based identity, plan §3.5) with its most common descriptive attributes.
brands = (drug.select("drug_name", F.explode(F.split("brand_names_all", "; ")).alias("brand"))
          .where("brand IS NOT NULL AND brand <> ''"))
top_brands = (brands.groupBy("drug_name", "brand").count()
              .withColumn("_rk", F.row_number().over(Window.partitionBy("drug_name").orderBy(F.col("count").desc(), "brand")))
              .where("_rk <= 10").groupBy("drug_name")
              .agg(F.array_join(F.sort_array(F.collect_list(F.struct(F.col("_rk"), F.col("brand")))).brand, "; ")
                   .alias("brand_names")))
epc = (pharm.where("class_type = 'EPC'").join(drug.select("_report_uid", "drug_seq", "drug_name"), ["_report_uid", "drug_seq"])
       .select("drug_name", "pharm_class"))
dim_drug = (drug.select("drug_name").distinct()
            .join(top_brands, "drug_name", "left")
            .join(most_frequent(drug.select("drug_name", "product_type"), "drug_name", "product_type"), "drug_name", "left")
            .join(most_frequent(epc, "drug_name", "pharm_class", "pharm_class_epc"), "drug_name", "left")
            .select(hkey("drug_name").alias("drug_key"), "drug_name", "brand_names", "product_type", "pharm_class_epc",
                    (F.col("drug_name") == "UNKNOWN").alias("is_unknown")))
save(dim_drug, "dim_drug", zorder=["drug_name"])

dim_pharm_class = (pharm.select("class_type", "pharm_class").distinct()
                   .select(hkey("class_type", "pharm_class").alias("pharm_class_key"), "pharm_class", "class_type"))
save(dim_pharm_class, "dim_pharm_class")

bridge = (pharm.join(drug.select("_report_uid", "drug_seq", "drug_name"), ["_report_uid", "drug_seq"])
          .select(hkey("drug_name").alias("drug_key"), hkey("class_type", "pharm_class").alias("pharm_class_key"))
          .distinct())
save(bridge, "bridge_drug_pharm_class")

# Reaction dimension: case-insensitive MedDRA PT, displayed with its most common casing.
reaction_norm = reaction.select(F.coalesce(F.lower("reaction_pt"), F.lit("unknown")).alias("reaction_norm"),
                                F.coalesce("reaction_pt", F.lit("Unknown")).alias("reaction_pt"))
dim_reaction = (most_frequent(reaction_norm, "reaction_norm", "reaction_pt")
                .select(hkey("reaction_norm").alias("reaction_key"), "reaction_pt"))
save(dim_reaction, "dim_reaction", zorder=["reaction_pt"])

# Country dimension: ISO-2 codes resolved to English names on the driver (JVM Locale); other values kept as-is.
country_expr = F.coalesce("occur_country", "primary_source_country", F.lit("UNKNOWN"))
codes = [r[0] for r in report.select(country_expr.alias("c")).distinct().collect()]
Locale = spark._jvm.java.util.Locale


def country_name(c):
    if c == "UNKNOWN":
        return "Unknown"
    if len(c) == 2:
        name = Locale("", c).getDisplayCountry(Locale.ENGLISH)
        if name and name.upper() != c:
            return name
    return c.title()


dim_country = (spark.createDataFrame([(c, country_name(c)) for c in codes], "country_code string, country_name string")
               .select(hkey("country_code").alias("country_key"), "country_code", "country_name"))
save(dim_country, "dim_country")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Facts

# CELL ********************

fatal_reports = reaction.groupBy("_report_uid").agg(F.max(F.col("is_fatal_outcome").cast("int")).cast("boolean").alias("has_fatal_reaction"))

fact_report = (report.join(fatal_reports, "_report_uid", "left")
               .select(hkey("safetyreport_id").alias("report_key"), "safetyreport_id",
                       F.date_format("receive_date", "yyyyMMdd").cast("int").alias("receive_date_key"), "receive_date",
                       hkey(country_expr).alias("occur_country_key"),
                       "report_type", "reporter_qualification", "is_hcp_reported", "sender_type",
                       "patient_sex", "age_group", "patient_age_years", "patient_weight_kg",
                       "is_serious", "is_death", "is_life_threatening", "is_hospitalization", "is_disabling",
                       "is_congenital_anomaly", "is_other_serious", "is_expedited",
                       F.coalesce("has_fatal_reaction", F.lit(False)).alias("has_fatal_reaction"),
                       "drug_count", "suspect_drug_count", "reaction_count"))
save(fact_report, "fact_report", zorder=["receive_date_key"])

fact_report_drug = drug.select(hkey("safetyreport_id").alias("report_key"), hkey("drug_name").alias("drug_key"),
                               "drug_seq", "drug_role", (F.col("drug_role") == "Suspect").alias("is_suspect"),
                               "route", "action_taken", "rechallenge", "drug_indication")
save(fact_report_drug, "fact_report_drug", zorder=["drug_key"])

fact_report_reaction = reaction.select(hkey("safetyreport_id").alias("report_key"),
                                       hkey(F.coalesce(F.lower("reaction_pt"), F.lit("unknown"))).alias("reaction_key"),
                                       "reaction_seq", "reaction_outcome", "is_fatal_outcome")
save(fact_report_reaction, "fact_report_reaction", zorder=["reaction_key"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Insight tables
# Periods: `all_time`, plus the last `p_recent_years` years ending at the latest receive date in the data.

# CELL ********************

fr = spark.table(f"{G}.fact_report")
frd = spark.table(f"{G}.fact_report_drug")
frr = spark.table(f"{G}.fact_report_reaction")
d_drug = spark.table(f"{G}.dim_drug").select("drug_key", "drug_name")
d_reaction = spark.table(f"{G}.dim_reaction").select("reaction_key", "reaction_pt")
# UNKNOWN (no identifiable drug) stays in the facts but is left out of drug-level summaries and signals.
known_drugs = spark.table(f"{G}.dim_drug").where("NOT is_unknown").select("drug_key")

recent_start = F.add_months(F.lit(max_receive_date), -12 * p_recent_years)
report_periods = fr.withColumn("period", F.explode(
    F.when(F.col("receive_date") > recent_start, F.array(F.lit("all_time"), F.lit(RECENT)))
     .otherwise(F.array(F.lit("all_time")))))

trend = (fr.groupBy(F.trunc("receive_date", "month").alias("month_start_date"), "occur_country_key",
                    "report_type", "reporter_qualification")
           .agg(F.count("*").alias("reports"),
                *[F.sum(F.col(c).cast("long")).alias(n) for c, n in [
                    ("is_serious", "serious_reports"), ("is_death", "death_reports"),
                    ("is_hospitalization", "hospitalization_reports"), ("is_life_threatening", "life_threatening_reports"),
                    ("has_fatal_reaction", "fatal_outcome_reports"), ("is_hcp_reported", "hcp_reported_reports")]])
           .withColumn("month_date_key", F.date_format("month_start_date", "yyyyMMdd").cast("int")))
save(trend, "agg_report_trend_monthly", zorder=["month_start_date"])

suspect = frd.where("is_suspect").join(known_drugs, "drug_key", "left_semi").select("report_key", "drug_key").distinct()
suspect_p = suspect.join(report_periods.select("report_key", "period", "is_serious", "is_death", "is_hospitalization",
                                               "is_life_threatening", "has_fatal_reaction", "is_hcp_reported",
                                               "patient_sex", "age_group", "receive_date"), "report_key")
suspect_p = suspect_p.persist(StorageLevel.MEMORY_AND_DISK)

top_indication = most_frequent(
    frd.where("is_suspect AND drug_indication IS NOT NULL AND lower(drug_indication) <> 'product used for unknown indication'")
       .select("drug_key", "drug_indication"), "drug_key", "drug_indication", "top_indication")

cnt = lambda cond: F.sum(F.when(cond, 1).otherwise(0)).alias  # noqa: E731
drug_summary = (suspect_p.groupBy("drug_key", "period").agg(
                    F.count("*").alias("reports"),
                    cnt(F.col("is_serious"))("serious_reports"), cnt(F.col("is_death"))("death_reports"),
                    cnt(F.col("is_hospitalization"))("hospitalization_reports"),
                    cnt(F.col("is_life_threatening"))("life_threatening_reports"),
                    cnt(F.col("has_fatal_reaction"))("fatal_outcome_reports"),
                    cnt(F.col("is_hcp_reported"))("hcp_reported_reports"),
                    cnt(F.col("patient_sex") == "Female")("female_reports"),
                    cnt(F.col("patient_sex") == "Male")("male_reports"),
                    cnt(F.col("age_group") == "0-17")("age_0_17_reports"),
                    cnt(F.col("age_group") == "18-44")("age_18_44_reports"),
                    cnt(F.col("age_group") == "45-64")("age_45_64_reports"),
                    cnt(F.col("age_group") == "65-74")("age_65_74_reports"),
                    cnt(F.col("age_group") == "75+")("age_75_plus_reports"),
                    cnt(F.col("age_group") == "Unknown")("age_unknown_reports"),
                    F.min("receive_date").alias("first_receive_date"), F.max("receive_date").alias("last_receive_date"))
                .join(d_drug, "drug_key").join(top_indication, "drug_key", "left")
                .withColumn("serious_pct", F.round(F.col("serious_reports") / F.col("reports"), 4)))
save(drug_summary, "agg_drug_summary", zorder=["drug_name"])

# Report-level co-occurrence of suspect drug and reaction (distinct reports per pair and period).
reaction_by_report = frr.groupBy("report_key", "reaction_key").agg(F.max(F.col("is_fatal_outcome").cast("int")).alias("fatal"))
pairs = (suspect_p.join(reaction_by_report, "report_key")
         .groupBy("drug_key", "reaction_key", "period")
         .agg(F.count("*").alias("a"),
              cnt(F.col("is_serious"))("serious_reports"),
              cnt(F.col("is_death"))("death_reports"),
              F.sum("fatal").alias("fatal_outcome_reports"))
         .persist(StorageLevel.MEMORY_AND_DISK))

drug_reaction = (pairs.where(F.col("a") >= p_min_cases)
                 .withColumnRenamed("a", "reports")
                 .withColumn("rank_in_drug", F.row_number().over(
                     Window.partitionBy("drug_key", "period").orderBy(F.col("reports").desc(), "reaction_key")))
                 .join(d_drug, "drug_key").join(d_reaction, "reaction_key"))
save(drug_reaction, "agg_drug_reaction", zorder=["drug_name", "reaction_pt"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Disproportionality signals (PRR, ROR, chi-square)
# The universe is reports with at least one suspect drug and at least one reaction, per period.
# The 2×2 table for each drug–reaction pair is:
# - `a` = drug and reaction
# - `b` = drug without the reaction
# - `c` = reaction without the drug
# - `d` = neither
# 
# A row is flagged when it meets the Evans criteria: PRR ≥ 2, chi-square (Yates) ≥ 4 and a ≥ 3.

# CELL ********************

universe = suspect_p.select("report_key", "period").distinct().join(reaction_by_report.select("report_key").distinct(), "report_key")
n_total = universe.groupBy("period").agg(F.count("*").alias("n_total"))
drug_totals = suspect_p.join(universe, ["report_key", "period"], "left_semi").groupBy("drug_key", "period").agg(F.count("*").alias("drug_reports"))
reaction_totals = (reaction_by_report.select("report_key", "reaction_key").join(universe, "report_key")
                   .groupBy("reaction_key", "period").agg(F.count("*").alias("reaction_reports")))

a, b, c, d = (F.col(x).cast("double") for x in ("a", "b", "c", "d"))
n = F.col("n_total").cast("double")
valid = (F.col("b") > 0) & (F.col("c") > 0) & (F.col("d") > 0)
prr = (a / (a + b)) / (c / (c + d))
se_ln_prr = F.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
ror = (a * d) / (b * c)
se_ln_ror = F.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
chi_sq = n * F.pow(F.greatest(F.abs(a * d - b * c) - n / 2, F.lit(0.0)), 2) / ((a + b) * (c + d) * (a + c) * (b + d))

signals = (pairs.where(F.col("a") >= p_min_cases).select("drug_key", "reaction_key", "period", "a")
           .join(drug_totals, ["drug_key", "period"]).join(reaction_totals, ["reaction_key", "period"]).join(n_total, "period")
           .withColumn("b", F.col("drug_reports") - F.col("a"))
           .withColumn("c", F.col("reaction_reports") - F.col("a"))
           .withColumn("d", F.col("n_total") - F.col("a") - F.col("b") - F.col("c"))
           .withColumn("prr", F.when(valid, F.round(prr, 4)))
           .withColumn("prr_lower_95", F.when(valid, F.round(F.exp(F.log(prr) - 1.96 * se_ln_prr), 4)))
           .withColumn("prr_upper_95", F.when(valid, F.round(F.exp(F.log(prr) + 1.96 * se_ln_prr), 4)))
           .withColumn("ror", F.when(valid, F.round(ror, 4)))
           .withColumn("ror_lower_95", F.when(valid, F.round(F.exp(F.log(ror) - 1.96 * se_ln_ror), 4)))
           .withColumn("ror_upper_95", F.when(valid, F.round(F.exp(F.log(ror) + 1.96 * se_ln_ror), 4)))
           .withColumn("chi_square", F.when(valid, F.round(chi_sq, 4)))
           .withColumn("signal_flag", F.coalesce((F.col("prr") >= 2) & (F.col("chi_square") >= 4) & (F.col("a") >= 3), F.lit(False)))
           .join(d_drug, "drug_key").join(d_reaction, "reaction_key")
           .select("drug_key", "drug_name", "reaction_key", "reaction_pt", "period",
                   "a", "b", "c", "d", "n_total", "drug_reports", "reaction_reports",
                   "prr", "prr_lower_95", "prr_upper_95", "ror", "ror_lower_95", "ror_upper_95",
                   "chi_square", "signal_flag"))
save(signals, "agg_drug_reaction_signal", zorder=["drug_name", "reaction_pt"])

_ = pairs.unpersist()
_ = suspect_p.unpersist()

# The dataset disclaimer is documented in medallion-architecture-plan.md §8; remove the table earlier builds created.
spark.sql(f"DROP TABLE IF EXISTS {G}.ref_dataset_info")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Validate

# CELL ********************

checks = {
    "fact_report_matches_silver": row_counts["fact_report"] == report.count(),
    "fact_report_drug_matches_silver": row_counts["fact_report_drug"] == drug.count(),
    "fact_report_reaction_matches_silver": row_counts["fact_report_reaction"] == reaction.count(),
    "report_key_unique": fr.select("report_key").distinct().count() == row_counts["fact_report"],
    "drug_key_unique": spark.table(f"{G}.dim_drug").select("drug_key").distinct().count() == row_counts["dim_drug"],
    "reaction_key_unique": spark.table(f"{G}.dim_reaction").select("reaction_key").distinct().count() == row_counts["dim_reaction"],
    "no_orphan_drug_keys": frd.join(spark.table(f"{G}.dim_drug"), "drug_key", "left_anti").count() == 0,
    "no_orphan_reaction_keys": frr.join(spark.table(f"{G}.dim_reaction"), "reaction_key", "left_anti").count() == 0,
    "unknown_excluded_from_aggregates": all(
        spark.table(f"{G}.{t}").where("drug_name = 'UNKNOWN'").limit(1).count() == 0
        for t in ("agg_drug_summary", "agg_drug_reaction", "agg_drug_reaction_signal")),
}
print(json.dumps({"row_counts": row_counts, "checks": checks}, indent=2))

print("Top all-time signals by case count:")
(spark.table(f"{G}.agg_drug_reaction_signal").where("period = 'all_time' AND signal_flag")
 .orderBy(F.col("a").desc()).select("drug_name", "reaction_pt", "a", "prr", "ror", "chi_square").show(15, truncate=False))

failed = [k for k, v in checks.items() if not v]
if failed:
    raise AssertionError(f"Gold validation failed: {failed}")
notebookutils.notebook.exit(json.dumps({"row_counts": row_counts, "checks": checks}))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
