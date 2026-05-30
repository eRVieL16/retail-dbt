{{
  config(
    materialized = 'table',
    schema       = 'marketing'
  )
}}

with customer_orders as (

    select
        customer_id,
        count(distinct order_id)             as total_orders,
        sum(net_amount)                      as total_spent,
        date_diff(
            'day',
            max(order_date),
            current_date
        )                                    as days_since_last_order

    from {{ ref('fct_orders') }}
    -- order_status is the renamed column from stg_orders (was: status)
    where order_status != 'cancelled'
    group by 1

),

rfm_scored as (

    select
        customer_id,
        total_orders,
        total_spent,
        days_since_last_order,

        -- Thresholds are vars — override at run time without touching SQL:
        --   dbt build --vars '{"rfm_recency_days_active": 14}'
        {{ rfm_recency_score('days_since_last_order') }}  as recency_score,
        {{ rfm_frequency_score('total_orders') }}         as frequency_score,
        {{ rfm_monetary_score('total_spent') }}           as monetary_score

    from customer_orders

),

final as (

    select
        customer_id,
        total_orders,
        total_spent,
        days_since_last_order,
        recency_score,
        frequency_score,
        monetary_score,
        recency_score + frequency_score + monetary_score  as rfm_score,

        -- Reference the already-computed rfm_score column, not the raw expression.
        -- This keeps the macro call readable and avoids repeating the arithmetic.
        {{ rfm_segment_label('rfm_score') }}              as rfm_segment

    from rfm_scored

)

select * from final
