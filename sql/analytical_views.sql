CREATE OR REPLACE VIEW v_monthly_category_kpi AS
WITH monthly_agg AS (
    SELECT
        DATE_TRUNC('month', f.sale_date)::date AS report_month,
        p.category,
        r.city,
        COUNT(f.order_id) AS orders_count,
        SUM(f.quantity) AS total_units,
        ROUND(SUM(f.net_revenue)::numeric, 2) AS net_revenue,
        ROUND((AVG(f.discount_pct) * 100)::numeric, 2) AS avg_discount_pct
    FROM fact_sales f
    JOIN dim_products p ON f.product_id = p.product_id
    JOIN dim_regions r ON f.region_id = r.region_id
    GROUP BY 1, 2, 3
)
SELECT
    report_month,
    category,
    city,
    orders_count,
    total_units,
    net_revenue,
    avg_discount_pct,
    LAG(net_revenue) OVER (PARTITION BY category, city ORDER BY report_month) AS prev_month_revenue,
    ROUND(
        (
            (net_revenue - LAG(net_revenue) OVER (PARTITION BY category, city ORDER BY report_month))
            / NULLIF(LAG(net_revenue) OVER (PARTITION BY category, city ORDER BY report_month), 0) * 100
        )::numeric,
        2
    ) AS mom_growth_pct,
    RANK() OVER (PARTITION BY report_month ORDER BY net_revenue DESC) AS city_category_rank
FROM monthly_agg;
