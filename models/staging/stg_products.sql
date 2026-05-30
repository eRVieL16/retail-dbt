-- stg_products
{{
  config(
    materialized='view',
    description='SCD Type 2 products — harga berubah, track margin per versi'
  )
}}

with source as (
    select * from {{ source('raw', 'dim_products') }}
),

typed as (
    select
        cast(product_key as integer)      as product_key,
        cast(product_id as integer)       as product_id,
        trim(sku)                         as sku,
        trim(product_name)                as product_name,
        trim(category)                    as category,
        trim(brand)                       as brand,
        cast(cost_price as double)        as cost_price,
        cast(selling_price as double)     as selling_price,
        cast(weight_gram as integer)      as weight_gram,
        cast(is_active as boolean)        as is_active,
        cast(valid_from as timestamp)     as valid_from,
        cast(valid_to as timestamp)       as valid_to,
        cast(is_current as boolean)       as is_current,
        cast(updated_at as timestamp)     as updated_at,

        -- margin metrics per versi harga
        round(cast(selling_price as double) - cast(cost_price as double), 2)
                                          as gross_margin_idr,
        round(
            (cast(selling_price as double) - cast(cost_price as double))
            / nullif(cast(selling_price as double), 0),
            4
        )                                 as gross_margin_pct,

        case
            when cast(selling_price as double) < 100000  then 'budget'
            when cast(selling_price as double) < 500000  then 'mid_range'
            when cast(selling_price as double) < 1500000 then 'premium'
            else 'luxury'
        end                               as price_tier,

        -- reprice tracking
        lag(cast(selling_price as double)) over (
            partition by product_id order by valid_from
        )                                 as previous_selling_price

    from source
),

with_reprice as (
    select
        *,
        case
            when previous_selling_price is not null
            then round(
                (selling_price - previous_selling_price) / previous_selling_price,
                4
            )
            else null
        end as price_change_pct
    from typed
)

select * from with_reprice
