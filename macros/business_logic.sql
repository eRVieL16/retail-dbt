-- macros/business_logic.sql
-- ==========================
-- All business logic constants are centralised here and overridable via
-- dbt vars. This means:
--   1. No code changes needed to adjust thresholds — just pass --vars
--   2. The same macro works in dev (loose thresholds) vs prod (strict)
--   3. Elementary / dbt tests can reference the macro to stay in sync


-- ---------------------------------------------------------------------------
-- RFM Scoring Thresholds
-- ---------------------------------------------------------------------------
-- Usage:
--   {{ rfm_recency_score('days_since_last_order') }}
--   Override: dbt build --vars '{"rfm_recency_days_active": 30}'

{% macro rfm_recency_score(days_col) %}
    case
        when {{ days_col }} <= {{ var('rfm_recency_days_active',    30) }} then 5
        when {{ days_col }} <= {{ var('rfm_recency_days_recent',    60) }} then 4
        when {{ days_col }} <= {{ var('rfm_recency_days_moderate',  90) }} then 3
        when {{ days_col }} <= {{ var('rfm_recency_days_lapsed',   180) }} then 2
        else 1
    end
{% endmacro %}


{% macro rfm_frequency_score(orders_col) %}
    case
        when {{ orders_col }} >= {{ var('rfm_freq_champion',   10) }} then 5
        when {{ orders_col }} >= {{ var('rfm_freq_loyal',       6) }} then 4
        when {{ orders_col }} >= {{ var('rfm_freq_potential',   3) }} then 3
        when {{ orders_col }} >= {{ var('rfm_freq_new',         2) }} then 2
        else 1
    end
{% endmacro %}


{% macro rfm_monetary_score(amount_col) %}
    case
        when {{ amount_col }} >= {{ var('rfm_monetary_champion',   5000000) }} then 5
        when {{ amount_col }} >= {{ var('rfm_monetary_loyal',      2000000) }} then 4
        when {{ amount_col }} >= {{ var('rfm_monetary_potential',  1000000) }} then 3
        when {{ amount_col }} >= {{ var('rfm_monetary_new',         500000) }} then 2
        else 1
    end
{% endmacro %}


{% macro rfm_segment_label(rfm_score_col) %}
    case
        when {{ rfm_score_col }} >= {{ var('rfm_segment_champion_min',   13) }} then 'Champion'
        when {{ rfm_score_col }} >= {{ var('rfm_segment_loyal_min',      10) }} then 'Loyal Customer'
        when {{ rfm_score_col }} >= {{ var('rfm_segment_potential_min',   7) }} then 'Potential Loyalist'
        when {{ rfm_score_col }} >= {{ var('rfm_segment_atrisk_min',      4) }} then 'At Risk'
        else 'Lost'
    end
{% endmacro %}


-- ---------------------------------------------------------------------------
-- Currency Conversion
-- ---------------------------------------------------------------------------
-- Usage:
--   {{ to_idr('refund_amount', 'currency') }}
-- Override exchange rate at run time:
--   dbt build --vars '{"usd_to_idr_rate": 16200}'

{% macro to_idr(amount_col, currency_col) %}
    case
        when upper({{ currency_col }}) = 'USD'
            then {{ amount_col }} * {{ var('usd_to_idr_rate', 15800) }}
        when upper({{ currency_col }}) = 'SGD'
            then {{ amount_col }} * {{ var('sgd_to_idr_rate', 11900) }}
        else {{ amount_col }}   -- already IDR, pass through
    end
{% endmacro %}


-- ---------------------------------------------------------------------------
-- Generation Cohort
-- ---------------------------------------------------------------------------
-- Centralise generational boundaries so dim_customers_scd and any future
-- model stay in sync. Boundaries are vars so they can be adjusted without
-- touching SQL.

{% macro generation_cohort(birth_year_col) %}
    case
        when {{ birth_year_col }} >= {{ var('gen_z_birth_year_min',        1997) }} then 'Gen Z'
        when {{ birth_year_col }} >= {{ var('millennial_birth_year_min',   1981) }} then 'Millennial'
        when {{ birth_year_col }} >= {{ var('gen_x_birth_year_min',        1965) }} then 'Gen X'
        when {{ birth_year_col }} >= {{ var('boomer_birth_year_min',       1946) }} then 'Boomer'
        else 'Silent Generation'
    end
{% endmacro %}


-- ---------------------------------------------------------------------------
-- Audit Helpers
-- ---------------------------------------------------------------------------

{% macro is_late_arriving(payment_ts_col, order_ts_col, grace_minutes=0) %}
    {{ payment_ts_col }} < {{ order_ts_col }}
    {%- if grace_minutes > 0 %}
        - INTERVAL '{{ grace_minutes }} minutes'
    {%- endif %}
{% endmacro %}