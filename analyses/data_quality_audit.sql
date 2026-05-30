-- ============================================================
-- DATA QUALITY AUDIT
-- Cara menjalankan — pilih salah satu:
--
-- Option A (Python, works di semua OS):
--   python run_audit.py
--
-- Option B (manual, butuh dbt compile dulu):
--   dbt compile --select data_quality_audit
--   python run_audit.py --compiled
-- ============================================================

-- 1. Orphan order items (partial load simulation)
select
    'orphan_items'                                              as check_name,
    count(*)                                                    as n_rows,
    'Items tanpa order header — simulasi partial load'          as description
from {{ ref('stg_order_items') }}
where is_orphan_record = true

union all

-- 2. Late-arriving payments
select
    'late_arriving_payments',
    count(*),
    'Payments dengan payment_date < order_date'
from {{ ref('stg_payments') }}
where is_late_arriving = true

union all

-- 3. SCD overlap (customer)
select
    'scd_customer_overlap',
    count(*),
    'Customer SCD records dengan overlapping valid_from ranges'
from {{ ref('stg_customers') }}
where has_scd_overlap = true

union all

-- 4. Currency conversion di returns
select
    'returns_currency_converted',
    count(*),
    'Return records yang di-convert dari USD ke IDR'
from {{ ref('stg_returns') }}
where was_currency_converted = true

union all

-- 5. Dedup events — jumlah setelah dedup
select
    'events_after_dedup',
    count(*),
    'Events setelah dedup — bandingkan dengan source untuk lihat jumlah duplikat'
from {{ ref('stg_events') }}

union all

-- 6. Split payments
select
    'split_payment_orders',
    count(distinct order_id),
    'Orders yang dibayar dengan lebih dari 1 metode'
from {{ ref('stg_payments') }}
where is_split_payment = true

union all

-- 7. Negative net amount
select
    'negative_net_amount_orders',
    count(*),
    'Orders dengan net_amount negatif (discount > gross)'
from {{ ref('stg_orders') }}
where is_negative_order = true

order by check_name
