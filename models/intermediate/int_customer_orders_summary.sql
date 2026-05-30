WITH orders AS (

    SELECT * 
    FROM {{ ref('int_orders_enriched') }}

),

items AS (

    SELECT *
    FROM {{ ref('stg_order_items') }}
    WHERE NOT is_orphan_record

),

order_items_agg AS (

    SELECT
        order_id,
        COUNT(*) AS n_items,
        SUM(quantity) AS total_units,
        SUM(subtotal) AS net_revenue_from_items,
        SUM(discount) AS total_discount_from_items,
        MAX(discount_rate) AS max_discount_rate_in_order
    FROM items
    GROUP BY 1

),

base AS (

    SELECT
        o.customer_id,

        o.customer_name,
        o.customer_segment,
        o.customer_city,

        o.gender,
        o.referral_code,

        o.order_id,
        o.order_date,
        o.net_amount,
        o.status,
        o.is_completed,

        oi.n_items,
        oi.total_units

    FROM orders o
    LEFT JOIN order_items_agg oi USING (order_id)

),

agg AS (

    SELECT
        customer_id,

        MAX(order_date) AS last_order_date,

        COUNT(DISTINCT order_id) AS frequency,

        SUM(CASE WHEN is_completed THEN net_amount ELSE 0 END) AS monetary_value,

        AVG(net_amount) AS avg_order_value,

        AVG(n_items) AS avg_items_per_order,

        MIN(order_date) AS first_order_date

    FROM base
    GROUP BY 1

),

final AS (

    SELECT
        a.*,

        -- deterministic recency
        DATE_DIFF(
            'day',
            a.last_order_date,
            (SELECT MAX(order_date) FROM orders)
        ) AS recency_days

    FROM agg a

)

SELECT * FROM final