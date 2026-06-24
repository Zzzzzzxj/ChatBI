CREATE DATABASE IF NOT EXISTS chatbi_mvp
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE chatbi_mvp;

DROP TABLE IF EXISTS finance_expenses;
DROP TABLE IF EXISTS sales_orders;
DROP TABLE IF EXISTS exchange_rates;
DROP TABLE IF EXISTS dim_products;
DROP TABLE IF EXISTS dim_customers;

CREATE TABLE dim_customers (
    customer_id INT PRIMARY KEY COMMENT '客户ID',
    customer_name VARCHAR(100) NOT NULL COMMENT '客户名称',
    customer_type VARCHAR(50) NOT NULL COMMENT '客户类型：OEM整车厂 / 储能集成商 / 电网集团 / 工商业用户 / 换电运营商 / 经销商',
    industry VARCHAR(50) NOT NULL COMMENT '客户行业：交通 / 能源 / 工业 / 特种交通',
    country VARCHAR(50) NOT NULL COMMENT '具体国家，如 Germany',
    region VARCHAR(50) NOT NULL COMMENT '大区，如 欧洲、北美'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户维度表';

CREATE TABLE dim_products (
    product_id INT PRIMARY KEY COMMENT '产品ID',
    product_name VARCHAR(100) NOT NULL COMMENT '产品名称',
    product_line VARCHAR(50) NOT NULL COMMENT '产品线：动力电池-乘用车 / 动力电池-商用车 / 储能系统-电网级 / 储能系统-工商业 / 电池材料与回收',
    category VARCHAR(50) NOT NULL COMMENT '产品分类：高能量密度型 / 超快充型 / 混动专用型 / 低温适配型 / 商用车标准型 / 电网级储能型 / 工商业储能型',
    tech_route VARCHAR(50) NOT NULL COMMENT '技术路线：三元锂 / 磷酸铁锂 / 钠离子 / 固态电池',
    standard_cost DECIMAL(10,2) NOT NULL COMMENT '标准成本',
    material_cost DECIMAL(10,2) NOT NULL COMMENT '材料成本',
    labor_cost DECIMAL(10,2) NOT NULL COMMENT '人工成本'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品维度表';

CREATE TABLE exchange_rates (
    rate_date DATE NOT NULL COMMENT '日期',
    currency VARCHAR(10) NOT NULL COMMENT '币种',
    rate_to_cny DECIMAL(10,4) NOT NULL COMMENT '兑人民币汇率',
    PRIMARY KEY (rate_date, currency)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='汇率表';

CREATE TABLE sales_orders (
    order_id BIGINT PRIMARY KEY COMMENT '订单ID',
    order_no VARCHAR(50) NOT NULL UNIQUE COMMENT '订单编号',
    customer_id INT NOT NULL COMMENT '客户ID',
    product_id INT NOT NULL COMMENT '产品ID',
    region VARCHAR(50) NOT NULL COMMENT '销售区域',
    order_date DATE NOT NULL COMMENT '订单日期',
    order_status VARCHAR(20) NOT NULL COMMENT '订单状态：completed / cancelled / pending',
    quantity DECIMAL(10,2) NOT NULL COMMENT '数量（MWh 或套数）',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '单价（每 MWh 或每套价格，不含税）',
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '折扣金额',
    gross_amount DECIMAL(12,2) NOT NULL COMMENT '含税总额',
    net_amount DECIMAL(12,2) NOT NULL COMMENT '不含税收入（财务口径的销售额）',
    currency VARCHAR(10) NOT NULL COMMENT '币种',
    CONSTRAINT fk_sales_orders_customer
        FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id),
    CONSTRAINT fk_sales_orders_product
        FOREIGN KEY (product_id) REFERENCES dim_products(product_id),
    CONSTRAINT chk_sales_orders_status
        CHECK (order_status IN ('completed', 'cancelled', 'pending')),
    INDEX idx_sales_order_date (order_date),
    INDEX idx_sales_order_status (order_status),
    INDEX idx_sales_customer (customer_id),
    INDEX idx_sales_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售订单表';

CREATE TABLE finance_expenses (
    expense_id BIGINT PRIMARY KEY COMMENT '费用ID',
    expense_date DATE NOT NULL COMMENT '费用日期',
    department VARCHAR(50) NOT NULL COMMENT '部门',
    rd_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '研发费用（新能源企业研发投入大）',
    selling_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '销售费用',
    admin_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '管理费用',
    finance_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '财务费用',
    marketing_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '市场费用（属于销售费用子项）',
    logistics_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '物流费用',
    warranty_expense DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '质保费用',
    INDEX idx_finance_expense_date (expense_date),
    INDEX idx_finance_department (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='费用表';

