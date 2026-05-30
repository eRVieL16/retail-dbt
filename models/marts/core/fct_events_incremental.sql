{{ 
  config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='delete+insert',
    on_schema_change='append_new_columns'
  ) 
}}

{% set lookback_days = var('events_lookback_days', 3) %}

WITH source AS (

    SELECT *
    FROM {{ ref('stg_events') }}

    {% if is_incremental() %}
        WHERE CAST(event_ts AS DATE) >= (
            SELECT MAX(CAST(event_ts AS DATE)) - INTERVAL '{{ lookback_days }} DAY'
            FROM {{ this }}
        )
    {% endif %}

),

final AS (

    SELECT
        event_id,
        session_id,
        customer_id,
        product_id,
        event_type,

        event_ts,
        CAST(event_ts AS DATE)                  AS event_date,
        EXTRACT(hour FROM event_ts)::integer    AS event_hour,

        channel,
        device,

        funnel_stage,
        ingested_at,
        batch_id,

        '{{ run_started_at }}'::timestamp       AS dbt_loaded_at

    FROM source

)

SELECT * FROM final
