WITH source AS (

    SELECT * FROM {{ source('raw', 'dim_customers') }}

),

scd_check AS (

    SELECT
        *,

        LEAD(valid_from) OVER (
            PARTITION BY customer_id
            ORDER BY valid_from
        ) AS next_valid_from

    FROM source

),

final AS (

    SELECT
        *,

        -- overlap detection
        CASE
            WHEN next_valid_from < valid_to THEN TRUE
            ELSE FALSE
        END AS has_scd_overlap

    FROM scd_check

)

SELECT * FROM final