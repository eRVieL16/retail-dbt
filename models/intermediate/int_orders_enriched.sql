WITH orders AS (

    SELECT * 
    FROM {{ ref('stg_orders') }}

),

customers AS (

    -- SCD point-in-time join
    SELECT *
    FROM {{ ref('stg_customers') }}

),

payments_summary AS (

    SELECT
        order_id,

        SUM(amount)                                          AS total_paid,
        COUNT(*)                                             AS n_payment_rows,
        COUNT(*) > 1                                         AS is_split_payment,
        BOOL_OR(is_late_arriving)                            AS has_late_payment,
        MIN(payment_ts)                                      AS first_payment_ts,
        CAST(MIN(payment_ts) AS DATE)                        AS first_payment_date,
        STRING_AGG(DISTINCT payment_method_group, ', ')      AS payment_methods_used

    FROM {{ ref('stg_payments') }}
    GROUP BY 1

),

enriched AS (

    SELECT
        -- order keys
        o.order_id,
        o.customer_id,
        o.store_id,

        -- dates (all variants fct_orders needs)
        o.order_ts,
        o.order_date,
        CAST(o.order_date AS DATE)                           AS order_date_day,
        DATE_TRUNC('week',  o.order_date)::date              AS order_week,
        DATE_TRUNC('month', o.order_date)::date              AS order_month,

        -- order attributes
        o.order_status                                       ,
        o.gross_amount,
        o.discount_total,
        o.net_amount,
        o.is_negative_order                                  AS is_bad_order,

        -- updated_at from raw (needed for incremental filter)
        o.ingested_at                                        AS updated_at,

        -- channel / shipping — from raw source via stg_orders
        o.source                                             AS channel,
        NULL::varchar                                        AS shipping_city,   -- populated by raw data column if present

        -- customer attributes at time of order (SCD point-in-time)
        c.customer_key,
        c.full_name                                          AS customer_name,
        c.segment                                            AS customer_segment,
        c.city                                               AS customer_city,
        c.gender                                             AS customer_gender,
        c.referral_code,
        c.gender AS gender,

        -- derived flags
        CASE WHEN o.order_status = 'completed' THEN TRUE ELSE FALSE END AS is_completed,

        -- payments
        COALESCE(p.total_paid, 0)                            AS total_paid,
        COALESCE(p.n_payment_rows, 0)                        AS n_payment_rows,
        COALESCE(p.is_split_payment, FALSE)                  AS is_split_payment,
        COALESCE(p.has_late_payment, FALSE)                  AS has_late_payment,
        p.first_payment_ts,
        p.first_payment_date,
        p.payment_methods_used,

        -- payment latency
        DATE_DIFF('minute', o.order_ts, p.first_payment_ts) AS minutes_to_payment

    FROM orders o

    -- LEFT JOIN customers c
    --     ON o.customer_id = c.customer_id
    --    AND o.order_ts BETWEEN c.valid_from AND COALESCE(c.valid_to, '2999-12-31'::timestamp)
    LEFT JOIN customers c
        ON o.customer_id = c.customer_id
        -- Pastikan c.valid_from dan c.valid_to sudah di-cast ke TIMESTAMP
        AND o.order_ts BETWEEN CAST(c.valid_from AS TIMESTAMP) 
                           AND COALESCE(CAST(c.valid_to AS TIMESTAMP), CAST('2999-12-31' AS TIMESTAMP))
    LEFT JOIN payments_summary p
        USING (order_id)

)

SELECT * FROM enriched
