# FDA Human Drug Adverse Events (FAERS): Medallion Architecture Plan

> **Status:** The notebooks and pipeline described in this plan are built, deployed, and tested on scratch schemas. Production `silver` and `gold` tables were built with an earlier version of the notebooks. **Run the pipeline once with `p_reset = true`** to rebuild them to this plan. See [§7](#7-build-artifacts-and-how-to-run).
>
> **Scope:** Data engineering only: build the **Silver** and **Gold** Delta tables from the downloaded openFDA JSON files.
>
> **Downstream consumers (out of scope, but considered in the design):** a Power BI Direct Lake semantic model, a Fabric Data Agent, and a Rayfin app. These consumers are not built as part of this work.
>
> **Approach:** Use the Skills for Fabric `e2e-medallion-architecture` pattern, adapted for a **one-time full load** that minimizes storage. The JSON files serve as Bronze, so there are no Bronze tables. Silver and Gold use schemas in the existing **schema-enabled lakehouse**.

---

## 1. Environment

| Item | Value |
|---|---|
| Workspace | `hlsfdaadverseeventsdemowus001` (`13e6d67e-3693-4f4a-898b-5d0949b4aa9c`) |
| Capacity | `fabhlsiq002usw3`, **F64**, West US 3 |
| Lakehouse | `fda_adverse_events_lakehouse` (`cf5ef8dc-25a3-40c5-b969-736356b758c4`), **schema-enabled**; default schema is `dbo` |
| SQL analytics endpoint | Provisioned |
| `Files/fda_ds/` | 1,799 `*.json.zip` files, ~114 GB (original downloads) |
| `Files/fda_ds_unzipped/` | 1,799 JSON files, **~580 GB**, covering 91 quarters (2004 Q1–2026 Q3) plus 4 `all_other` files. `all_other` is the openFDA set of reports that fall outside the quarterly files. Individual files are up to ~930 MB. |

The zip and unzipped files remain in place. The owner manages their retention manually.

### Source file shape

Each file contains one multiline JSON object with `meta` and `results[]`. Each element of `results` is one safety report, with these nested structures:

- `patient.drug[]`
- `patient.reaction[]`
- `drug[].openfda{}`

Key modeling facts from the [openFDA drug event documentation](https://open.fda.gov/apis/drug/event/):

- A report can list multiple drugs and multiple reactions, but **a specific drug is not linked to a specific reaction**. All drug–reaction analysis must therefore be done at report level.
- Updates arrive as new `safetyreportversion` records. Silver keeps the latest version of each report.
- Reports are unvalidated and **cannot establish causality or incidence**. The disclaimer is documented in [§8](#8-disclaimer) and the README.

---

## 2. Target architecture

```text
 BRONZE (files, no tables)
   Files/fda_ds/*.json.zip  ·  Files/fda_ds_unzipped/*.json
            │  nb_fda_01_silver_load   (PySpark, pruned explicit schema, multi-quarter batches)
            ▼
 SILVER (schema `silver`, Delta)
   adverse_event_report      1 row / report (latest version)
   adverse_event_drug        1 row / report × drug
   adverse_event_reaction    1 row / report × reaction
   drug_pharm_class          1 row / report × drug × pharmacologic class
   load_log, dq_log          small operational tables
            │  nb_fda_02_gold_build    (PySpark / Spark SQL)
            ▼
 GOLD (schema `gold`, Delta)
   dim_*, bridge_*, fact_*   narrow star schema
   agg_*                     pre-computed insight tables
            │
            ▼  (future, out of scope)
   Direct Lake semantic model → Power BI · Data Agent · Rayfin app
```

### 2.1 Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Bronze | JSON files in `Files/`; **no Bronze tables** | Avoids duplicating 580 GB of raw data for a one-time load. The source files remain available for lineage and replay. |
| Lakehouse topology | Existing schema-enabled lakehouse with `silver` and `gold` schemas | Uses the skill-preferred one-lakehouse-with-schemas pattern and avoids copying data. |
| Engine | PySpark notebooks | Suits a one-time build. MLVs mainly benefit repeatable refreshes. They can be added later through `spark-cli` (**authoring** mode). MLVs require a schema-enabled lakehouse, which this lakehouse is. |
| Load pattern | One-time full load in large multi-quarter batches, with a restart log | Few batches reduce the fixed cost of each batch. A rerun resumes without reprocessing completed quarters. There are no incremental loads. |
| Physical layout | No partitioning; Z-ordering and V-Order applied once in finalize | Each table is only a few GB, below the ~1 GB-per-partition guidance. Z-ordering provides file skipping without small files. |
| Gold shape | Narrow integer-key facts with readable text stored in dimensions | Keeps Gold small and fits the Direct Lake star schema. |

### 2.2 Downstream consumption requirements built into the tables

The semantic model, Data Agent, and Rayfin app are out of scope. The Silver and Gold tables must still meet the following requirements so these consumers can be built later without rework.

| Requirement | Why |
|---|---|
| **No array, struct, or map columns** in Silver or Gold | Direct Lake and the SQL analytics endpoint, which Rayfin connectors and Data Agents use, do not support complex types. |
| **Decoded, human-readable values** stored alongside or instead of E2B codes | The Data Agent needs readable values to answer questions, and Power BI and Rayfin need display-ready labels. |
| **Consistent snake_case names** with **table and column descriptions** | Descriptions help Data Agent query generation and map to semantic model descriptions. They are applied after the build through `onelake-catalog-cli` **curate** mode. |
| **Stable surrogate keys** (deterministic `xxhash64` of the natural key) and a `dim_date` table | Supports Direct Lake relationships and Rayfin lookups. Facts get their keys without joining to dimensions. |
| **Small pre-aggregated `agg_*` tables** | Keeps Rayfin API calls and agent queries fast. |
| **A documented disclaimer** ([§8](#8-disclaimer)) | Downstream consumers reuse the same text: the Power BI About page, Data Agent instructions, and the Rayfin app footer. |

---

## 3. JSON to Silver: `nb_fda_01_silver_load`

### 3.1 Load strategy

1. **Use a pruned explicit schema.** Define a `StructType` that contains only the fields listed in §3.2. Spark then skips all other fields while parsing. Do not infer the schema across 580 GB.
2. **Read whole quarters in large batches.** Read `Files/fda_ds_unzipped/{yyyy}q{n}-*.json` and `all_other-*.json` with `multiLine=true` and `mode=PERMISSIVE`. Quarters are grouped into batches of about `p_files_per_batch` files (default 128), which gives about 15 batches for 92 quarter sets. Each multiline file is parsed by a single task. With 64 cores, a 128-file batch is read in about two waves of tasks.
3. **Spread the work across all cores.** Spark reads each multiline file as one partition, which would cap every later step at one task per file and make it wait for the largest file. Immediately after reading, the parsed reports are repartitioned to 128 partitions and cached, and every table is built from that cached data.
4. **Transform each batch.**
   - Explode `results` into report rows.
   - Explode `patient.drug` and `patient.reaction` into child rows.
   - Explode the `openfda.pharm_class_*` arrays into the bridge table.
   - Type and decode values, apply data-quality rules, and **append** to the Silver tables with `_source_quarter` and `_report_uid`. `_report_uid` is a hash of the report ID, version, file and position, and links child rows to their exact report version. The report table also records `_source_file` and `_source_record_index` for lineage.
5. **Record restart status.** Write one row per quarter to `silver.load_log` with these fields:
   - report, drug, reaction, and pharmacologic-class row counts
   - corrupt-file count
   - `meta.results.total` and whether the loaded report count matches it
   - status
   - start and end timestamps

   On rerun, skip quarters marked `Succeeded`. Before retrying a quarter, delete its partial rows by `_source_quarter`.
6. **Finalize after all batches.**
   - Keep the latest version of each `safetyreportid`. Rank versions by highest `safetyreport_version`, then latest `receipt_date`, then latest source quarter. `all_other` ranks lowest.
   - Delete superseded report rows and their child rows by `_report_uid`.
   - Run `OPTIMIZE` with `ZORDER` and V-Order, then `VACUUM` with the default retention. The 7-day retention means replaced files stay in storage until a later `VACUUM`.

**Schema note:** `reportduplicate` is a single object in older files and sometimes an array in newer files. It is read as raw JSON text and parsed in both shapes. When there are several duplicate sources, they are joined with `; `. The pruned schema was checked against the smallest file from every quarter and from `all_other`, and no files were flagged corrupt.

**Spark profile:**
- **Session:** a first-cell `%%configure` holds a fixed 8 executors of 8 cores and 56 GB each (`spark.dynamicAllocation.minExecutors` = `maxExecutors` = 8). With the pool default of dynamic allocation, the full run used only 2–3 executors, because each batch's demand burst was too short to trigger scale-up.
- **During the load:** V-Order and Optimize Write are off, because writes are append-only and are rewritten by `OPTIMIZE`.
- **During finalize:** V-Order is turned on. AQE is on throughout.

### 3.2 Field scope

| Level | Kept fields |
|---|---|
| Report | `safetyreportid`, `safetyreportversion`, `receivedate`, `receiptdate`, `transmissiondate` (+ `*dateformat`), `reporttype`, `serious`, the six `seriousness*` flags, `fulfillexpeditecriteria`, `primarysourcecountry`, `occurcountry`, `primarysource.qualification`, `primarysource.reportercountry`, `sender.sendertype`, `sender.senderorganization`, `companynumb`, `duplicate`, `reportduplicate.duplicatesource` |
| Patient | `patientonsetage`, `patientonsetageunit`, `patientagegroup`, `patientsex`, `patientweight`, `patientdeath.patientdeathdate` |
| Reaction | `reactionmeddrapt`, `reactionmeddraversionpt`, `reactionoutcome` |
| Drug | `drugcharacterization`, `medicinalproduct`, `activesubstance.activesubstancename`, `drugindication`, `drugadministrationroute`, `drugdosagetext`, `drugdosageform`, `actiondrug`, `drugrecurreadministration`, `drugstartdate`, `drugenddate`, `drugtreatmentduration`, `drugtreatmentdurationunit` |
| openFDA | `brand_name`, `generic_name`, `substance_name`, `product_type`, `route`, `rxcui`, `unii`, `pharm_class_epc`, `pharm_class_moa`, `pharm_class_pe`, `pharm_class_cs` |

**Excluded fields (not parsed):**

- **openFDA:** `manufacturer_name` (left out of the demo on purpose), `product_ndc`, `package_ndc`, `application_number`, `spl_id`, `spl_set_id`, `nui`
- **Drug:** `drugauthorizationnumb`, `drugbatchnumb`, and cumulative or structured dose fields
- **Report:** `authoritynumb`, `reportduplicate.duplicatenumb`, `receiver.*`
- **File metadata:** `meta.*`

### 3.3 Silver tables

No columns use complex types. Multi-valued openFDA fields are stored as **`; `-delimited text columns** holding every value (`*_all`). The one exception is `product_type`, which keeps its first value. The drug's identity is the derived `drug_name` ([§3.5](#35-drug-identification)), not any single openFDA value. Pharmacologic classes are stored in a separate bridge table.

**`silver.adverse_event_report`: one row per report**

| Group | Columns |
|---|---|
| Keys | `safetyreport_id` (string), `safetyreport_version` (int), `company_number` |
| Dates | `receive_date`, `receipt_date`, `transmission_date` (`DATE`; date formats 102, 610, and 602 are parsed), `receive_year`, `receive_quarter` |
| Report | `report_type` (Spontaneous, Report from study, Other, Not available to sender), `is_expedited` |
| Seriousness | `is_serious`, `is_death`, `is_life_threatening`, `is_hospitalization`, `is_disabling`, `is_congenital_anomaly`, `is_other_serious` (`BOOLEAN`) |
| Geography | `primary_source_country`, `occur_country`, `reporter_country` (ISO-2) |
| Reporter | `reporter_qualification` (Physician, Pharmacist, Other health professional, Lawyer, Consumer or non-health professional, Unknown), `is_hcp_reported`, `sender_type`, `sender_organization` |
| Patient | `patient_sex` (Male, Female, Unknown), `patient_age_years` (normalized from age units 800–805), `age_group` (`0-17`, `18-44`, `45-64`, `65-74`, `75+`, `Unknown`), `patient_weight_kg`, `patient_death_date` |
| Duplicates | `is_duplicate`: **earlier versions of this report were submitted to FDA** (openFDA `duplicate` = 1). It does **not** mean the same event was reported separately under another report ID. `duplicate_source`: the organizations that also hold this case. |
| Counts | `drug_count`, `suspect_drug_count`, `reaction_count` |
| Lineage | `_source_quarter`, `_source_file` (JSON file name, for example `2025q4-drug-event-0001-of-0029.json`), `_source_record_index` (0-based position in that file's `results` array), `_loaded_ts` |

Partitioning: none. Z-order: `receive_year`, `safetyreport_id`. `receive_year` sits among the first 32 columns because Delta collects the file statistics that Z-ordering needs only for those columns.

**`silver.adverse_event_drug`: one row per report × drug**

| Group | Columns |
|---|---|
| Keys and role | `safetyreport_id`, `drug_seq`, `drug_role` (Suspect, Concomitant, Interacting) |
| Product names (as reported) | `medicinal_product` (raw), `medicinal_product_std` (cosmetic cleanup only: uppercase, trimmed, spaces collapsed, trailing periods removed, placeholders such as `UNK` set to NULL), `active_substance` |
| Drug identity | `drug_name` and `drug_name_source` (`openfda_generic`, `reported_substance`, `product_text`, or `none`); see [§3.5](#35-drug-identification) |
| openFDA values | `brand_names_all`, `generic_names_all`, `substance_names_all`, `rxcui_all`, `unii_all` (every value, `; `-joined; RxCUI and UNII are kept for future drug and substance normalization); `product_type`; `is_openfda_matched` |
| Use and administration | `drug_indication`, `route` (decoded), `dosage_text`, `dosage_form` |
| Actions and rechallenge | `action_taken` (Drug withdrawn, Dose reduced, Dose increased, Dose not changed, Unknown, Not applicable), `rechallenge` |
| Dates and duration | `drug_start_date`, `drug_end_date`, `treatment_duration_days` |

Partitioning: none, because joins use `safetyreport_id`. Z-order: `drug_name`, `safetyreport_id`.

**`silver.adverse_event_reaction`: one row per report × reaction**

Columns: `safetyreport_id`, `reaction_seq`, `reaction_pt` (MedDRA Preferred Term, trimmed; casing is harmonized in `gold.dim_reaction`), `meddra_version`, `reaction_outcome` (Recovered/resolved, Recovering/resolving, Not recovered/not resolved, Recovered with sequelae, Fatal, Unknown), `is_fatal_outcome`.

Z-order: `reaction_pt`, `safetyreport_id`.

**`silver.drug_pharm_class`: one row per report × drug × pharmacologic class**

Columns: `safetyreport_id`, `drug_seq`, `class_type` (`EPC`, `MOA`, `PE`, `CS`), `pharm_class`.

**`silver.load_log` and `silver.dq_log`**

These tables store per-quarter load status and per-rule data-quality counts.

### 3.4 Data quality rules and validation

| Rule | Action |
|---|---|
| Missing `safetyreportid` | Drop the row and count it in `dq_log` |
| Superseded report versions | Remove during finalization (§3.1, step 6) |
| Unparseable dates, dates before 1900, or dates after the load date | Set to `NULL` and count |
| Age outside 0–120 years, or weight outside 0–600 kg | Set to `NULL` and count |
| Unknown code value | Set to `Unknown` and count |
| Blank or `UNK` text | Set to `NULL` |

**Validation gates:**

- Loaded reports match `meta.results.total` for each quarter.
- No source files are flagged corrupt. A corrupt file still loads, but any field that did not match the schema is set to NULL.
- After deduplication, each `safetyreport_id` appears only once.
- Every child row has a parent report.
- Every drug row has a `drug_name`. The number of distinct names is logged, and the top 100 suspect drugs are spot-checked for leftover splits.
- The null-rate profile of key columns is reviewed.

### 3.5 Drug identification

FAERS reports have no standardized drug identifier. For this demo, each drug row gets a `drug_name` from simple, explainable rules that need no external drug vocabulary. The goal is that the same drug, written different ways, ends up under one name often enough for demo-level analytics. Limits are stated in the [disclaimer](#8-disclaimer).

**Why not use a single openFDA field?** The loaded data (78.3 M drug rows; 73.7% matched by openFDA) showed problems with each option:

- **First generic name:** it splits drugs by salt, for example `LOSARTAN` (131 K rows) and `LOSARTAN POTASSIUM` (84 K).
- **First substance name:** it drops combinations, and it mislabels when openFDA matched an unrelated label. Rows with generic `FOLIC ACID` have a multivitamin's substances, so they would become `CHOLECALCIFEROL`.
- **Brand name:** it never fills a gap, because no row has a brand without a generic or substance. Used as the name, it would also split one drug across its brands.

#### Step A: choose a source name

The first available value in this order wins:

| Order | Source | Value used | `drug_name_source` |
|---|---|---|---|
| 1 | openFDA `generic_name` list | One value from the list. See [Choosing among several openFDA generic names](#choosing-among-several-openfda-generic-names). | `openfda_generic` |
| 2 | Reported `activesubstancename` | Used when openFDA found no match; filled for 83% of unmatched rows from 2013 onward, and almost never before | `reported_substance` |
| 3 | Reported `medicinalproduct` | Last resort, mostly for 2004–2012 | `product_text` |

#### Choosing among several openFDA generic names

openFDA attaches the generic names of every drug label it matched to the reported product. So 19.6% of matched drug rows have several values, for example `ASPIRIN; ASPIRIN 81 MG; ASPIRIN 325 MG`. Each value is normalized (step B), and one is chosen:

1. **Use the value that matches the reported active substance.** Both are compared after normalization.
2. **Exception:** if the matching value is just the shortest value plus extra words, such as a salt that isn't on the salt list, use the shortest value instead. For example, `CLOPIDOGREL BISULFATE` → `CLOPIDOGREL`. Combinations (names containing ` / `) are not affected by this exception.
3. **Otherwise, use the shortest value**, with ties broken alphabetically.

| openFDA generic names | Reported active substance | `drug_name` | Why |
|---|---|---|---|
| `ASPIRIN; ASPIRIN 81 MG; ASPIRIN 325 MG` | – | `ASPIRIN` | Shortest |
| `METFORMIN; METFORMIN ER 500 MG` | `METFORMIN HYDROCHLORIDE` | `METFORMIN` | Matches after normalization |
| `HYDROCORTISONE; ANTI-ITCH CREAM; ANTI ITCH; …` | `HYDROCORTISONE` | `HYDROCORTISONE` | Matches the reported substance; the shortest value, `ANTI ITCH`, is a marketing description |
| `LIDICAINE; LIDOCAINE; …` | `LIDOCAINE` | `LIDOCAINE` | Matches the reported substance; the shortest value is a label typo |
| `LOSARTAN POTASSIUM AND HYDROCHLOROTHIAZIDE; LOSARTAN POTASSIUM` | `HYDROCHLOROTHIAZIDE\LOSARTAN POTASSIUM` | `HYDROCHLOROTHIAZIDE / LOSARTAN` | Matches the reported combination |
| `CLOPIDOGREL; CLOPIDOGREL BISULFATE` | `CLOPIDOGREL BISULFATE` | `CLOPIDOGREL` | The match only adds a salt word, so the shortest value is used |

**Effect on the loaded data:** compared with always taking the shortest value, 0.59% of openFDA-matched drug rows (338 K) get a different name. Examples include `ANTI ITCH` → `HYDROCORTISONE`, `ANTACID` → `CALCIUM CARBONATE`, `ADVIL PM` → `DIPHENHYDRAMINE / IBUPROFEN`, and label typos such as `LIDICAINE`, `BISCODYL`, and `DOXEPN` corrected.

Before 2012 the reported active substance is almost always empty, so the shortest value is used. When openFDA matched both a single-ingredient label and a combination label and no substance was reported, the shortest value picks the single ingredient. The data can't tell which product it was.

#### Step B: normalize the chosen name

The rules are applied in this order to the uppercased, trimmed value.

| Order | Rule | Example |
|---|---|---|
| 1 | Remove text in parentheses | `LOSARTAN (LOSARTAN)` → `LOSARTAN` |
| 2 | Split combinations on `\`, `/`, or ` AND ` into ingredients | `LOSARTAN POTASSIUM AND HYDROCHLOROTHIAZIDE` → `LOSARTAN POTASSIUM`, `HYDROCHLOROTHIAZIDE` |
| 3 | Remove strengths from each ingredient: a leading concentration, a part that is only a strength or a number, and everything from a number that follows a space. Numbers inside a name are kept. | `ASPIRIN 81 MG` → `ASPIRIN`; `HUMIRA 40 MG/0.8 ML PEN` → `HUMIRA`; `0.9% SODIUM CHLORIDE INJECTION` → `SODIUM CHLORIDE INJECTION`; `5-FU`, `COVID-19 VACCINE`, `VITAMIN B12` unchanged |
| 4 | Remove a trailing qualifier: ` NOS`, `, UNSPECIFIED`, or ` UNSPECIFIED FORM` | `INSULIN NOS` → `INSULIN`; `MENTHOL, UNSPECIFIED FORM` → `MENTHOL` |
| 5 | Remove a trailing salt word (details below) | `LOSARTAN POTASSIUM` → `LOSARTAN` |
| 6 | Drop placeholder ingredients (details below) | `UNSPECIFIED INGREDIENT` → (nothing); `ASPIRIN / UNKNOWN DRUG` → `ASPIRIN` |
| 7 | Sort ingredients alphabetically, remove duplicates, and join them with ` / ` | → `HYDROCHLOROTHIAZIDE / LOSARTAN` |

Splitting before removing strengths keeps both ingredients in names like `HYDROCHLOROTHIAZIDE 12.5 MG / LOSARTAN 50 MG`. If nothing is left (for example `UNK`, `50 MG`, or `UNKNOWN MEDICATION`), the next source in step A is tried. If no source gives a name, the name is `UNKNOWN` and `drug_name_source` is `none`.

#### Placeholder names (step 6)

Reporters sometimes enter a phrase instead of a drug name. Without this rule each phrase becomes its own "drug"; `UNSPECIFIED INGREDIENT` alone is on about 131 K drug rows. An ingredient is a placeholder if, after steps 1–5, it:

- **starts with** `UNKNOWN` or `UNSPECIFIED`, for example `UNKNOWN MEDICATION`, `UNKNOWN BLOOD PRESSURE MEDICATION`, or `UNSPECIFIED INGREDIENT`; or
- **consists only of generic words:** UNKNOWN, UNK, UNSPECIFIED, NOT, SPECIFIED, FURTHER, NO, NAME, NOS, OTHER, DRUG(S), MEDICATION(S), MEDICINE(S), INGREDIENT(S), PRODUCT(S), THERAPY/THERAPIES, AGENT(S). Examples: `DRUG, UNSPECIFIED`, `NO DRUG NAME`, `DRUG THERAPY NOS`, `OTHER MEDICATIONS`.

Names that describe a drug or class are kept, for example `OTHER HORMONE REPLACEMENT THERAPY DRUGS`. Step 4 runs first, so qualifiers on a real drug don't make it a placeholder: `INSULIN NOS` becomes `INSULIN`. When every source is a placeholder or empty, the drug is `UNKNOWN` ([§4](#4-silver-to-gold-nb_fda_02_gold_build) explains how Gold handles it).

#### The salt rule (step 5)

**Why it matters:** many drugs are made as a salt, a stable compound of the active drug with an acid or base, such as losartan *potassium* or sertraline *hydrochloride*. The salt doesn't change which drug it is. But labels and reporters write the name both with and without it, so each spelling becomes a separate drug and splits its reports. Examples from the loaded data:

| The same drug written two ways | Where it came from |
|---|---|
| `LOSARTAN` (131 K rows) vs `LOSARTAN POTASSIUM` (84 K) | Generic names on different openFDA labels |
| `RANITIDINE` vs `RANITIDINE HYDROCHLORIDE` | openFDA generic vs substance (590 K rows) |
| `METFORMIN` vs `METFORMIN HYDROCHLORIDE` | openFDA generic vs substance (321 K rows) |
| `AMLODIPINE` vs `AMLODIPINE BESYLATE` | openFDA generic vs substance (288 K rows) |
| `TOFACITINIB` vs `TOFACITINIB CITRATE` | openFDA generic vs substance (257 K rows) |

Choosing among several openFDA generic names already fixes rows whose list contains both forms. The salt rule catches rows whose only name includes the salt, and names typed by reporters.

**Rule:** if the **last word** of an ingredient is on the salt list, remove it. Don't remove it if what remains is itself a mineral (SODIUM, POTASSIUM, CALCIUM, MAGNESIUM, FERROUS, ZINC), because then the mineral is the drug.

- **Salt list (whole-word match):** HYDROCHLORIDE, HCL, SODIUM, POTASSIUM, CALCIUM, MAGNESIUM, BESYLATE, CITRATE, SULFATE, MESYLATE.

**The salt is removed, so the same drug comes together:**

| Before | After |
|---|---|
| `LOSARTAN POTASSIUM` | `LOSARTAN` |
| `SERTRALINE HYDROCHLORIDE` / `METFORMIN HCL` | `SERTRALINE` / `METFORMIN` |
| `AMLODIPINE BESYLATE` | `AMLODIPINE` |
| `LEVOTHYROXINE SODIUM` | `LEVOTHYROXINE` |
| `OMEPRAZOLE MAGNESIUM` | `OMEPRAZOLE` |
| `TOFACITINIB CITRATE` | `TOFACITINIB` |
| `HYDROCHLOROTHIAZIDE\LOSARTAN POTASSIUM` | `HYDROCHLOROTHIAZIDE / LOSARTAN` |

**Unchanged, because the last word isn't on the salt list:**

| Name | Why |
|---|---|
| `POTASSIUM CHLORIDE` | CHLORIDE isn't listed; it's a distinct product from potassium citrate |
| `SODIUM BICARBONATE` | BICARBONATE isn't listed |
| `CALCIUM CARBONATE` | CARBONATE isn't listed |
| `CLOPIDOGREL BISULFATE` | Whole-word match: BISULFATE isn't SULFATE. It stays split from `CLOPIDOGREL`, which is an accepted gap. |

**Unchanged, because what remains is a mineral:**

| Name | Without the safeguard | With it |
|---|---|---|
| `MAGNESIUM SULFATE` | `MAGNESIUM`, merged with magnesium supplements ✗ | unchanged ✓ |
| `FERROUS SULFATE` | `FERROUS` ✗ | unchanged ✓ |
| `POTASSIUM CITRATE` | `POTASSIUM` ✗ | unchanged ✓ |
| `ZINC SULFATE` | `ZINC` ✗ | unchanged ✓ |

Single-word names such as `POTASSIUM` or `MAGNESIUM` are never changed, because no word would remain.

#### Known gaps (accepted for the demo)

- **Brand names typed by reporters** stay as separate drugs, for example `HUMIRA` next to `ADALIMUMAB`.
- **Misspellings stay separate,** for example `LOSARTAN POSTASSIUM`.
- **Salt words not on the short list** still split names: BISULFATE, TARTRATE, MALEATE, FUMARATE, and others.
- **Dose-form words without a number** remain, for example `LOSARTAN POT TAB`.
- **Unusual layouts lose the drug name:** a strength before the name (`81 MG ASPIRIN`), or a drug only inside parentheses (`476 (MESALAZINE)`). These cases are about 3 K rows; they fall through to the next source or `UNKNOWN`.
- **Placeholder detection is word-based.** Vague class phrases such as `DRUG USED IN DIABETES` are kept as names, and a category hint such as `UNKNOWN BLOOD PRESSURE MEDICATION` is lost when the name becomes `UNKNOWN`.
- **Biosimilars are kept as distinct drugs,** for example `INFLIXIMAB-DYYB` separate from `INFLIXIMAB`.
- **openFDA lists that mix products** can still pick an imperfect generic. This happens when no active substance was reported, and with combination names written with commas (for example `ACETAMINOPHEN, GUAIFENESIN, AND PHENYLEPHRINE`), which aren't split because commas also appear inside dose forms.
- **No authoritative drug vocabulary such as RxNorm is used.** All RxCUIs and UNIIs are kept (`rxcui_all`, `unii_all`), so RxNorm or substance-level normalization can be added later.

---

## 4. Silver to Gold: `nb_fda_02_gold_build`

**Gold profile:**

- `spark.sql.parquet.vorder.default=true`
- `spark.databricks.delta.optimizeWrite.enabled=true`
- `spark.databricks.delta.optimizeWrite.binSize=1g`
- Run `OPTIMIZE ZORDER` after writes.

### 4.1 Star schema

| Table | Grain | Contents |
|---|---|---|
| `gold.dim_date` | Day, 2004 to the end of the latest data year | `date_key` (int `yyyymmdd`), date, year, quarter, month, month name, year-quarter, year-month, month start date, day of week |
| `gold.dim_drug` | `drug_name` ([§3.5](#35-drug-identification)) | `drug_key`, `drug_name`, `brand_names` (the 10 most frequent openFDA brand names across the drug's rows, `; `-joined), the most frequent `product_type` and `pharm_class_epc`, and `is_unknown` (true for the `UNKNOWN` drug) |
| `gold.dim_pharm_class` | Pharmacologic class | `pharm_class_key`, `pharm_class`, `class_type` |
| `gold.bridge_drug_pharm_class` | Drug × class | `drug_key`, `pharm_class_key` |
| `gold.dim_reaction` | MedDRA PT (case-insensitive) | `reaction_key`, `reaction_pt` (most common casing) |
| `gold.dim_country` | Country code | `country_key`, `country_code`, `country_name` (ISO-2 codes resolved to English names; other values kept as-is). Country is `occur_country`, falling back to `primary_source_country`. |
| `gold.fact_report` | Report | `report_key`, `safetyreport_id`, `receive_date_key`, `receive_date`, `occur_country_key`, `report_type`, `reporter_qualification`, `is_hcp_reported`, `sender_type`, `patient_sex`, `age_group`, `patient_age_years`, `patient_weight_kg`, seriousness flags, `has_fatal_reaction`, `drug_count`, `suspect_drug_count`, `reaction_count` |
| `gold.fact_report_drug` | Report × drug | `report_key`, `drug_key`, `drug_seq`, `drug_role`, `is_suspect`, `route`, `action_taken`, `rechallenge`, `drug_indication` |
| `gold.fact_report_reaction` | Report × reaction | `report_key`, `reaction_key`, `reaction_seq`, `reaction_outcome`, `is_fatal_outcome` |

Keys are deterministic `xxhash64` (bigint) values of the natural key. The Gold validation step checks that keys are unique.

**Modeling notes:**

- Low-cardinality descriptors stay as readable columns on `fact_report` instead of separate dimensions. These include sex, age group, report type, and reporter qualification. This keeps future semantic models and agent query generation simple.
- `fact_report_drug` and `fact_report_reaction` connect only through `report_key`. This preserves the FAERS rule that drugs and reactions are linked only at report level.
- **`UNKNOWN` drug:** it stays in `dim_drug` and `fact_report_drug`, so per-report drug counts are complete. `dim_drug.is_unknown` lets the semantic model, the Data Agent, and the Rayfin app filter it out.

### 4.2 Pre-computed insight tables

| Table | Grain | Contents |
|---|---|---|
| `gold.agg_report_trend_monthly` | Month × country × report type × reporter qualification | Reports, serious, death, hospitalization, life-threatening, fatal-outcome, and HCP-reported counts |
| `gold.agg_drug_summary` | Suspect drug × period (`all_time`, `last_3_years`) | Drug name, report counts, serious and fatal-outcome counts, sex and age-band counts, first and last receive dates, serious %, top indication |
| `gold.agg_drug_reaction` | Suspect drug × reaction PT × period, where reports ≥ 3 | Drug and reaction names, co-reported counts, serious, death, and fatal-outcome counts, and rank within the drug |
| `gold.agg_drug_reaction_signal` | Suspect drug × reaction PT × period, where `a ≥ 3` | Disproportionality metrics (see below) |

The aggregate tables include `drug_name` and `reaction_pt` directly so that Rayfin and the Data Agent can query them without joins.

The drug-level tables (`agg_drug_summary`, `agg_drug_reaction`, and `agg_drug_reaction_signal`) **exclude the `UNKNOWN` drug**, because an entry with no identifiable drug can't be compared with other drugs. Reports whose only suspect drug is `UNKNOWN` are also left out of the signal calculation, so they don't distort its denominators. The Gold validation step checks that `UNKNOWN` doesn't appear in these tables.

**Signal metrics:** The signal table stores 2×2 contingency counts `a`, `b`, `c`, and `d` over distinct reports where the drug is suspect. From these counts it calculates:

- **PRR** with a 95% confidence interval
- **ROR** with a 95% confidence interval
- chi-square
- a `signal_flag` that follows the Evans criteria: PRR ≥ 2, chi-square ≥ 4, and `a` ≥ 3

Two periods are included: `all_time` and `last_3_years`. The minimum case count is `a ≥ 3`. Signals generate hypotheses and should not be treated as conclusions.

### 4.3 Insights supported

1. Report volume from 2004 to 2026 by seriousness, country, report type, and reporter qualification
2. Suspect drugs and pharmacologic classes with the most serious or fatal-outcome reports, including trends
3. Top co-reported reactions for a drug, with demographic breakdowns
4. Drug–reaction pairs with disproportionate reporting, all time and in the last 3 years
5. Outcomes, including death, hospitalization, and life-threatening events, by age group and sex
6. Consumer versus healthcare-professional reporting mix over time and by drug
7. Drug actions, such as withdrawal or dose reduction, and rechallenge compared with reaction outcomes

---

## 5. Execution sequence

| Step | Action | Validation |
|---|---|---|
| 0 | Create `silver` and `gold` schemas | `SHOW SCHEMAS` |
| 1 | Pilot `nb_fda_01_silver_load` on `2004q1`, `2025q4`, and `all_other` in a scratch schema | Row counts match `meta.results.total`, and the largest (~930 MB) files parse |
| 2 | Run the full load across all 92 quarter sets, then finalize (deduplicate, `OPTIMIZE`, `VACUUM`) | Validation gates in §3.4 |
| 3 | Run `nb_fda_02_gold_build` | Gold totals reconcile with Silver, keys are unique, and dimensions have no orphan keys; spot-check top signals |
| 4 | Add table and column descriptions to Silver and Gold using `onelake-catalog-cli` **curate** mode | Descriptions are visible in the OneLake catalog |

**Notebook conventions:**

- Bind notebooks to `fda_adverse_events_lakehouse`.
- Use schema-qualified table names such as `silver.*` and `gold.*`. Schema names are parameters, which allows test runs in scratch schemas.
- Save notebooks in this folder as `.ipynb` files.
- The `pl_fda_one_time_build` pipeline runs steps 2–3 unattended. Rerunning it is safe because quarters that already loaded are skipped.

**Compute:**

- Run the build on **F64**, using the workspace Starter Pool (Medium nodes). Each notebook's `%%configure` reserves 8 executors. Nodes take about 2–4 minutes to arrive after the session starts; the small 2004–2006 batches absorb most of that wait.
- Avoid running concurrent interactive workloads during step 2.

---

## 6. Expected storage

| Data | Approx. size |
|---|---|
| Silver Delta | about 4.4 GB, before `VACUUM` reclaims replaced files |
| Gold Delta | about 1.9 GB |
| Source files (`Files/`) | ~694 GB; retention is managed manually by the owner |

---

## 7. Build artifacts and how to run

| Artifact | Fabric item | Source in this folder |
|---|---|---|
| Silver load notebook | `nb_fda_01_silver_load` | [nb_fda_01_silver_load.ipynb](./nb_fda_01_silver_load.ipynb) |
| Gold build notebook | `nb_fda_02_gold_build` | [nb_fda_02_gold_build.ipynb](./nb_fda_02_gold_build.ipynb) |
| Orchestration pipeline | `pl_fda_one_time_build` | [pl_fda_one_time_build.json](./pl_fda_one_time_build.json) |

### Parameters

Blank or missing values use the defaults below. Pipeline runs pass an empty parameter as null, and both notebooks handle that.

| Parameter | Default | Used by | Purpose |
|---|---|---|---|
| `p_quarters` | `""` (all) | Silver | Comma-separated subset to load, for example `2004q1,2025q4,all_other` |
| `p_files_per_batch` | `128` | Silver | Target number of JSON files per Spark batch. Quarters are never split. Larger batches amortize the fixed cost of each batch, about 35 s. |
| `p_finalize` | `true` | Silver | Deduplicate report versions, then run `OPTIMIZE` and `VACUUM` |
| `p_reset` | `false` | Silver | Drop all Silver tables and reload from scratch. Required when existing tables have a different layout; the notebook stops with a message if a reset is needed. |
| `p_silver_schema` / `p_gold_schema` | `silver` / `gold` | Both | Target schemas; set these to scratch schemas for test runs |
| `p_min_cases` | `3` | Gold | Minimum number of co-reported cases for `agg_drug_reaction` and signals |
| `p_recent_years` | `3` | Gold | Length of the recent-period window |

### Run the full build

1. Open `pl_fda_one_time_build` in the workspace and select **Run**. This loads every quarter into `silver` and then builds `gold`. Set `p_reset = true` to rebuild from scratch, which the current production tables need.
2. If the Silver activity fails or times out, run the pipeline again with `p_reset = false`. Quarters already marked `Succeeded` in `silver.load_log` are skipped.
3. Check the notebook exit values:
   - **Silver** exits with report counts, orphan checks, lineage checks, distinct drug names, rows per `drug_name_source`, and any quarters with count mismatches or corrupt files. It also prints the top 25 suspect drugs for a spot-check.
   - **Gold** exits with reconciliation and key checks.

   Either notebook fails if a validation gate fails.

### Measured results

**Full load profile** (all 92 quarter sets):

| Item | Result |
|---|---|
| Volume | 1,799 files; 21,054,159 reports loaded; 1,813 superseded versions removed, leaving 21,052,346 unique reports |
| Data quality | All quarter sets match `meta.results.total`; 0 corrupt files |
| Rows | 78.3 M drug rows, 63.2 M reaction rows, 96.9 M pharmacologic-class rows |
| openFDA match | 73.7% of drug rows; 19.6% of matched rows have several generic names |
| Country | 61% of reports are from the US and 14% have no country; the rest are spread across about 250 other country codes |

**Performance:**

| Item | Result |
|---|---|
| Session | `%%configure` reserves 8 executors (64 cores); nodes arrive 2–4 minutes after the session starts |
| Batch cost | About 35 s fixed overhead plus about 0.6 s per GB once all executors are up. For example, 2026q3 (36 files, 17 GB) takes 45 s; a 126-file, 63 GB batch runs without spill or failed tasks. |
| Expected full build | Roughly 25–35 min for Silver and 40–50 min for the whole pipeline. This is an estimate; confirm it on the rebuild. With the pool's default dynamic allocation, the same load took 88 min on 2–3 executors. |

**Drug identification** (rule tests, plus a scratch run on `2004q1`, `2025q4`, and `all_other`, 1.9 M drug rows):

| Check | Result |
|---|---|
| Rule tests | All normalization examples in §3.5 behave as documented (65 cases, including strengths, qualifiers, salts, minerals, combinations, and placeholders), as do all generic-name selection examples (14 cases) |
| Distinct drug names (scratch run) | **36,631**, compared with 47,661 when taking the first openFDA generic name (−23%) |
| `drug_name_source` (scratch run) | `openfda_generic` 80%, `reported_substance` 11%, `product_text` 9%, `none` (`UNKNOWN`) 0.09% |
| Losartan (scratch run) | `LOSARTAN` and `HYDROCHLOROTHIAZIDE / LOSARTAN`, plus small free-text variants such as `LOSARTAN POT TAB` and `HCTZ / LOSARTAN` (known gaps) |
| Placeholders (all loaded rows) | `UNSPECIFIED INGREDIENT` (about 131 K rows), `UNKNOWN MEDICATION`, `NO DRUG NAME`, and similar phrases become placeholders. Qualified real drugs such as `INSULIN NOS` and `VITAMIN D NOS` keep their names. Only 4 distinct openFDA generic names reduce to nothing. |
| Generic-name selection (all 57.7 M matched rows) | Matching the reported substance changes the name for 0.59% of rows compared with shortest-only, for example `ANTI ITCH` → `HYDROCORTISONE` and `LIDICAINE` → `LIDOCAINE` |
| Gold | `dim_drug` has `drug_key`, `drug_name`, `brand_names`, `product_type`, `pharm_class_epc`, `is_unknown`. In the scratch run, `UNKNOWN` covers 1,743 drug rows (410 suspect); they remain in `fact_report_drug`, and none appear in the three drug-level aggregate tables. There is no `ref_dataset_info` table. |
| Signals | Top all-time signals are clinically plausible, for example dupilumab with atopic dermatitis and paroxetine with drug withdrawal syndrome |

---

## 8. Disclaimer

Use this text in the README, on the Power BI "About the data" page, in the Data Agent instructions, and in the Rayfin app.

> **About this data.** FAERS adverse event reports are voluntarily submitted and are not validated. They can't establish that a drug caused a reaction, and report counts can't be used to estimate how often a reaction occurs. A report can list several drugs and several reactions, and reactions aren't linked to a specific drug. Disproportionality signals (PRR and ROR) only suggest hypotheses. Cases reported to FDA by more than one party, under different report IDs, aren't de-duplicated. Don't rely on these data to make decisions about medical care.
>
> **Drug identification.** FAERS has no standardized drug identifier. Each reported drug is named by simple rules:
> - Use the openFDA generic name that matches the reported active substance, otherwise the shortest openFDA generic name. If openFDA has no match, use the reported active substance, otherwise the reported product name.
> - Then remove parenthetical text, strengths, qualifiers such as NOS, and common salt words, and write combination products as alphabetically sorted ingredients.
> - Placeholder entries such as UNSPECIFIED INGREDIENT or UNKNOWN DRUG are grouped as UNKNOWN, which is excluded from drug-level summaries and signals.
>
> No authoritative drug vocabulary such as RxNorm is used. Misspellings, brand names entered as free text, and uncommon entries may appear as separate drugs, so drug-level counts and signals are approximate and intended for demonstration only.

---

## References

- openFDA downloads: <https://open.fda.gov/data/downloads/>
- Drug adverse event API overview: <https://open.fda.gov/apis/drug/event/>
- Drug event field definitions: <https://open.fda.gov/fields/drugevent.yaml>
- Rayfin overview: <https://learn.microsoft.com/fabric/apps/rayfin-overview>
- Existing sample in this repo: [`analytics-bi-largecomplex-jsondataset`](../analytics-bi-largecomplex-jsondataset/Readme.md)
