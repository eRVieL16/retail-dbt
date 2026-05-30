WITH source AS (

    SELECT *, CAST(payment_date AS TIMESTAMP) AS payment_ts FROM {{ source('raw', 'fact_payments') }}

),

orders AS (
    SELECT order_id, order_ts FROM {{ ref('stg_orders') }}
),

joined AS (

    SELECT
        p.*,

        payment_ts,

        -- late arriving detection
        CASE 
            WHEN payment_ts < o.order_ts THEN TRUE
            ELSE FALSE
        END AS is_late_arriving,

        -- grouping method
        CASE
            WHEN payment_method LIKE '%card%' THEN 'card'
            WHEN payment_method LIKE '%transfer%' THEN 'bank_transfer'
            WHEN payment_method LIKE '%wallet%' THEN 'e_wallet'
            WHEN payment_method = 'cod' THEN 'cod'
            WHEN payment_method = 'paylater' THEN 'bnpl'
            ELSE 'other'
        END AS payment_method_group,

        -- split payment detection: order yang dibayar lebih dari 1 kali
        CASE
            WHEN COUNT(*) OVER (PARTITION BY p.order_id) > 1 THEN TRUE
            ELSE FALSE
        END AS is_split_payment

    FROM source p
    LEFT JOIN orders o
        ON p.order_id = o.order_id

)

SELECT * FROM joined