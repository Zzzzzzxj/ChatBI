-- ============================================================
-- 步骤 1：创建数据库并切换（如已存在则跳过创建）
-- ============================================================

CREATE DATABASE IF NOT EXISTS chatbi_mvp
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE chatbi_mvp;

-- ============================================================
-- 步骤 2：建表（支持重复执行）
-- ============================================================

-- 清理旧表（如存在）并关闭外键检查，避免删除顺序问题
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS sales_orders;
DROP TABLE IF EXISTS exchange_rates;
DROP TABLE IF EXISTS finance_expenses;
DROP TABLE IF EXISTS dim_products;
DROP TABLE IF EXISTS dim_customers;

SET FOREIGN_KEY_CHECKS = 1;

-- 创建数据表（先维度表，后事实表）

-- 1. 客户维度表
CREATE TABLE dim_customers (
    customer_id     INT PRIMARY KEY,
    customer_name   VARCHAR(100) NOT NULL,
    customer_type   VARCHAR(50),
    industry        VARCHAR(50),
    country         VARCHAR(50),
    region          VARCHAR(50)
);

-- 2. 产品维度表
CREATE TABLE dim_products (
    product_id      INT PRIMARY KEY,
    product_name    VARCHAR(100) NOT NULL,
    product_line    VARCHAR(50),
    category        VARCHAR(50),
    tech_route      VARCHAR(50),
    standard_cost   DECIMAL(10,2),
    material_cost   DECIMAL(10,2),
    labor_cost      DECIMAL(10,2)
);

-- 3. 销售订单表
CREATE TABLE sales_orders (
    order_id        BIGINT PRIMARY KEY,
    order_no        VARCHAR(50) UNIQUE,
    customer_id     INT,
    product_id      INT,
    region          VARCHAR(50),
    order_date      DATE,
    order_status    VARCHAR(20),
    quantity        DECIMAL(10,2),
    unit_price      DECIMAL(10,2),
    discount_amount DECIMAL(10,2),
    gross_amount    DECIMAL(12,2),
    net_amount      DECIMAL(12,2),
    currency        VARCHAR(10),
    FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES dim_products(product_id)
);

-- 4. 汇率表
CREATE TABLE exchange_rates (
    rate_date       DATE,
    currency        VARCHAR(10),
    rate_to_cny     DECIMAL(10,4),
    PRIMARY KEY (rate_date, currency)
);

-- 5. 费用表
CREATE TABLE finance_expenses (
    expense_id       BIGINT PRIMARY KEY,
    expense_date     DATE,
    department       VARCHAR(50),
    rd_expense       DECIMAL(12,2),
    selling_expense  DECIMAL(12,2),
    admin_expense    DECIMAL(12,2),
    finance_expense  DECIMAL(12,2),
    marketing_expense DECIMAL(12,2),
    logistics_expense DECIMAL(12,2),
    warranty_expense  DECIMAL(12,2)
);

