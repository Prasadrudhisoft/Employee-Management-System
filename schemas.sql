-- =========================================
-- SCHEMA.SQL — FULL PRODUCTION SCHEMA
-- All tables, indexes, and constraints
-- =========================================

SET FOREIGN_KEY_CHECKS = 0;


-- =========================================
-- users TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS users (
    id          CHAR(36)        PRIMARY KEY,
    Name        VARCHAR(200)    NOT NULL,
    Email       VARCHAR(150)    NOT NULL UNIQUE,
    Password    VARCHAR(500)    NOT NULL,
    Role        VARCHAR(50)     NOT NULL,
    Profile_img VARCHAR(255),
    Status      VARCHAR(50),
    Contact     MEDIUMTEXT,
    org_id      CHAR(36),
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    created_by  CHAR(36),
    org_name    VARCHAR(200)    NOT NULL,

    -- Single column indexes
    INDEX idx_users_org    (org_id),
    INDEX idx_users_role   (Role),
    INDEX idx_users_email  (Email),              -- ← NEW: login query on every request

    -- Composite index covers all common query patterns:
    -- WHERE org_id = ? AND role = 'EMP' AND status = 'Active'
    -- WHERE org_id = ? AND role = 'Manager'
    -- WHERE org_id = ? AND role != 'Admin'
    INDEX idx_users_org_role_status (org_id, Role, Status)  -- ← NEW
) ENGINE=InnoDB;


-- =========================================
-- DEPARTMENTS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS departments (
    id              CHAR(36)        PRIMARY KEY,
    org_id          CHAR(36)        NOT NULL,
    department_name VARCHAR(100)    NOT NULL,
    created_by      CHAR(36),
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_departments_org
        FOREIGN KEY (org_id) REFERENCES users(org_id)
        ON DELETE CASCADE,

    INDEX idx_departments_org (org_id)
) ENGINE=InnoDB;


-- =========================================
-- EMPLOYEE DETAILS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS emp_detailes (
    id            CHAR(36)        PRIMARY KEY,
    user_id       CHAR(36)        NOT NULL,
    org_id        CHAR(36)        NOT NULL,
    department_id CHAR(36),
    address       VARCHAR(300),
    designation   VARCHAR(200),
    join_date     DATE,

    CONSTRAINT fk_emp_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_emp_department
        FOREIGN KEY (department_id) REFERENCES departments(id)
        ON DELETE SET NULL,

    INDEX idx_emp_user       (user_id),
    INDEX idx_emp_org        (org_id),
    INDEX idx_emp_department (department_id)
) ENGINE=InnoDB;


-- =========================================
-- SALARY DETAILS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS salary_detailes (
    id           CHAR(36)        PRIMARY KEY,
    user_id      CHAR(36)        NOT NULL,
    org_id       CHAR(36)        NOT NULL,

    base_salary  INT             DEFAULT 0 NULL,
    agp          INT             DEFAULT 0 NULL,
    da           INT             DEFAULT 0 NULL,
    dp           INT             DEFAULT 0 NULL,
    hra          INT             DEFAULT 0 NULL,
    tra          INT             DEFAULT 0 NULL,
    cla          INT             DEFAULT 0 NULL,
    pt           INT             DEFAULT 0 NULL,

    bank_acc_no  VARCHAR(100),
    ifsc_code    VARCHAR(20),
    bank_name    VARCHAR(200),
    bank_address VARCHAR(200),

    created_by   CHAR(36),
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_salary_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX idx_salary_user (user_id),
    INDEX idx_salary_org  (org_id)
) ENGINE=InnoDB;


-- =========================================
-- STAFF SALARY RECORD TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS staff_salary_record (
    id                      CHAR(36)        NOT NULL PRIMARY KEY,
    user_id                 CHAR(36)        NOT NULL,
    org_id                  CHAR(36)        NOT NULL,

    adj_base                DECIMAL(10,2),
    adj_agp                 DECIMAL(10,2),
    adj_da                  DECIMAL(10,2) NULL,      -- ← FIXED: NULL was on wrong line
    adj_dp                  DECIMAL(10,2),
    adj_hra                 DECIMAL(10,2),
    adj_tra                 DECIMAL(10,2),
    adj_cla                 DECIMAL(10,2),
    pt                      DECIMAL(10,2)   DEFAULT 0.00,
    pf                      DECIMAL(10,2)   DEFAULT 0.00,
    other_deduction         DECIMAL(10,2)   DEFAULT 0.00,
    absent_days_deduction   DECIMAL(10,2)   DEFAULT 0.00,
    gross_salary            DECIMAL(10,2)   NOT NULL,
    net_salary              DECIMAL(10,2)   NOT NULL,
    salary_month            VARCHAR(200),
    salary_date             DATE            NOT NULL,
    created_by              CHAR(36),
    created_date            TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    -- ← NEW: all three indexes missing from original
    INDEX idx_ssr_user  (user_id),
    INDEX idx_ssr_org   (org_id),
    INDEX idx_ssr_month (salary_month)
) ENGINE=InnoDB;


-- =========================================
-- LEAVE TYPES TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS leave_types (
    id          VARCHAR(36)     PRIMARY KEY,
    org_id      VARCHAR(36)     NOT NULL,
    name        VARCHAR(80)     NOT NULL,
    total_days  DECIMAL(5,1)    NOT NULL,
    description VARCHAR(255)    DEFAULT NULL,
    is_active   TINYINT(1)      DEFAULT 1,
    created_by  VARCHAR(36)     DEFAULT NULL,
    created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_lt_org (org_id)
) ENGINE=InnoDB;


-- =========================================
-- LEAVE BALANCES TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS leave_balances (
    id              VARCHAR(36)     PRIMARY KEY,
    user_id         VARCHAR(36)     NOT NULL,
    org_id          VARCHAR(36)     NOT NULL,
    leave_type_id   VARCHAR(36)     NOT NULL,
    total_days      DECIMAL(5,1)    NOT NULL,
    used_days       DECIMAL(5,1)    DEFAULT 0.0,
    remaining_days  DECIMAL(5,1)    NOT NULL,
    year            YEAR            NOT NULL DEFAULT (YEAR(CURDATE())),
    updated_at      DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- UNIQUE KEY acts as index — covers all balance lookups:
    -- WHERE user_id = ? AND leave_type_id = ? AND year = ?
    UNIQUE KEY uq_balance   (user_id, leave_type_id, year),
    INDEX idx_lb_org        (org_id),
    INDEX idx_lb_user       (user_id)
) ENGINE=InnoDB;


-- =========================================
-- LEAVE REQUESTS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS leave_requests (
    id              VARCHAR(36)     PRIMARY KEY,
    user_id         VARCHAR(36)     NOT NULL,
    org_id          VARCHAR(36)     NOT NULL,
    leave_type_id   VARCHAR(36)     NOT NULL,
    from_date       DATE            NOT NULL,
    to_date         DATE            NOT NULL,
    leave_days      DECIMAL(5,1)    NOT NULL,
    day_type        ENUM('Full Day','Half Day') DEFAULT 'Full Day',
    reason          TEXT            DEFAULT NULL,
    status          ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    manager_comment TEXT            DEFAULT NULL,
    reviewed_by     VARCHAR(36)     DEFAULT NULL,
    reviewed_at     DATETIME        DEFAULT NULL,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_lr_org         (org_id),
    INDEX idx_lr_user        (user_id),
    INDEX idx_lr_status      (status),

    -- ← NEW: _has_overlap() runs on every leave application
    -- WHERE user_id = ? AND status IN ('Pending','Approved') AND from_date <= ? AND to_date >= ?
    INDEX idx_lr_user_status (user_id, status)
) ENGINE=InnoDB;


-- =========================================
-- HOLIDAYS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS holidays (
    id           VARCHAR(36)     PRIMARY KEY,
    org_id       VARCHAR(36)     NOT NULL,
    name         VARCHAR(120)    NOT NULL,
    holiday_date DATE            NOT NULL,
    description  VARCHAR(255)    DEFAULT NULL,
    created_by   VARCHAR(36)     DEFAULT NULL,
    created_at   DATETIME        DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_holiday (org_id, holiday_date),
    INDEX idx_hol_org     (org_id)
) ENGINE=InnoDB;


-- =========================================
-- CONTACTS TABLE
-- =========================================
CREATE TABLE IF NOT EXISTS contacts (
    id         VARCHAR(100)    PRIMARY KEY,
    name       VARCHAR(200),
    email      VARCHAR(100),
    subject    VARCHAR(200),
    message    VARCHAR(500),
    created_at TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    is_read    TINYINT(1)      DEFAULT 0,

    -- ← NEW: for admin filtering unread messages
    INDEX idx_contacts_is_read (is_read),
    INDEX idx_contacts_email   (email)
) ENGINE=InnoDB;


SET FOREIGN_KEY_CHECKS = 1;

-- =========================================
-- END OF FILE
-- =========================================