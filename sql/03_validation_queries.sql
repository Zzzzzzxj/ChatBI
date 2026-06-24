USE chatbi_mvp;

-- 1. 验证核心表数据量
SELECT 'dim_customers' AS table_name, COUNT(*) AS row_count FROM dim_customers
UNION ALL
SELECT 'dim_products' AS table_name, COUNT(*) AS row_count FROM dim_products
UNION ALL
SELECT 'exchange_rates' AS table_name, COUNT(*) AS row_count FROM exchange_rates
UNION ALL
SELECT 'sales_orders' AS table_name, COUNT(*) AS row_count FROM sales_orders
UNION ALL
SELECT 'finance_expenses' AS table_name, COUNT(*) AS row_count FROM finance_expenses;

-- 2. 已完成订单数量
SELECT COUNT(*) AS completed_order_count
FROM sales_orders
WHERE order_status = 'completed';

-- 3. 按客户类型统计订单数量
SELECT
    c.customer_type,
    COUNT(*) AS order_count
FROM sales_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'completed'
GROUP BY c.customer_type
ORDER BY order_count DESC;

-- 4. 按产品线统计不含税收入
SELECT
    p.product_line,
    SUM(o.net_amount) AS total_revenue
FROM sales_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.order_status = 'completed'
GROUP BY p.product_line
ORDER BY total_revenue DESC;

-- 5. 按区域统计人民币折算收入
SELECT
    o.region,
    SUM(o.net_amount * r.rate_to_cny) AS total_revenue_cny
FROM sales_orders o
JOIN exchange_rates r
  ON DATE_FORMAT(o.order_date, '%Y-%m-01') = r.rate_date
 AND o.currency = r.currency
WHERE o.order_status = 'completed'
GROUP BY o.region
ORDER BY total_revenue_cny DESC;

-- 6. 第一季度总费用
SELECT
    SUM(rd_expense + selling_expense + admin_expense + finance_expense) AS total_expense
FROM finance_expenses
WHERE expense_date >= '2026-01-01'
  AND expense_date < '2026-04-01';

