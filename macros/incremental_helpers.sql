/*
  Macro: get_max_timestamp
  ─────────────────────────
  Ambil max timestamp dari tabel yang sedang di-build (this).
  Dipakai di incremental models sebagai lower bound filter.

  Contoh pakai:
    WHERE updated_at > {{ get_max_timestamp('updated_at') }}
*/
{% macro get_max_timestamp(timestamp_column) %}
    (
        select
            coalesce(
                max({{ timestamp_column }}),
                '1970-01-01'::timestamp    -- fallback kalau tabel masih kosong
            )
        from {{ this }}
    )
{% endmacro %}


/*
  Macro: is_full_refresh
  ─────────────────────────
  Return true kalau run pakai --full-refresh flag.
  Berguna untuk logging atau conditional logic.
*/
{% macro is_full_refresh() %}
    {% if flags.FULL_REFRESH %}
        true
    {% else %}
        false
    {% endif %}
{% endmacro %}


/*
  Macro: incremental_filter
  ─────────────────────────
  Wrapper standar untuk filter incremental — dengan lookback buffer.
  Lookback default dari var incremental_lookback_days (default 3).

  Contoh pakai di model:
    {{ incremental_filter('updated_at') }}
    → menghasilkan: WHERE updated_at > (max - 3 hari)

  Kenapa perlu lookback?
    Bayangkan order dibuat tgl 10, status berubah tgl 12.
    Kalau kita filter tepat dari tgl 12, kita ketinggalan update status tgl 10.
    Lookback 3 hari = kita proses ulang tgl 10,11,12 di setiap run.
*/
{% macro incremental_filter(timestamp_column, lookback_days=none) %}
    {% if is_incremental() %}
        {% set days = lookback_days or var('incremental_lookback_days', 3) %}
        where CAST({{ timestamp_column }} AS TIMESTAMP) >= (
            select max(CAST({{ timestamp_column }} AS TIMESTAMP)) - interval '{{ days }}' day
            from {{ this }}
        )
    {% endif %}
{% endmacro %}


/*
  Macro: generate_date_spine
  ─────────────────────────
  Generate sequence tanggal dari start sampai end.
  Berguna untuk memastikan tidak ada tanggal yang kosong di revenue report.

  Contoh pakai di model:
    with all_dates as (
        {{ generate_date_spine('2023-01-01', '2024-12-31') }}
    )
*/
{% macro generate_date_spine(start_date, end_date) %}
    select
        unnest(
            generate_series(
                '{{ start_date }}'::date,
                '{{ end_date }}'::date,
                interval '1 day'
            )
        )::date as date_day
{% endmacro %}
