# retail_dbt — Analytics Engineering Portfolio Project

> **Stack**: dbt Core · DuckDB · Python  
> **Data**: Retail simulator dengan 10 raw tables, 5,000 orders, 25,000 clickstream events

## Arsitektur

```
raw CSVs
   │
   ▼
[DuckDB]  ←─ setup.py loads CSVs
   │
   ▼
staging/          ← views, cleaning & typing
   │
   ▼
intermediate/     ← ephemeral, business logic & joins
   │
   ▼
marts/
  ├── core/       ← fct_orders, dim_customers_scd
  ├── finance/    ← fct_revenue_daily
  └── marketing/  ← fct_customer_rfm, fct_funnel_conversion
```

## Data Quality Challenges (Intentional)

| Challenge | Lokasi | Cara handle di dbt |
|---|---|---|
| Orphan records | `fact_order_items` | Left join + `is_orphan_record` flag di `stg_order_items` |
| Late-arriving payments | `fact_payments` | `is_late_arriving` flag via timestamp comparison |
| SCD Type 2 overlap | `dim_customers` | `has_scd_overlap` flag via `lead()` window function |
| Duplicate events | `fact_events` | `row_number()` dedup di `stg_events` |
| Currency mismatch | `raw_returns` | Normalize ke IDR (× 15,500) di `stg_returns` |
| Inconsistent casing | `raw_returns.reason` | `initcap(lower(trim(...)))` + category mapping |
| Nested JSON | `raw_inventory_feed` | Parse di pipeline sebelum masuk dbt |
| Split payments | `fact_payments` | `count(*) over (partition by order_id)` |

## Setup

### 1. Clone & install

```bash
git clone <repo>
cd retail_dbt

pip install dbt-duckdb dbt-utils pandas faker
```

### 2. Generate raw data

```bash
cd ..
python generate_retail_data.py   # output ke retail_raw_data/
cd retail_dbt
```

### 3. Load ke DuckDB

```bash
python setup.py
```
### 4. Install dbt packages

```bash
# letakkan profiles.yml di folder ini atau ~/.dbt/
dbt deps
```

### 5. Add Process Snapshot and Incremental Data

```bash
# Step 1 — generate raw source files
python raw_sources_for_snapshot.py

# Step 2 — load batch pertama ke DuckDB
python setup_snapshot_sources.py --batch=1

# Step 3 — snapshot pertama (initial state)
dbt snapshot

# Step 4 — load batch kedua (ada perubahan segmen & harga)
python setup_snapshot_sources.py --batch=2

# Step 5 — snapshot kedua (tangkap perubahan)
dbt snapshot

# Step 6 — load batch ketiga (ada churn)
python setup_snapshot_sources.py --batch=3

# Step 7 — snapshot ketiga
dbt snapshot

# Step 8 — lihat hasil
dbt run -s stg_customers_snapshot
```
### 6. Run, Test and Documentation dbt

```bash
dbt build           # run + test sekaligus
dbt docs generate
dbt docs serve      # buka lineage graph di browser
```

### 5. Jalankan data quality audit

```bash
dbt compile --select analyses/data_quality_audit
# copy SQL dari target/compiled/retail_dbt/analyses/data_quality_audit.sql
# run di DuckDB CLI: duckdb retail.duckdb < <file.sql>
```

## Model Lineage

![Model Lineage](Assets/lineage.png)

## Key Business Questions yang Bisa Dijawab

- **Revenue**: Total GMV per hari/minggu/bulan per channel dan kota
- **RFM**: Segmentasi customer Champions vs At Risk vs Lost
- **Funnel**: Conversion rate dari page view sampai checkout per channel dan device
- **Returns**: Return rate per kategori produk, refund by reason
- **Data Quality**: Berapa % orders punya late payment? Berapa orphan records?

## Decisions & Trade-offs

**Kenapa ephemeral untuk intermediate?**  
Intermediate models adalah pure business logic — tidak perlu di-materialize karena tidak ada query langsung ke sana. Ephemeral = zero storage cost, zero maintenance.

**Kenapa DuckDB bukan BigQuery?**  
Portfolio-friendly: zero infrastructure, zero cost, full SQL support. Mudah di-swap ke BigQuery/Snowflake dengan ganti profile saja — SQL-nya identik.

**Kenapa tidak pakai `dbt snapshot` untuk SCD?**  
Raw data dari simulator sudah include SCD columns (`valid_from`, `valid_to`, `is_current`). Di real job, kamu akan pakai `dbt snapshot` untuk generate SCD dari non-SCD source.
