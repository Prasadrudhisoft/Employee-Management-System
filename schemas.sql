
-- =========================================
-- USERS TABLE
-- =========================================
CREATE TABLE users (
    id CHAR(36) PRIMARY KEY,
    Name VARCHAR(200) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Password VARCHAR(500) NOT NULL,
    Role VARCHAR(50) NOT NULL,
    Profile_img VARCHAR(255),
    Status ENUM('Active','Inactive') DEFAULT 'Active',
    Contact MEDIUMTEXT,
    org_id CHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by CHAR(36),
    org_name VARCHAR(200) NOT NULL,

    INDEX idx_users_org (org_id),
    INDEX idx_users_role (role)
) ENGINE=InnoDB;


-- =========================================
-- DEPARTMENTS TABLE
-- =========================================
CREATE TABLE departments (
    id CHAR(36) PRIMARY KEY,
    org_id CHAR(36) NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    created_by CHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_departments_org
        FOREIGN KEY (org_id) REFERENCES users(org_id)
        ON DELETE CASCADE,

    INDEX idx_departments_org (org_id)
) ENGINE=InnoDB;


-- =========================================
-- EMPLOYEE DETAILS TABLE
-- =========================================
CREATE TABLE emp_detailes (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    org_id CHAR(36) NOT NULL,
    department_id CHAR(36),
    address VARCHAR(300),
    designation VARCHAR(200),
    join_date DATE,

    CONSTRAINT fk_emp_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_emp_department
        FOREIGN KEY (department_id) REFERENCES departments(id)
        ON DELETE SET NULL,

    INDEX idx_emp_user (user_id),
    INDEX idx_emp_org (org_id),
    INDEX idx_emp_department (department_id)
) ENGINE=InnoDB;


-- =========================================
-- SALARY DETAILS TABLE
-- =========================================
CREATE TABLE salary_detailes (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    org_id CHAR(36) NOT NULL,

    base_salary INT DEFAULT 0 NULL,
    agp INT DEFAULT 0 NULL,
    da INT DEFAULT 0 NULL,
    dp INT DEFAULT 0 NULL,
    hra INT DEFAULT 0 NULL,
    tra INT DEFAULT 0 NULL,
    cla INT DEFAULT 0 NULL,
    pt INT DEFAULT 0 NULL,

    bank_acc_no VARCHAR(100),
    ifsc_code VARCHAR(20),
    bank_name VARCHAR(200),
    bank_address VARCHAR(200),

    created_by CHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_salary_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX idx_salary_user (user_id),
    INDEX idx_salary_org (org_id)
) ENGINE=InnoDB;


SET FOREIGN_KEY_CHECKS = 1;

-- =========================================
-- END OF FILE
-- =========================================

CREATE TABLE staff_salary_record(
    id CHAR(36) NOT NULL PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    org_id CHAR(36) NOT NULL,
    adj_base DECIMAL(10,2),
    adj_agp DECIMAL(10,2),
    adj_da DECIMAL(10,2), NULL
    adj_dp DECIMAL(10,2),
    adj_hra DECIMAL(10,2),
    adj_tra DECIMAL(10,2),
    adj_cla DECIMAL(10,2),
    pt DECIMAL(10,2) DEFAULT 0.00,
    pf DECIMAL(10,2) DEFAULT 0.00,
    other_deduction DECIMAL(10,2) DEFAULT 0.00,
    absent_days_deduction DECIMAL(10,2) DEFAULT 0.00,
    gross_salary DECIMAL(10,2) NOT NULL,
    net_salary DECIMAL(10,2) NOT NULL,
    salary_month varchar(200),
    salary_date DATE NOT NULL,
    created_by CHAR(36),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


--################ For leave management system ####################

CREATE TABLE IF NOT EXISTS leave_types (
    id            VARCHAR(36)   PRIMARY KEY,
    org_id        VARCHAR(36)   NOT NULL,
    name          VARCHAR(80)   NOT NULL,        -- e.g. Casual Leave, Sick Leave
    total_days    DECIMAL(5,1)  NOT NULL,         -- e.g. 12.0
    description   VARCHAR(255)  DEFAULT NULL,
    is_active     TINYINT(1)    DEFAULT 1,        -- soft delete
    created_by    VARCHAR(36)   DEFAULT NULL,
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lt_org (org_id)
);

-- 2. Leave Balances (auto-created per employee × leave type)
CREATE TABLE IF NOT EXISTS leave_balances (
    id              VARCHAR(36)   PRIMARY KEY,
    user_id         VARCHAR(36)   NOT NULL,
    org_id          VARCHAR(36)   NOT NULL,
    leave_type_id   VARCHAR(36)   NOT NULL,
    total_days      DECIMAL(5,1)  NOT NULL,
    used_days       DECIMAL(5,1)  DEFAULT 0.0,
    remaining_days  DECIMAL(5,1)  NOT NULL,
    year            YEAR          NOT NULL DEFAULT (YEAR(CURDATE())),
    updated_at      DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_balance (user_id, leave_type_id, year),
    INDEX idx_lb_org  (org_id),
    INDEX idx_lb_user (user_id)
);

-- 3. Leave Requests (Employee applies)
CREATE TABLE IF NOT EXISTS leave_requests (
    id              VARCHAR(36)   PRIMARY KEY,
    user_id         VARCHAR(36)   NOT NULL,       -- employee
    org_id          VARCHAR(36)   NOT NULL,
    leave_type_id   VARCHAR(36)   NOT NULL,
    from_date       DATE          NOT NULL,
    to_date         DATE          NOT NULL,
    leave_days      DECIMAL(5,1)  NOT NULL,        -- 0.5 for half-day
    day_type        ENUM('Full Day','Half Day')    DEFAULT 'Full Day',
    reason          TEXT          DEFAULT NULL,
    status          ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    manager_comment TEXT          DEFAULT NULL,
    reviewed_by     VARCHAR(36)   DEFAULT NULL,    -- manager id
    reviewed_at     DATETIME      DEFAULT NULL,
    created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lr_org    (org_id),
    INDEX idx_lr_user   (user_id),
    INDEX idx_lr_status (status)
);

-- 4. Holidays (Manager manages)
CREATE TABLE IF NOT EXISTS holidays (
    id            VARCHAR(36)   PRIMARY KEY,
    org_id        VARCHAR(36)   NOT NULL,
    name          VARCHAR(120)  NOT NULL,
    holiday_date  DATE          NOT NULL,
    description   VARCHAR(255)  DEFAULT NULL,
    created_by    VARCHAR(36)   DEFAULT NULL,
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_holiday (org_id, holiday_date),
    INDEX idx_hol_org (org_id)
);

