# Panduan Snapshot & Incremental — Cara Belajar + Cara Cerita di Interview

## Konsep dalam 1 kalimat

| Fitur | Untuk apa | Analogi |
|---|---|---|
| **dbt snapshot** | Track perubahan data di source sistem | Foto profil yang disimpan setiap ada perubahan |
| **Incremental model** | Hanya proses data baru, tidak rebuild semua | Baca koran hari ini saja, bukan dari edisi pertama |

---

## Bagian 1: dbt Snapshot

### Mengapa perlu snapshot?

Sistem sumber (aplikasi, ERP, CRM) biasanya hanya simpan **state terbaru**.
Kalau customer ganti kota dari Jakarta ke Surabaya — data lama hilang, diganti.

Di data warehouse, kita butuh tahu **histori** — kota mana saat order ini dibuat?
Segmen apa saat customer ini beli produk itu?

dbt snapshot menangkap perubahan sebelum hilang.

### Cara kerja step-by-step

```
Run 1 (batch 1 di DuckDB):
  Source: Budi | Jakarta | new | updated_at: 2023-01-05

  Snapshot result:
  customer_id | city    | segment | dbt_valid_from | dbt_valid_to | is_current
  1           | Jakarta | new     | 2023-01-05     | NULL         | true

─────────────────────────────────────────────────────────────────

Run 2 (batch 2 di DuckDB — Budi pindah ke Surabaya, naik jadi loyal):
  Source: Budi | Surabaya | loyal | updated_at: 2023-04-03

  Snapshot result:
  customer_id | city     | segment | dbt_valid_from | dbt_valid_to | is_current
  1           | Jakarta  | new     | 2023-01-05     | 2023-04-03   | false   ← ditutup
  1           | Surabaya | loyal   | 2023-04-03     | NULL         | true    ← baru

─────────────────────────────────────────────────────────────────

Run 3 (batch 3 — Budi churn):
  customer_id | city     | segment  | dbt_valid_from | dbt_valid_to | is_current
  1           | Jakarta  | new      | 2023-01-05     | 2023-04-03   | false
  1           | Surabaya | loyal    | 2023-04-03     | 2023-09-12   | false   ← ditutup
  1           | Surabaya | churned  | 2023-09-12     | NULL         | true    ← baru
```

### Cara jalankan (urut)

```bash
# Step 1 — generate raw source files
python raw_sources_for_snapshot.py

# Step 2 — load batch pertama ke DuckDB
python setup_snapshot_sources.py --batch=1

# Step 3 — snapshot pertama (initial state)
dbt snapshot

# Step 4 — load batch kedua (ada perubahan segmen & harga)
python setup_snapshot_sources.py --batch=2

# Step 5 — snapshot kedua (tangkap perubahan)
dbt snapshot

# Step 6 — load batch ketiga (ada churn)
python setup_snapshot_sources.py --batch=3

# Step 7 — snapshot ketiga
dbt snapshot

# Step 8 — lihat hasil
dbt run -s stg_customers_snapshot
```

### Query untuk verifikasi hasil snapshot

```sql
-- Lihat semua versi customer ID 1
SELECT customer_id, city, segment, dbt_valid_from, dbt_valid_to, is_current
FROM snapshots.snp_customers
WHERE customer_id = 1
ORDER BY dbt_valid_from;

-- Hitung berapa customer yang pernah berubah
SELECT
  CASE WHEN COUNT(*) > 1 THEN 'Pernah berubah' ELSE 'Tidak berubah' END as status,
  COUNT(DISTINCT customer_id) as n_customers
FROM snapshots.snp_customers
GROUP BY customer_id
-- lalu group lagi
;
```

---

## Bagian 2: Incremental Models

### Mengapa perlu incremental?

| Situasi | Table (rebuild semua) | Incremental |
|---|---|---|
| 1 juta baris, tambah 2.000/hari | Proses 1.002.000 baris tiap run | Proses 2.000 baris saja |
| BigQuery cost | Scan 1 juta baris = $5 | Scan 2.000 baris = $0.01 |
| Waktu run | 10 menit | 5 detik |

### 3 pola incremental yang ada di project ini

**Pola 1 — updated_at timestamp** (`fct_orders_incremental`)
```sql
-- Cocok untuk: data yang bisa di-UPDATE (status order berubah)
{% if is_incremental() %}
  WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

**Pola 2 — event_date dengan lookback** (`fct_events_incremental`)
```sql
-- Cocok untuk: append-only data tapi ada late-arriving
{% if is_incremental() %}
  WHERE event_date >= (
    SELECT DATEADD('day', -2, MAX(event_date)) FROM {{ this }}
  )
{% endif %}
```

**Pola 3 — composite unique_key** (`fct_revenue_daily_incremental`)
```sql
-- Cocok untuk: aggregasi harian yang perlu di-rebuild beberapa hari
-- unique_key = ['date_day', 'channel', 'shipping_city', ...]
-- dbt akan DELETE lalu INSERT untuk kombinasi yang berubah
```

### Cara jalankan

```bash
# Run biasa (incremental — hanya data baru)
dbt run -s fct_orders_incremental

# Full refresh (rebuild semua dari awal — pakai kalau schema berubah)
dbt run -s fct_orders_incremental --full-refresh

# Run semua incremental sekaligus
dbt run -s fct_orders_incremental fct_events_incremental fct_revenue_daily_incremental

# Build semuanya (run + test)
dbt build
```

### Kapan pakai --full-refresh?

- Pertama kali (tabel belum ada) → dbt otomatis full refresh
- Ada perubahan kolom di model (`on_schema_change='sync_all_columns'` handle ini)
- Data historis ada yang salah dan perlu diperbaiki semua
- Setelah update logic bisnis yang fundamental

---

## Cara cerita di interview

### Tentang Snapshot

> *"Di project ini, saya mensimulasikan situasi dimana sistem sumber hanya menyimpan state terbaru customer — tidak ada histori. Saya pakai dbt snapshot dengan strategi timestamp yang membaca kolom updated_at untuk mendeteksi perubahan. Hasilnya adalah SCD Type 2 yang dibangun otomatis — setiap kali customer ganti kota atau naik segmen, baris lama ditutup dengan dbt_valid_to dan baris baru dibuat. Dengan ini saya bisa menjawab pertanyaan point-in-time: customer ini tinggal di mana saat order ini dibuat?"*

### Tentang Incremental

> *"Saya punya dua strategi incremental berbeda tergantung karakteristik data. Untuk orders yang statusnya bisa berubah, saya filter berdasarkan updated_at dengan lookback 3 hari untuk memastikan tidak ada perubahan status yang terlewat. Untuk clickstream events yang append-only tapi kadang late-arriving, saya pakai lookback 2 hari berdasarkan event_date. Pendekatan ini mengurangi volume data yang diproses dari jutaan baris menjadi ribuan per run."*

---

## Checklist sebelum lanjut ke Phase 2

- [ ] `python raw_sources_for_snapshot.py` berhasil generate 6 CSV
- [ ] `dbt snapshot` berhasil 3x (batch 1, 2, 3)
- [ ] Query ke `snapshots.snp_customers` menunjukkan histori perubahan
- [ ] `dbt run -s fct_orders_incremental` berhasil
- [ ] `dbt run -s fct_orders_incremental` kedua kali — hanya proses baris baru
- [ ] `dbt run -s fct_orders_incremental --full-refresh` berhasil rebuild semua
- [ ] Semua test pass: `dbt test`
- [ ] Screenshot lineage graph dari `dbt docs serve`
