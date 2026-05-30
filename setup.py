"""
setup.py
=========
Load semua file Parquet dari retail_raw_data/ ke DuckDB.

Mode penggunaan:

  # Full load (drop + recreate semua tabel):
  python setup.py --full-refresh

  # Incremental load (tambah data baru saja, skip kalau tabel sudah ada):
  python setup.py

  # Load snapshot sources untuk batch tertentu:
  python setup.py --snapshot-batch=1
  python setup.py --snapshot-batch=2
  python setup.py --snapshot-batch=3

Urutan setup lengkap:
  1. python simulator/main.py                        # generate semua data
  2. python setup.py --full-refresh                  # load ke DuckDB
  3. python simulator/main.py --snapshot-batch=1
  4. python setup.py --snapshot-batch=1
  5. dbt deps && dbt snapshot && dbt build
  6. python simulator/main.py --snapshot-batch=2
  7. python setup.py --snapshot-batch=2
  8. dbt snapshot && dbt build
  9. python simulator/main.py --snapshot-batch=3
  10. python setup.py --snapshot-batch=3
  11. dbt snapshot && dbt build
"""

import argparse
import glob
import os

import duckdb

# DB_PATH dibaca dari environment variable DUCKDB_PATH.
# - Local dev  : tidak perlu set apa-apa → pakai "retail.duckdb" di folder project
# - Docker     : set DUCKDB_PATH=/data/retail.duckdb (shared volume di docker-compose)
DB_PATH   = os.environ.get("DUCKDB_PATH", "retail.duckdb")
DATA_PATH = os.environ.get("RETAIL_DATA_PATH", "./retail_raw_data")

# ── Main tables (fact + dimension) ──────────────────────────────
MAIN_TABLES = {
    "fact_orders":        "fact_orders/**/*.parquet",
    "fact_order_items":   "fact_order_items.parquet",
    "fact_payments":      "fact_payments/**/*.parquet",
    "fact_events":        "fact_events/**/*.parquet",
    "dim_customers":      "dim_customers.parquet",
    "dim_products":       "dim_products.parquet",
    "dim_stores":         "dim_stores.parquet",
    "raw_returns":        "raw_returns.parquet",
    "raw_inventory_feed": "raw_inventory_feed.parquet",
}

# ── Snapshot source tables ────────────────────────────────────────
SNAPSHOT_TABLES = {
    "raw_customers_current": "snapshots/batch_{batch}/raw_customers_current.parquet",
    "raw_products_current":  "snapshots/batch_{batch}/raw_products_current.parquet",
}


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def table_exists(con, table: str) -> bool:
    return con.execute(
        f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'"
    ).fetchone()[0] > 0


def get_max_ingested_at(con, table: str):
    try:
        return con.execute(f"SELECT MAX(ingested_at) FROM {table}").fetchone()[0]
    except Exception:
        return None


def files_exist(pattern: str) -> bool:
    return len(glob.glob(pattern, recursive=True)) > 0


def normalize(path: str) -> str:
    return path.replace("\\", "/")


# ─────────────────────────────────────────────────────────────────
# LOAD LOGIC
# ─────────────────────────────────────────────────────────────────

def full_refresh(con, table: str, pattern: str) -> None:
    print(f"🔄 FULL REFRESH → {table}")

    if not files_exist(pattern):
        print(f"   ⚠  no files found — skipping {table}")
        return

    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"""
        CREATE TABLE {table} AS
        SELECT * FROM read_parquet('{normalize(pattern)}')
    """)
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"   {count:,} rows loaded")


def incremental_load(con, table: str, pattern: str) -> None:
    print(f"⚡ INCREMENTAL → {table}")

    if not files_exist(pattern):
        print(f"   ⚠  no files found — skipping {table}")
        return

    if not table_exists(con, table):
        print("   table not found → fallback to full refresh")
        return full_refresh(con, table, pattern)

    max_ts = get_max_ingested_at(con, table)
    if max_ts is None:
        print("   no ingested_at found → full refresh")
        return full_refresh(con, table, pattern)

    con.execute(f"""
        INSERT INTO {table}
        SELECT * FROM read_parquet('{normalize(pattern)}')
        WHERE ingested_at > '{max_ts}'
    """)
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"   {count:,} rows now in table (added since {max_ts})")


def replace_table(con, table: str, pattern: str) -> None:
    """
    Drop + replace — untuk snapshot sources yang selalu full-overwrite
    karena ini tabel current-state (bukan append).
    """
    print(f"♻  REPLACE → {table}")

    if not files_exist(pattern):
        print(f"   ⚠  no files found — skipping {table}")
        return

    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"""
        CREATE TABLE {table} AS
        SELECT * FROM read_parquet('{normalize(pattern)}')
    """)
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"   {count:,} rows loaded")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINTS
# ─────────────────────────────────────────────────────────────────

def load_main_tables(con, do_full_refresh: bool) -> None:
    print("\n── Main tables ────────────────────────────────")
    for table, glob_pattern in MAIN_TABLES.items():
        full_path = os.path.join(DATA_PATH, glob_pattern)
        if do_full_refresh:
            full_refresh(con, table, full_path)
        else:
            incremental_load(con, table, full_path)


def load_snapshot_batch(con, batch: int) -> None:
    print(f"\n── Snapshot batch {batch} ────────────────────────────────")
    for table, pattern_template in SNAPSHOT_TABLES.items():
        glob_pattern = pattern_template.format(batch=batch)
        full_path = os.path.join(DATA_PATH, glob_pattern)
        replace_table(con, table, full_path)


def main():
    parser = argparse.ArgumentParser(
        description="Load Parquet files into DuckDB"
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        default=False,
        help="Drop and recreate all main tables (default: incremental)",
    )
    parser.add_argument(
        "--snapshot-batch",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Load snapshot sources for a specific batch. Mutually exclusive with main load.",
    )
    args = parser.parse_args()

    con = duckdb.connect(DB_PATH)
    print(f"Connected to {DB_PATH}")

    if args.snapshot_batch is not None:
        load_snapshot_batch(con, args.snapshot_batch)
    else:
        load_main_tables(con, do_full_refresh=args.full_refresh)

    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
