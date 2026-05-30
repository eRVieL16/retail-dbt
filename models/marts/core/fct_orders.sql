{{ 
  config(
    materialized = 'incremental',
    unique_key = 'order_id',
    incremental_strategy = 'delete+insert',
    on_schema_change = 'append_new_columns'
  ) 
}}

WITH source AS (

    SELECT *
    FROM {{ ref('int_orders_enriched') }}

    {% if is_incremental() %}
        WHERE CAST(updated_at AS TIMESTAMP) >= (
            -- SELECT MAX(updated_at) - INTERVAL 2 DAY FROM {{ this }}
            -- Ubah baris ini di fct_orders.sql
            SELECT MAX(CAST(updated_at AS TIMESTAMP)) - INTERVAL 2 DAY FROM {{ this }}
        )
    {% endif %}

),

final AS (

    SELECT
        {{ dbt_utils.generate_surrogate_key(['order_id']) }} AS order_sk,

        order_id,
        customer_id,
        customer_key,
        store_id,

        order_date,
        order_date_day,
        order_week,
        order_month,

        first_payment_date,
        minutes_to_payment,

        order_status,
        channel,
        shipping_city,

        customer_segment,
        customer_city,
        customer_gender,

        payment_methods_used,

        is_completed,
        is_bad_order,
        is_split_payment,
        has_late_payment,

        gross_amount,
        discount_total,
        net_amount,
        total_paid,

        updated_at,

        '{{ run_started_at }}'::timestamp AS dbt_loaded_at

    FROM source

)

SELECT * FROM final
