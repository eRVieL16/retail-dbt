{{ 
  config(
    materialized  = 'incremental',
    unique_key    = ['date_day', 'channel', 'shipping_city', 'customer_segment'],
    incremental_strategy = 'delete+insert',
    on_schema_change = 'append_new_columns'
  )
}}

{% set lookback_days = var('revenue_lookback_days', 3) %}

WITH orders AS (

    SELECT *
    FROM {{ ref('fct_orders') }}
    WHERE is_completed = TRUE

    {% if is_incremental() %}
        AND order_date_day >= (
            SELECT MAX(date_day) - INTERVAL '{{ lookback_days }} DAY'
            FROM {{ this }}
        )
    {% endif %}

),

returns AS (

    SELECT
        o.order_date_day                    AS date_day,
        o.channel,
        o.shipping_city,
        o.customer_segment,

        SUM(r.refund_amount_idr)            AS total_refunds_idr,
        COUNT(*)                            AS n_returns

    FROM {{ ref('stg_returns') }} r
    JOIN {{ ref('fct_orders') }} o
        ON r.order_id = o.order_id

    {% if is_incremental() %}
        WHERE r.return_date >= (
            SELECT MAX(date_day) - INTERVAL '{{ lookback_days }} DAY'
            FROM {{ this }}
        )
    {% endif %}

    GROUP BY 1, 2, 3, 4

),

daily AS (

    SELECT
        order_date_day          AS date_day,
        channel,
        shipping_city,
        customer_segment,

        COUNT(DISTINCT order_id)        AS n_orders,
        COUNT(DISTINCT customer_id)     AS n_unique_customers,

        SUM(gross_amount)               AS gross_revenue,
        SUM(discount_total)             AS total_discounts,
        SUM(net_amount)                 AS net_revenue,

        AVG(net_amount)                 AS avg_order_value,

        SUM(CASE WHEN is_split_payment THEN 1 ELSE 0 END) AS n_split_payment_orders

    FROM orders
    GROUP BY 1, 2, 3, 4

),

final AS (

    SELECT
        d.*,
        COALESCE(r.total_refunds_idr, 0)                    AS total_refunds_idr,
        COALESCE(r.n_returns, 0)                            AS n_returns,
        d.net_revenue - COALESCE(r.total_refunds_idr, 0)   AS net_revenue_after_returns,

        '{{ run_started_at }}'::timestamp                   AS dbt_loaded_at

    FROM daily d
    LEFT JOIN returns r
        USING (date_day, channel, shipping_city, customer_segment)

)

SELECT * FROM final
