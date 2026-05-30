WITH source AS (

    SELECT * FROM {{ source('raw', 'raw_returns') }}

),

cleaned AS (

    SELECT
        return_ref,
        order_id,

        CAST(return_date AS DATE) AS return_date,

        -- normalize text
        -- DuckDB tidak punya INITCAP — normalize ke lowercase dulu,
        -- capitalize huruf pertama dengan concat + upper + substr
        CASE
            WHEN reason IS NULL THEN NULL
            ELSE CONCAT(
                UPPER(LEFT(LOWER(TRIM(reason)), 1)),
                LOWER(SUBSTR(TRIM(reason), 2))
            )
        END AS reason_clean,

        -- currency normalization
        {{ to_idr('refund_amount', 'currency') }}     as refund_amount_idr,

        currency,

            -- data quality flag: apakah record ini di-convert dari USD
        upper(currency) != 'IDR'                      as was_currency_converted,

        ingested_at

    FROM source

)

SELECT * FROM cleaned