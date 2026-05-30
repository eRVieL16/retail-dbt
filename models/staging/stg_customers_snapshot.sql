-- stg_customers_snapshot
{{
  config(
    materialized = 'view',
    description  = 'Customer SCD Type 2 dari dbt snapshot — sudah ada dbt_valid_from/to otomatis'
  )
}}

/*
  Model ini membaca DARI SNAPSHOT — bukan dari raw CSV.
  Perbedaan dengan stg_customers (yang baca dari dim_customers di generator):
    - stg_customers      → SCD sudah ada dari generator (untuk latihan baca SCD)
    - stg_customers_snapshot → SCD dibuat oleh dbt snapshot (situasi nyata)

  Di production, kamu hanya pakai SALAH SATU. Keduanya ada di project ini
  supaya kamu bisa compare dan paham bedanya.
*/

with snapshot as (
    select * from {{ ref('snp_customers') }}
),

enriched as (
    select
        -- keys dari snapshot
        dbt_scd_id                                  as customer_version_key,
        customer_id,

        -- atribut
        full_name,
        email,
        phone,
        gender,
        cast(date_of_birth as date)                 as date_of_birth,
        city,
        segment,
        referral_code,
        is_active,

        -- SCD columns yang dbt generate otomatis
        dbt_valid_from                              as valid_from,
        dbt_valid_to                                as valid_to,
        case
            when dbt_valid_to is null then true
            else false
        end                                         as is_current,

        -- derived
        date_diff(
            'year',
            cast(date_of_birth as date),
            current_date
        )                                           as age_years,

        case
            when date_diff('year', cast(date_of_birth as date), current_date) < 25 then 'gen_z'
            when date_diff('year', cast(date_of_birth as date), current_date) < 40 then 'millennial'
            when date_diff('year', cast(date_of_birth as date), current_date) < 56 then 'gen_x'
            else 'boomer'
        end                                         as generation_cohort,

        -- berapa versi yang sudah ada untuk customer ini
        count(*) over (partition by customer_id)    as n_versions,

        -- apakah pernah churn
        bool_or(segment = 'churned') over (
            partition by customer_id
        )                                           as ever_churned,

        -- track perubahan segmen
        lag(segment) over (
            partition by customer_id
            order by dbt_valid_from
        )                                           as previous_segment,

        -- track perubahan kota
        lag(city) over (
            partition by customer_id
            order by dbt_valid_from
        )                                           as previous_city,

        dbt_updated_at

    from snapshot
),

change_flags as (
    select
        *,
        case
            when previous_segment is not null
             and previous_segment != segment
            then true else false
        end                 as segment_changed,

        case
            when previous_city is not null
             and previous_city != city
            then true else false
        end                 as city_changed

    from enriched
)

select * from change_flags
