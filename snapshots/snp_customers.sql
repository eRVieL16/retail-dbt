{% snapshot snp_customers %}

{{
  config(
    target_schema = 'snapshots',
    unique_key    = 'customer_id',
    strategy      = 'timestamp',
    updated_at    = 'updated_at',
    invalidate_hard_deletes = True
  )
}}

/*
  Snapshot ini membaca raw_customers_current — tabel "flat" yang hanya
  simpan state terbaru (tidak ada histori).

  Setiap kali dbt snapshot dijalankan, dbt akan:
    1. Baca semua baris dari source
    2. Bandingkan dengan snapshot terakhir via updated_at
    3. Kalau ada perubahan → tutup baris lama (isi dbt_valid_to)
                           → buat baris baru (dbt_valid_from = sekarang)
    4. Kalau tidak berubah → biarkan

  Kolom yang dbt tambahkan otomatis:
    dbt_scd_id      — surrogate key unik per versi
    dbt_updated_at  — kapan snapshot ini diambil
    dbt_valid_from  — mulai berlaku
    dbt_valid_to    — NULL = current record, ada isi = sudah expired
    dbt_is_active   — True kalau current (hanya ada kalau invalidate_hard_deletes=True)

  Analogi:
    Bayangkan kamu foto halaman buku setiap hari.
    Kalau ada tulisan yang berubah, kamu simpan foto lama DAN foto baru.
    Snapshot = sistem yang otomatis foto dan simpan semua versi.
*/

select
    customer_id,
    full_name,
    email,
    phone,
    gender,
    date_of_birth,
    city,
    segment,
    referral_code,
    is_active,
    updated_at

from {{ source('raw', 'raw_customers_current') }}

{% endsnapshot %}
