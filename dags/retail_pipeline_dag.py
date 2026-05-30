"""
retail_pipeline_dag.py
======================
Orchestrates the full retail_dbt_v2 pipeline:
  simulator → setup.py → dbt snapshot → dbt build → run_audit.py

Design decisions:
- BashOperator keeps the DAG thin; business logic stays in project scripts.
  Swap to DbtTaskGroup (astronomer-cosmos) when moving to a cloud warehouse.
- Snapshot batches are sequential — DuckDB does not support concurrent writes.
- max_active_runs=1 prevents parallel DAG runs from conflicting on DuckDB.
- All paths resolved from env vars so the DAG is portable across workers /
  Docker containers. No paths are hardcoded.
- on_failure_callback sends a Slack alert on any task failure.
  Set SLACK_WEBHOOK_URL env var to activate; silently skipped if not set.
"""

from __future__ import annotations

import os
import json
import urllib.request
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup

# ---------------------------------------------------------------------------
# Configuration — override via environment variables
# ---------------------------------------------------------------------------

PROJECT_DIR      = os.environ.get("RETAIL_DBT_PROJECT_DIR",  "/project")
PYTHON_BIN       = os.environ.get("RETAIL_PYTHON_BIN",       "python")
DBT_BIN          = os.environ.get("RETAIL_DBT_BIN",          "dbt")
DBT_PROFILES_DIR = os.environ.get("RETAIL_DBT_PROFILES_DIR", PROJECT_DIR)
DBT_TARGET_PATH  = os.environ.get("DBT_TARGET_PATH",         "/data/dbt_target")
SNAPSHOT_BATCHES = int(os.environ.get("RETAIL_SNAPSHOT_BATCHES", "3"))

# Optional — set this env var to enable Slack alerts on task failure.
# Example: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


# ---------------------------------------------------------------------------
# Failure callback — Slack notification
# ---------------------------------------------------------------------------

def notify_slack_on_failure(context: dict) -> None:
    """
    Send a Slack message when any task fails.

    Why a plain urllib request instead of SlackWebhookOperator or an Airflow
    connection? Keeps the callback dependency-free — no extra packages, no
    Airflow connection setup required. Trade-off: less retry logic, but for
    failure notifications that is acceptable.

    Learning note: In production you would use the Airflow Slack provider
    (apache-airflow-providers-slack) and store the webhook in an Airflow
    Connection, not an env var. This implementation is intentionally minimal
    for a local/Docker portfolio setup.
    """
    if not SLACK_WEBHOOK_URL:
        # Env var not set — skip silently. No exception so the task status
        # is not affected by a missing notification config.
        return

    dag_id   = context.get("dag").dag_id
    task_id  = context.get("task_instance").task_id
    run_id   = context.get("run_id", "unknown")
    log_url  = context.get("task_instance").log_url

    message = {
        "text": (
            f":red_circle: *Task failed* in DAG `{dag_id}`\n"
            f"*Task:* `{task_id}`\n"
            f"*Run ID:* `{run_id}`\n"
            f"*Logs:* {log_url}"
        )
    }

    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        # Never let a notification failure break the pipeline itself.
        print(f"[notify_slack_on_failure] Failed to send Slack alert: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

default_args = {
    "owner":               "analytics_engineering",
    "depends_on_past":     False,
    "retries":             1,
    "retry_delay":         timedelta(minutes=5),
    "email_on_failure":    False,
    "email_on_retry":      False,
    # Every task in this DAG will call notify_slack_on_failure on failure.
    # If SLACK_WEBHOOK_URL is not set, the callback exits immediately.
    "on_failure_callback": notify_slack_on_failure,
}


def _dbt(subcmd: str, extra: str = "") -> str:
    """
    Build a dbt CLI command scoped to the project directory.

    --profiles-dir  : explicit path so dbt never falls back to ~/.dbt/
    --target-path   : write artifacts to a Docker volume, not the bind-mounted
                      /project dir (avoids Windows permission issues)
    """
    return (
        f"cd {PROJECT_DIR} && "
        f"{DBT_BIN} {subcmd} "
        f"--profiles-dir {DBT_PROFILES_DIR} "
        f"--target-path {DBT_TARGET_PATH} "
        f"{extra}"
    ).strip()


def _py(script: str, args: str = "") -> str:
    """Run a Python script from the project root."""
    return f"cd {PROJECT_DIR} && {PYTHON_BIN} {script} {args}".strip()


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="retail_pipeline",
    description="End-to-end retail pipeline: simulator → DuckDB → dbt → audit",
    schedule_interval="0 3 * * *",   # 03:00 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,               # DuckDB single-writer constraint
    default_args=default_args,
    tags=["retail", "analytics_engineering", "dbt", "duckdb"],
    doc_md=__doc__,
) as dag:

    # 1. Simulate raw data ──────────────────────────────────────────────────
    generate_raw = BashOperator(
        task_id="generate_raw_data",
        bash_command=_py("simulator/main.py"),
        doc_md="Generate Parquet files in retail_raw_data/ (Hive-partitioned).",
    )

    # 2. Load Parquet → DuckDB ──────────────────────────────────────────────
    load_duckdb = BashOperator(
        task_id="load_to_duckdb",
        bash_command=_py("setup.py"),
        doc_md=(
            "Merge Parquet → retail.duckdb raw schema. "
            "Incremental by default; setup.py --full-refresh to rebuild."
        ),
    )

    # 3. Snapshot batches (sequential — single DuckDB writer) ───────────────
    with TaskGroup(group_id="snapshot_batches") as snapshot_group:
        prev = None
        for n in range(1, SNAPSHOT_BATCHES + 1):
            gen = BashOperator(
                task_id=f"generate_batch_{n}",
                bash_command=_py("simulator/main.py", f"--snapshot-batch={n}"),
                doc_md=f"Generate snapshot batch {n} raw data.",
            )
            load = BashOperator(
                task_id=f"load_batch_{n}",
                bash_command=_py("setup.py", f"--snapshot-batch={n}"),
                doc_md=f"Load snapshot batch {n} into DuckDB.",
            )
            snap = BashOperator(
                task_id=f"dbt_snapshot_{n}",
                bash_command=_dbt("snapshot"),
                doc_md=(
                    f"Run dbt snapshot for batch {n}. "
                    "Captures SCD2 changes for snp_customers and snp_products."
                ),
            )
            gen >> load >> snap
            if prev:
                prev >> gen
            prev = snap

    # 4. dbt build ──────────────────────────────────────────────────────────
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=_dbt("build", "--fail-fast"),
        doc_md=(
            "Full dbt build: staging → intermediate → marts + all tests. "
            "--fail-fast aborts on first test failure to surface issues early."
        ),
    )

    # 5. Compile audit SQL ──────────────────────────────────────────────────
    compile_audit = BashOperator(
        task_id="compile_audit_sql",
        bash_command=_dbt("compile", "--select data_quality_audit"),
        doc_md=(
            "Compile analyses/data_quality_audit.sql. "
            "Output written to DBT_TARGET_PATH so run_audit.py can read it."
        ),
    )

    # 6. Run data quality audit ─────────────────────────────────────────────
    run_audit = BashOperator(
        task_id="run_audit",
        bash_command=_py("run_audit.py"),
        doc_md=(
            "Execute compiled audit SQL on DuckDB and print flagged records. "
            "Cross-platform — no DuckDB CLI required (works on Windows too)."
        ),
    )

    # 7. Regenerate dbt docs (non-blocking) ─────────────────────────────────
    gen_docs = BashOperator(
        task_id="generate_dbt_docs",
        bash_command=_dbt("docs generate"),
        # all_done: runs even if upstream tasks had warnings or soft failures.
        # Ensures docs are always up-to-date regardless of test results.
        trigger_rule="all_done",
        doc_md="Rebuild dbt docs catalog. Picked up by dbt-docs service on next request.",
    )

    # Dependency graph ───────────────────────────────────────────────────────
    (
        generate_raw
        >> load_duckdb
        >> snapshot_group
        >> dbt_build
        >> compile_audit
        >> run_audit
        >> gen_docs
    )
