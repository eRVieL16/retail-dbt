"""
run_audit.py
=============
Menjalankan data quality audit tanpa membutuhkan DuckDB CLI.
Bekerja di Windows (PowerShell / CMD), macOS, dan Linux.

Cara penggunaan:
  python run_audit.py

Cara kerja:
  1. Baca file SQL yang sudah di-compile oleh dbt
  2. Eksekusi langsung via duckdb Python package
  3. Print hasil dalam format tabel

Prasyarat:
  - dbt build sudah dijalankan sebelumnya (model harus sudah ada di DuckDB)
  - dbt compile sudah dijalankan (untuk menghasilkan compiled SQL)
    Jika belum: jalankan `dbt compile --select data_quality_audit` dulu
"""

import os
import sys
import duckdb

DB_PATH      = os.environ.get("DUCKDB_PATH", "retail.duckdb")
COMPILED_SQL = os.path.join(
    os.environ.get("DBT_TARGET_PATH", "target"),
    "compiled/retail/analyses/data_quality_audit.sql"
)


def check_prerequisites():
    errors = []

    if not os.path.exists(DB_PATH):
        errors.append(
            f"  ✗  {DB_PATH} tidak ditemukan.\n"
            f"     Jalankan: python setup.py --full-refresh"
        )

    if not os.path.exists(COMPILED_SQL):
        errors.append(
            f"  ✗  {COMPILED_SQL} tidak ditemukan.\n"
            f"     Jalankan: dbt compile --select data_quality_audit"
        )

    if errors:
        print("\nPrerequisite check gagal:\n")
        for e in errors:
            print(e)
        sys.exit(1)


def run():
    check_prerequisites()

    print(f"\nConnecting to {DB_PATH}...")
    con = duckdb.connect(DB_PATH, read_only=True)

    with open(COMPILED_SQL, "r", encoding="utf-8") as f:
        sql = f.read()

    print("Running data quality audit...\n")

    try:
        result = con.execute(sql).fetchall()
    except Exception as e:
        print(f"Error saat eksekusi SQL:\n  {e}")
        sys.exit(1)
    finally:
        con.close()

    # ── Pretty print ───────────────────────────────────────
    header = ("CHECK NAME", "N ROWS", "DESCRIPTION")
    col_w  = [
        max(len(header[0]), max(len(str(r[0])) for r in result)),
        max(len(header[1]), max(len(str(r[1])) for r in result)),
        max(len(header[2]), max(len(str(r[2])) for r in result)),
    ]

    sep  = "+-" + "-+-".join("-" * w for w in col_w) + "-+"
    row_fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_w) + " |"

    print(sep)
    print(row_fmt.format(*header))
    print(sep)

    for row in result:
        print(row_fmt.format(str(row[0]), f"{row[1]:,}", str(row[2])))

    print(sep)
    print(f"\n{len(result)} checks completed.\n")

    # ── Summary ────────────────────────────────────────────
    total_issues = sum(r[1] for r in result if "after_dedup" not in r[0])
    if total_issues == 0:
        print("✓  No data quality issues found.")
    else:
        print(f"⚠  Total flagged records: {total_issues:,}")
        print("   (Expected — these are intentionally introduced issues.)")
        print("   See README for details on each check.")

    print()


if __name__ == "__main__":
    run()
