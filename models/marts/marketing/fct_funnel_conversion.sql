{{
  config(
    materialized='table',
    description='Daily conversion funnel dari clickstream — page_view sampai checkout_complete'
  )
}}

with events as (
    select
        *,
        CAST(event_ts AS DATE) AS event_date
    from {{ ref('stg_events') }}
),

daily_funnel as (
    select
        event_date,
        channel,
        device,

        -- session-level step counts
        count(distinct session_id)                                                          as total_sessions,
        count(distinct case when event_type = 'page_view'         then session_id end)     as sessions_page_view,
        count(distinct case when event_type = 'product_view'      then session_id end)     as sessions_product_view,
        count(distinct case when event_type = 'add_to_cart'       then session_id end)     as sessions_add_to_cart,
        count(distinct case when event_type = 'checkout_start'    then session_id end)     as sessions_checkout_start,
        count(distinct case when event_type = 'checkout_complete' then session_id end)     as sessions_checkout_complete,

        -- unique users per step
        count(distinct case when event_type = 'page_view'         then customer_id end)    as users_page_view,
        count(distinct case when event_type = 'checkout_complete' then customer_id end)    as users_converted,

        count(*)                                                                            as total_events

    from events
    group by 1, 2, 3
),

with_rates as (
    select
        *,
        round(
            cast(sessions_product_view as double)
            / nullif(sessions_page_view, 0), 4
        ) as page_to_pdp_rate,

        round(
            cast(sessions_add_to_cart as double)
            / nullif(sessions_product_view, 0), 4
        ) as pdp_to_cart_rate,

        round(
            cast(sessions_checkout_start as double)
            / nullif(sessions_add_to_cart, 0), 4
        ) as cart_to_checkout_rate,

        round(
            cast(sessions_checkout_complete as double)
            / nullif(sessions_checkout_start, 0), 4
        ) as checkout_completion_rate,

        round(
            cast(sessions_checkout_complete as double)
            / nullif(total_sessions, 0), 4
        ) as overall_conversion_rate,

        current_timestamp as dbt_loaded_at
    from daily_funnel
)

select * from with_rates
