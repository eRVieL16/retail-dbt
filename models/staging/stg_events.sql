WITH source AS (

    SELECT * FROM {{ source('raw', 'fact_events') }}

),

deduped AS (

    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY event_ts
        ) AS rn
    FROM source

),

final AS (

    SELECT
        event_id,
        session_id,
        customer_id,
        product_id,

        event_type,

        CAST(event_ts AS TIMESTAMP) AS event_ts,

        -- funnel stage
        CASE event_type
            WHEN 'page_view' THEN 1
            WHEN 'product_view' THEN 2
            WHEN 'add_to_cart' THEN 3
            WHEN 'checkout_start' THEN 4
            WHEN 'checkout_complete' THEN 5
            ELSE 0
        END AS funnel_stage,

        channel,
        device,

        ingested_at,
        batch_id

    FROM deduped
    WHERE rn = 1

)

SELECT * FROM final