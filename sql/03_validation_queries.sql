USE chatbi_mvp;

-- 验证 1：按订单状态统计
SELECT
    order_status,
    COUNT(*) AS order_count,
    SUM(net_amount) AS total_net_amount
FROM sales_orders
GROUP BY order_status;

-- 验证 2：按产品线汇总收入
SELECT
    p.product_line,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(o.quantity) AS total_quantity,
    SUM(o.net_amount) AS total_revenue
FROM sales_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.order_status = 'completed'
GROUP BY p.product_line;

-- 验证 3：按区域汇总人民币收入（含汇率转换）
SELECT
    c.region,
    SUM(o.net_amount * er.rate_to_cny) AS revenue_rmb,
    COUNT(*) AS order_count
FROM sales_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN exchange_rates er
    ON o.order_date = er.rate_date
   AND o.currency = er.currency
WHERE o.order_status = 'completed'
GROUP BY c.region
ORDER BY revenue_rmb DESC;

-- 验证 4：产品线毛利计算
SELECT
    p.product_line,
    SUM(o.net_amount) AS revenue,
    SUM((p.material_cost + p.labor_cost) * o.quantity) AS product_cost,
    SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity) AS gross_profit,
    SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
      / SUM(o.net_amount) AS gross_margin_rate
FROM sales_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.order_status = 'completed'
GROUP BY p.product_line;

-- 验证 5：按月汇总费用
SELECT
    DATE_FORMAT(expense_date, '%Y-%m') AS month,
    SUM(rd_expense) AS total_rd,
    SUM(selling_expense) AS total_selling,
    SUM(admin_expense) AS total_admin,
    SUM(finance_expense) AS total_finance
FROM finance_expenses
GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
ORDER BY month;
