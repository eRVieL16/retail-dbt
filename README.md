# Retail-DBT: Production-Grade Analytics Engineering Pipeline

> **End-to-end analytics pipeline simulating a real retail operation — built to answer business questions, not just move data.**
>
> dbt Core · DuckDB · Apache Parquet · Python · Apache Airflow (reference)

[![Python](https://img.shields.io/badge/Python-47%25-blue)]()
[![SQL](https://img.shields.io/badge/SQL-34%25-orange)]()
[![YAML](https://img.shields.io/badge/YAML-19%25-red)]()


## 🎯 Why This Project Exists

Most data portfolios show clean pipelines with perfect data. **Real analytics engineering is about handling mess.** This project intentionally introduces **8 production-like data issues** — duplicates, orphans, late arrivals, currency mismatches — and demonstrates how to handle each one **transparently and audibly**, never silently dropping data.

**The result:** A pipeline that proves readiness for the chaos of real-world data, built with patterns used at companies like dbt Labs, Spotify, and GitLab.


## 📊 Business Questions Answered

This pipeline doesn't just transform data — it answers questions stakeholders actually ask:

| Stakeholder | Question | Model | Business Impact |
|---|---|---|---|
| **VP Marketing** | Which customer segment has the highest churn rate? | `fct_customer_rfm` + `dim_customers_scd` | Reduce CAC by targeting at-risk segments |
| **Marketing Manager** | Where do we lose customers in the purchase funnel? | `fct_funnel_conversion` | Optimize conversion at the highest drop-off stage |
| **Marketing Manager** | Which sales channel drives the most revenue? | `fct_orders` (grouped by `channel`) | Allocate budget to highest-ROI channels |
| **CFO** | How is daily revenue trending after correcting for late payments? | `fct_revenue_daily_incremental` | Accurate financial reporting with 7-day lookback |
| **Finance Analyst** | How many orders use split payments? | `fct_orders` → `is_split_payment` flag | Identify payment processing optimization opportunities |
| **Operations Lead** | How many order items are orphaned (no matching order)? | `stg_order_items` → `is_orphan_record` flag | Monitor ingestion pipeline health |
| **Data Engineering** | Is the source system creating overlapping customer records? | `stg_customers_snapshot` → `has_scd_overlap` flag | Catch source system bugs before they corrupt analytics |
| **Product Manager** | Which products have the highest return rate and why? | `stg_returns` (normalized reasons) | Improve product quality and descriptions |

> **Key philosophy:** Every data issue is **flagged with a boolean column** — never silently filtered out. Downstream models and BI tools can decide how to handle exceptions. This preserves a **complete audit trail.**


## 🛠️ Tech Stack & Why

| Layer | Tool | Why This Choice |
|---|---|---|
| **Transformation** | dbt Core 1.8+ | Industry standard for analytics engineering — modular, tested, documented |
| **Warehouse** | DuckDB | Zero-infrastructure OLAP — identical SQL runs on BigQuery/Snowflake with a config swap |
| **Storage** | Apache Parquet (Hive-partitioned) | Columnar, compressed, directly queryable by Spark, Athena, BigQuery, Presto |
| **Orchestration** | Apache Airflow (reference DAGs) | DAG patterns ready for production deployment |
| **Language** | Python 3.12 | Data generation, batch loading, quality audit automation |
| **Testing** | dbt-expectations + built-in tests | Schema validation + data quality assertions |
| **Version Control** | Git + GitHub | Collaboration-ready, semantically versioned |

> **Portability guarantee:** Swap `profiles.yml` target from `duckdb` to `bigquery` — **zero SQL changes required.** The same models run in production without modification.


## 🏗️ Architecture Overview
```
┌─────────────────────────────────────────────────────────────┐
│ DATA INGESTION LAYER                                        │
│ simulator/main.py → Parquet files (Hive-partitioned)        │
│ 9 raw tables · 5K orders · 25K events · 500 customers       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ WAREHOUSE LAYER                                             │
│ setup.py → DuckDB (retail.duckdb)                           │
│ Zero-infra · Readable by any Parquet-compatible engine      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ TRANSFORMATION LAYER (dbt)                                  │
│                                                             │
│ STAGING ────► INTERMEDIATE ────► MARTS                      │
│ (clean + flag) (business logic) (stakeholder-ready)         │
│                                                             │
│ Models: 15+ · Tests: 40+ · Snapshots: SCD Type 2            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ CONSUMPTION LAYER                                           │
│ Metabase / Looker Studio / any BI tool                      │
│ Ready for stakeholder dashboards                            │
└─────────────────────────────────────────────────────────────┘
```

## 📈 What This Demonstrates (For Hiring Managers)

| Skill | Evidence in This Project |
|---|---|
| **Dimensional Modeling** | Star schema: 5 fact tables + 4 dimension tables + SCD Type 2 tracking |
| **Incremental Processing** | 3 distinct strategies (`delete+insert`, `append`, macro-based) with lookback buffers |
| **Data Quality Engineering** | 8 intentional issues, each flagged explicitly — never silently dropped |
| **Data Lake Best Practices** | Hive-partitioned Parquet, compatible with Spark/Athena/BigQuery external tables |
| **Production Patterns** | `on_schema_change`, `invalidate_hard_deletes`, composite unique keys, ephemeral models |
| **Testing Culture** | `not_null`, `unique`, `accepted_values`, `dbt-expectations` regex validations |
| **Documentation** | Full YAML schema, model descriptions, auto-generated lineage graph |
| **Business Acumen** | Every model answers a specific stakeholder question (see table above) |
| **SQL Portability** | Same SQL on DuckDB, BigQuery, Snowflake — no vendor lock-in |


## 🧪 Data Quality: 8 Intentional Issues (The "Dirty Data" Manifesto)

Real data is messy. This project doesn't hide from that — it embraces it.

| # | Issue | Source Table | How It's Handled |
|---|---|---|---|
| 1 | **Orphan records** | `fact_order_items` | `LEFT JOIN` → `is_orphan_record` flag in `stg_order_items` |
| 2 | **Late-arriving payments** | `fact_payments` | Timestamp comparison → `is_late_arriving` flag in `stg_payments` |
| 3 | **SCD Type 2 date overlaps** | `dim_customers` | `LEAD()` window → `has_scd_overlap` flag in `stg_customers` |
| 4 | **Duplicate events** | `fact_events` | `ROW_NUMBER()` dedup in `stg_events` (~1% of 25K events) |
| 5 | **Currency mismatch** | `raw_returns` | USD → IDR normalization (× 15,500) in `stg_returns` |
| 6 | **Inconsistent casing** | `raw_returns.reason` | `INITCAP(LOWER(TRIM(...)))` in `stg_returns` |
| 7 | **Nested JSON** | `raw_inventory_feed` | `JSON_EXTRACT` flattening before dbt layer |
| 8 | **Split payments** | `fact_payments` | `COUNT(*) OVER (PARTITION BY order_id)` → `is_split_payment` |

**Audit trail:** Run `python run_audit.py` after `dbt build` to see all flagged rows:


## 📁 Project Structure
```
retail_dbt/
├── simulator/ # Python data generator
│ ├── config.py # Volumes, domains, batch timestamps
│ ├── generators.py # 9 entity generators
│ ├── main.py # Entry: full pipeline or --snapshot-batch=N
│ └── utils.py # Helpers: rand_ts(), to_ts(), new_uuid()
├── models/ # dbt transformation layer
│ ├── staging/ # stg_* — clean, cast, flag
│ ├── intermediate/ # int_* — ephemeral join + business logic
│ └── marts/ # fct_, dim_ — stakeholder-ready output
│ ├── core/ # fct_orders, fct_events, dim_customers_scd
│ ├── finance/ # fct_revenue_daily
│ └── marketing/ # fct_customer_rfm, fct_funnel_conversion
├── snapshots/ # SCD Type 2: snp_customers, snp_products
├── macros/ # Reusable Jinja: utils.sql, incremental_helpers.sql
├── analyses/ # data_quality_audit.sql, snapshot_audit.sql
├── dags/ # Airflow DAG (reference) — ready for orchestration
├── docker/ # Docker config for production parity
├── dbt_project.yml # dbt project configuration
├── packages.yml # dbt dependencies (dbt-expectations)
├── profiles.yml # Connection config — swap target for BigQuery/Snowflake
├── setup.py # Parquet → DuckDB loader
├── run_audit.py # Data quality audit automation
└── requirements.txt # Python dependencies
```

## ⚡ Quick Start (5 Minutes to Running Pipeline)

### Prerequisites
- Python 3.10+
- Git

**No database server, Docker, or cloud account required.**

### Step-by-Step

```bash
# 1. Clone and install
git clone https://github.com/eRVieL16/retail-dbt.git
cd retail-dbt
pip install -r requirements.txt

# 2. Generate 2 years of retail data (Parquet data lake)
python simulator/main.py

# 3. Load into DuckDB
python setup.py --full-refresh

# 4. Install dbt packages
dbt deps

# 5. Simulate 3 batches of source changes (SCD Type 2)
python simulator/main.py --snapshot-batch=1 && python setup.py --snapshot-batch=1 && dbt snapshot
python simulator/main.py --snapshot-batch=2 && python setup.py --snapshot-batch=2 && dbt snapshot
python simulator/main.py --snapshot-batch=3 && python setup.py --snapshot-batch=3 && dbt snapshot

# 6. Build all models + run all tests
dbt build

# 7. Generate documentation
dbt docs generate && dbt docs serve

# 8. Run data quality audit
python run_audit.py
