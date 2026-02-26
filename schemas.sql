
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
CREATE TABLE emp_details (
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
CREATE TABLE salary_details (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    org_id CHAR(36) NOT NULL,

    base_salary INT DEFAULT 0,
    agp INT DEFAULT 0,
    da INT DEFAULT 0,
    dp INT DEFAULT 0,
    hra INT DEFAULT 0,
    tra INT DEFAULT 0,
    cla INT DEFAULT 0,
    pt INT DEFAULT 0,

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