-- ══════════════════════════════════════════════════════════════
-- SNAPSHOT AUDIT — jalankan setelah minimal 2x dbt snapshot
-- Untuk melihat perubahan yang berhasil ditangkap
-- ══════════════════════════════════════════════════════════════

-- 1. Berapa versi yang ada per customer?
--    customer yang punya 1 versi = tidak pernah berubah
--    customer yang punya 2+ versi = pernah ganti kota/segmen
select
    n_versions,
    count(distinct customer_id)     as n_customers,
    round(
        count(distinct customer_id) * 100.0
        / sum(count(distinct customer_id)) over (),
    2)                              as pct
from {{ ref('stg_customers_snapshot') }}
group by 1
order by 1;


-- 2. Customer yang pernah ganti segmen — lihat history-nya
select
    customer_id,
    full_name,
    segment,
    previous_segment,
    valid_from,
    valid_to,
    is_current
from {{ ref('stg_customers_snapshot') }}
where segment_changed = true
order by customer_id, valid_from
limit 30;


-- 3. Customer yang pernah churn
select
    customer_id,
    full_name,
    count(*)        as n_versions,
    min(valid_from) as first_seen,
    max(valid_from) as last_changed
from {{ ref('stg_customers_snapshot') }}
where ever_churned = true
group by 1, 2
order by last_changed desc
limit 20;


-- 4. Audit incremental — berapa baris yang diproses per run?
--    (hanya bisa dilihat dari dbt logs, tapi ini query untuk verifikasi)
select
    date_trunc('day', dbt_loaded_at)    as load_date,
    count(*)                            as rows_loaded
from {{ ref('fct_orders_incremental') }}
group by 1
order by 1;


-- 5. Verifikasi tidak ada duplikat di incremental model
select
    order_id,
    count(*)    as n_rows
from {{ ref('fct_orders_incremental') }}
group by 1
having count(*) > 1
order by 2 desc
limit 10;
-- Hasil harus kosong (0 rows) kalau unique_key bekerja dengan benar


-- 6. Late-arriving events yang berhasil di-capture
--    (karena kita pakai lookback 2 hari di fct_events_incremental)
select
    event_date,
    count(*)        as n_events,
    count(distinct session_id) as n_sessions
from {{ ref('fct_events_incremental') }}
group by 1
order by 1 desc
limit 14;
