{% snapshot snp_products %}

{{
  config(
    target_schema = 'snapshots',
    unique_key    = 'product_id',
    strategy      = 'timestamp',
    updated_at    = 'updated_at',
    invalidate_hard_deletes = True
  )
}}

/*
  Snapshot produk — track perubahan harga dari waktu ke waktu.

  Kenapa ini penting untuk analisis:
    Tanpa snapshot: kamu tidak tahu harga produk saat order dibuat.
    Dengan snapshot: kamu bisa JOIN order (di tanggal tertentu) dengan
    versi harga yang berlaku saat itu. Ini yang disebut "point-in-time join."

  Contoh query point-in-time (setelah snapshot berjalan):
    SELECT
      o.order_id,
      o.order_date,
      p.selling_price as price_at_time_of_order,
      p.dbt_valid_from,
      p.dbt_valid_to
    FROM fct_orders o
    JOIN snapshots.snp_products p
      ON o.product_id = p.product_id
     AND o.order_date >= p.dbt_valid_from
     AND (o.order_date < p.dbt_valid_to OR p.dbt_valid_to IS NULL)
*/

select
    product_id,
    sku,
    product_name,
    category,
    brand,
    cost_price,
    selling_price,
    weight_gram,
    is_active,
    updated_at

from {{ source('raw', 'raw_products_current') }}

{% endsnapshot %}
