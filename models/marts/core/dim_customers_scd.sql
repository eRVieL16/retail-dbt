{{
  config(
    materialized='table',
    description='Customer dimension dengan full SCD Type 2 history — production-ready'
  )
}}

select
    customer_key,
    customer_id,
    full_name,
    email,
    phone,
    gender,
    date_of_birth,

    -- derive age dari date_of_birth — tidak tersedia di staging
    date_diff('year', cast(date_of_birth as date), current_date) as age_years,

    -- generation cohort berdasarkan tahun lahir
    {{ generation_cohort('extract(year from CAST(date_of_birth AS DATE))') }} as generation_cohort,

    city,
    segment,
    referral_code,
    valid_from,
    valid_to,
    is_current,
    has_scd_overlap,   -- data quality flag
    updated_at,

    -- useful untuk downstream filters
    case
        when valid_to is null then cast('9999-12-31' as date)
        else cast(valid_to as date)
    end as valid_to_date_safe

from {{ ref('stg_customers') }}
