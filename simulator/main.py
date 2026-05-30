"""
simulator/main.py
==================
Entry point untuk seluruh pipeline data simulasi.

Mode penggunaan:

  # Generate semua data dari awal (full run):
  python simulator/main.py

  # Generate snapshot sources saja (untuk alur dbt snapshot):
  python simulator/main.py --snapshot-batch=1
  python simulator/main.py --snapshot-batch=2
  python simulator/main.py --snapshot-batch=3

Output:
  retail_raw_data/
  ├── dim_customers.parquet          (SCD Type 2, flat)
  ├── dim_products.parquet           (SCD Type 2, flat)
  ├── dim_stores.parquet             (static)
  ├── raw_inventory_feed.parquet     (semi-structured, weekly)
  ├── fact_order_items.parquet       (flat, tidak dipartisi)
  ├── fact_orders/
  │   └── order_date_partition=YYYY-MM-DD/part-*.parquet
  ├── fact_payments/
  │   └── payment_date_partition=YYYY-MM-DD/part-*.parquet
  ├── fact_events/
  │   └── event_date_partition=YYYY-MM-DD/part-*.parquet
  └── snapshots/
      └── batch_{N}/
          ├── raw_customers_current.parquet
          └── raw_products_current.parquet

Semua output sudah siap dibaca oleh setup.py ke DuckDB.
"""

import argparse
import logging
import os
import sys

import pandas as pd
from faker import Faker

# Pastikan folder simulator bisa diimport saat dipanggil dari root project
sys.path.insert(0, os.path.dirname(__file__))

import config
from generators import (
    generate_dim_customers_scd2,
    generate_dim_products_scd2,
    generate_dim_stores,
    generate_fact_orders_and_items,
    generate_fact_payments,
    generate_fact_events,
    generate_raw_returns,
    generate_raw_inventory_feed,
    generate_snapshot_sources,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def write_flat(df: pd.DataFrame, path: str) -> None:
    """Tulis DataFrame sebagai single Parquet file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("  wrote %s  (%s rows)", path, f"{len(df):,}")


def write_partitioned(df: pd.DataFrame, base_path: str, partition_col: str) -> None:
    """
    Tulis DataFrame ke dalam partitioned Parquet dataset.

    Struktur output:
      base_path/partition_col=YYYY-MM-DD/part-YYYY-MM-DD.parquet

    Compatible dengan:
    - DuckDB: read_parquet('base_path/**/*.parquet')
    - Spark:  spark.read.parquet('base_path')
    - Hive-style partition pruning
    """
    df = df.copy()
    df[partition_col] = pd.to_datetime(df[partition_col]).dt.date.astype(str)

    n_partitions = 0
    for partition_value, group in df.groupby(partition_col):
        partition_path = os.path.join(base_path, f"{partition_col}={partition_value}")
        os.makedirs(partition_path, exist_ok=True)
        file_path = os.path.join(partition_path, f"part-{partition_value}.parquet")
        group.drop(columns=[partition_col]).to_parquet(file_path, index=False)
        n_partitions += 1

    log.info(
        "  wrote %s  (%s rows, %s partitions)",
        base_path, f"{len(df):,}", n_partitions,
    )


# ─────────────────────────────────────────────────────────────────
# PIPELINE: full generation
# ─────────────────────────────────────────────────────────────────

def run_full_pipeline(fake: Faker) -> None:
    """
    Generate semua tabel raw dari nol.
    Hapus output lama jika ada, lalu tulis ulang.
    """
    log.info("=== FULL PIPELINE ===")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out = config.OUTPUT_DIR

    # ── Dimensions ────────────────────────────────────────────
    log.info("Generating dim_customers (SCD2)...")
    dim_customers = generate_dim_customers_scd2(fake, config)
    write_flat(dim_customers, f"{out}/dim_customers.parquet")

    log.info("Generating dim_products (SCD2)...")
    dim_products = generate_dim_products_scd2(fake, config)
    write_flat(dim_products, f"{out}/dim_products.parquet")

    log.info("Generating dim_stores...")
    dim_stores = generate_dim_stores(config)
    write_flat(dim_stores, f"{out}/dim_stores.parquet")

    # ── Facts ─────────────────────────────────────────────────
    log.info("Generating fact_orders + fact_order_items...")
    fact_orders, fact_items = generate_fact_orders_and_items(
        dim_customers, dim_products, dim_stores, config
    )

    # Tambahkan partition column sebelum write
    fact_orders_part = fact_orders.copy()
    fact_orders_part["order_date_partition"] = fact_orders_part["order_date"]
    write_partitioned(fact_orders_part, f"{out}/fact_orders", "order_date_partition")
    write_flat(fact_items, f"{out}/fact_order_items.parquet")

    log.info("Generating fact_payments...")
    fact_payments = generate_fact_payments(fact_orders, config)
    fact_payments_part = fact_payments.copy()
    fact_payments_part["payment_date_partition"] = fact_payments_part["payment_date"]
    write_partitioned(fact_payments_part, f"{out}/fact_payments", "payment_date_partition")

    log.info("Generating fact_events...")
    fact_events = generate_fact_events(dim_customers, dim_products, config)
    fact_events_part = fact_events.copy()
    fact_events_part["event_date_partition"] = fact_events_part["event_ts"]
    write_partitioned(fact_events_part, f"{out}/fact_events", "event_date_partition")

    # ── Raw / unstructured ────────────────────────────────────
    log.info("Generating raw_returns...")
    raw_returns = generate_raw_returns(fact_orders, fake, config)
    write_flat(raw_returns, f"{out}/raw_returns.parquet")

    log.info("Generating raw_inventory_feed...")
    raw_inventory = generate_raw_inventory_feed(dim_products, fake, config)
    write_flat(raw_inventory, f"{out}/raw_inventory_feed.parquet")

    log.info("Full pipeline complete — output: %s/", out)
    _print_summary(out)


# ─────────────────────────────────────────────────────────────────
# PIPELINE: snapshot sources only
# ─────────────────────────────────────────────────────────────────

def run_snapshot_batch(batch: int, fake: Faker) -> None:
    """
    Generate raw_customers_current + raw_products_current untuk satu batch.
    Output ke retail_raw_data/snapshots/batch_{N}/.

    Alur penggunaan:
      python simulator/main.py --snapshot-batch=1
      python setup.py --snapshot-batch=1
      dbt snapshot

      python simulator/main.py --snapshot-batch=2
      python setup.py --snapshot-batch=2
      dbt snapshot
      ... dst
    """
    assert batch in (1, 2, 3), f"batch harus 1, 2, atau 3 — diterima: {batch}"

    log.info("=== SNAPSHOT BATCH %s ===", batch)
    out = os.path.join(config.OUTPUT_DIR, "snapshots", f"batch_{batch}")
    os.makedirs(out, exist_ok=True)

    customers_df, products_df = generate_snapshot_sources(batch, fake, config)

    write_flat(customers_df, f"{out}/raw_customers_current.parquet")
    write_flat(products_df,  f"{out}/raw_products_current.parquet")

    log.info("Snapshot batch %s written to %s/", batch, out)


# ─────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────

def _print_summary(out: str) -> None:
    print("\n" + "─" * 55)
    print("  OUTPUT SUMMARY")
    print("─" * 55)
    for root, dirs, files in os.walk(out):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(".parquet"):
                full = os.path.join(root, f)
                size = os.path.getsize(full)
                rel  = os.path.relpath(full, out)
                print(f"  {rel:<55} {size/1024:6.1f} KB")
    print("─" * 55 + "\n")


# ─────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Retail data simulator — generates Parquet data lake files"
    )
    parser.add_argument(
        "--snapshot-batch",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help=(
            "Generate snapshot sources only for a specific batch (1/2/3). "
            "Omit to run the full pipeline."
        ),
    )
    args = parser.parse_args()

    fake = Faker("id_ID")
    Faker.seed(42)

    import random, numpy as np
    random.seed(42)
    np.random.seed(42)

    if args.snapshot_batch is not None:
        run_snapshot_batch(args.snapshot_batch, fake)
    else:
        run_full_pipeline(fake)


if __name__ == "__main__":
    main()
