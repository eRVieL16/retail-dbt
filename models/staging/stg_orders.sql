WITH source AS (

    SELECT * FROM {{ source('raw', 'fact_orders') }}

),

renamed AS (

    SELECT
        order_id,
        customer_id,
        store_id,

        CAST(order_date AS TIMESTAMP)      AS order_ts,
        DATE(order_date)                   AS order_date,

        LOWER(TRIM(status))                AS order_status,

        -- channel dan shipping info dari raw source
        channel,
        shipping_city,

        gross_amount,
        discount_total,
        net_amount,

        -- data quality flags
        CASE 
            WHEN net_amount < 0 THEN TRUE
            ELSE FALSE
        END AS is_negative_order,

        -- metadata
        ingested_at,
        batch_id,
        source

    FROM source

)

SELECT * FROM renamed