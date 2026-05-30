{{
  config(
    materialized = 'incremental',
    unique_key = 'order_id',
    on_schema_change = 'append_new_columns',
    description = 'Orders fact — append-only incremental strategy (no lookback). Use fct_orders for full delete+insert.'
  )
}}

with source as (
    select * from {{ ref('int_orders_enriched') }}

    {% if is_incremental() %}
        {{ incremental_filter('updated_at') }}
    {% endif %}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['order_id']) }} as order_sk,
        order_id,
        customer_id,
        customer_key,
        store_id,
        order_date,
        order_date_day,
        order_week,
        order_month,
        first_payment_date,
        minutes_to_payment,
        order_status,
        channel,
        shipping_city,
        customer_segment,
        customer_city,
        customer_gender,
        payment_methods_used,
        is_completed,
        is_bad_order,
        is_split_payment,
        has_late_payment,
        gross_amount,
        discount_total,
        net_amount,
        total_paid,
        updated_at,
        current_timestamp as dbt_loaded_at
    from source
)

select * from final
