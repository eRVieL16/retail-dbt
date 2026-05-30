WITH source AS (

    SELECT * FROM {{ source('raw', 'fact_order_items') }}

),

orders AS (
    SELECT order_id FROM {{ ref('stg_orders') }}
),

joined AS (

    SELECT
        i.*,

        -- orphan detection
        CASE WHEN o.order_id IS NULL THEN TRUE ELSE FALSE END AS is_orphan_record,

        -- normalize discount rate
        CASE 
            WHEN unit_price = 0 THEN 0
            ELSE discount / unit_price
        END AS discount_rate

    FROM source i
    LEFT JOIN orders o
        ON i.order_id = o.order_id

)

SELECT * FROM joined