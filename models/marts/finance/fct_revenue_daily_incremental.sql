{{
  config(
    materialized  = 'incremental',
    unique_key    = ['date_day', 'channel', 'shipping_city', 'customer_segment'],
    on_schema_change = 'append_new_columns',
    description   = 'Daily revenue — incremental dengan composite unique_key. Uses append-only strategy.'
  )
}}

/*
  ════════════════════════════════════════════════════════
  INCREMENTAL DENGAN COMPOSITE UNIQUE KEY

  Tabel ini tidak punya 1 kolom ID unik — kombinasi 4 kolom yang unik.
  Kenapa perlu rebuild beberapa hari ke belakang:
    - Order yang dibuat kemarin bisa saja baru "completed" hari ini
    - Return dari minggu lalu bisa diproses hari ini
    - Lookback 3 hari untuk memastikan angka akurat
  ════════════════════════════════════════════════════════
*/

with orders as (
    select * from {{ ref('fct_orders_incremental') }}
    where is_completed = true

    {% if is_incremental() %}
        and order_date_day >= (
            select max(date_day) - interval 3 day
            from {{ this }}
        )
    {% endif %}
),

returns as (
    select
        r.return_date                               as date_day,
        sum(r.refund_amount_idr)                    as total_refunds_idr,
        count(*)                                    as n_returns
    from {{ ref('stg_returns') }} r

    {% if is_incremental() %}
        where r.return_date >= (
            select max(date_day) - interval 3 day
            from {{ this }}
        )
    {% endif %}

    group by 1
),

daily as (
    select
        order_date_day                                              as date_day,
        channel,
        shipping_city,
        customer_segment,

        count(distinct order_id)                                    as n_orders,
        count(distinct customer_id)                                 as n_unique_customers,
        sum(gross_amount)                                           as gross_revenue,
        sum(discount_total)                                         as total_discounts,
        sum(net_amount)                                             as net_revenue,
        avg(net_amount)                                             as avg_order_value,
        sum(case when is_split_payment then 1 else 0 end)           as n_split_payment_orders,
        current_timestamp                                           as dbt_loaded_at

    from orders
    group by 1, 2, 3, 4
),

with_returns as (
    select
        d.*,
        coalesce(r.total_refunds_idr, 0)                            as total_refunds_idr,
        coalesce(r.n_returns, 0)                                    as n_returns,
        d.net_revenue - coalesce(r.total_refunds_idr, 0)            as net_revenue_after_returns
    from daily d
    left join returns r using (date_day)
)

select * from with_returns
