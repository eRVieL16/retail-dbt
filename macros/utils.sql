{% macro cents_to_idr(column_name) %}
    round(cast({{ column_name }} as double) / 100.0, 2)
{% endmacro %}


{% macro safe_divide(numerator, denominator) %}
    case
        when {{ denominator }} = 0 or {{ denominator }} is null
        then null
        else round(cast({{ numerator }} as double) / cast({{ denominator }} as double), 4)
    end
{% endmacro %}


{% macro date_spine_cte(start_date, end_date) %}
    generate_series(
        '{{ start_date }}'::date,
        '{{ end_date }}'::date,
        interval '1 day'
    )::date
{% endmacro %}


{#
  Macro: assert_row_count
  Dipakai di analyses/ untuk sanity check jumlah baris
  Contoh: {{ assert_row_count(ref('fct_orders'), 4000) }}
#}
{% macro assert_row_count(model, expected_min) %}
    select
        '{{ model }}' as model_name,
        count(*) as actual_rows,
        {{ expected_min }} as expected_min_rows,
        case when count(*) >= {{ expected_min }} then 'PASS' else 'FAIL' end as result
    from {{ model }}
{% endmacro %}
