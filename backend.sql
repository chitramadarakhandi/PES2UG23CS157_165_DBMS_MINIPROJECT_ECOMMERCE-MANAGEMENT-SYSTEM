-- ================================
-- COMPLETE E-COMMERCE DATABASE
-- WITH ADMIN-ONLY UPDATE/DELETE
-- USING MYSQL USERS + TRIGGERS
-- ================================

DROP DATABASE IF EXISTS ecommerce_db;
CREATE DATABASE ecommerce_db;
USE ecommerce_db;

-- ================================
-- MAIN TABLES
-- ================================

CREATE TABLE users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin','customer') DEFAULT 'customer',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
  product_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  category VARCHAR(100),
  description TEXT,
  price DECIMAL(10,2) NOT NULL,
  stock_qty INT DEFAULT 0,
  image_path VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
  order_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  total_amount DECIMAL(10,2) DEFAULT 0.00,
  status ENUM('Pending','Confirmed','Shipped','Delivered','Cancelled') DEFAULT 'Pending',
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE order_details (
  order_detail_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE payments (
  payment_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  payment_mode VARCHAR(60),
  payment_status ENUM('Pending','Success','Failed') DEFAULT 'Pending',
  payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- ================================
-- AUDIT TABLE (LOG ADMIN ACTIONS)
-- ================================

CREATE TABLE product_audit (
  audit_id INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT,
  action VARCHAR(20),
  old_value TEXT,
  new_value TEXT,
  updated_by VARCHAR(100),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================
-- MYSQL USERS
-- ================================

CREATE USER 'eshop_admin'@'%' IDENTIFIED BY 'Admin123!';
GRANT ALL PRIVILEGES ON ecommerce_db.* TO 'eshop_admin'@'%';

CREATE USER 'eshop_user'@'%' IDENTIFIED BY 'User123!';
GRANT SELECT, INSERT ON ecommerce_db.* TO 'eshop_user'@'%';

FLUSH PRIVILEGES;

-- ================================
-- ADMIN-ONLY TRIGGERS
-- ================================

DELIMITER $$

-- BLOCK UPDATE for non-admin
CREATE TRIGGER trg_block_update
BEFORE UPDATE ON products
FOR EACH ROW
BEGIN
    IF CURRENT_USER() NOT LIKE 'eshop_admin%' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only admin can UPDATE products';
    END IF;
END$$

-- BLOCK DELETE for non-admin
CREATE TRIGGER trg_block_delete
BEFORE DELETE ON products
FOR EACH ROW
BEGIN
    IF CURRENT_USER() NOT LIKE 'eshop_admin%' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only admin can DELETE products';
    END IF;
END$$

-- LOG UPDATES by admin
CREATE TRIGGER trg_log_update
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    INSERT INTO product_audit(product_id, action, old_value, new_value, updated_by)
    VALUES (
        OLD.product_id,
        'UPDATE',
        CONCAT('Old name=', OLD.name, ', Old price=', OLD.price),
        CONCAT('New name=', NEW.name, ', New price=', NEW.price),
        CURRENT_USER()
    );
END$$

-- LOG DELETES by admin
CREATE TRIGGER trg_log_delete
AFTER DELETE ON products
FOR EACH ROW
BEGIN
    INSERT INTO product_audit(product_id, action, old_value, new_value, updated_by)
    VALUES (
        OLD.product_id,
        'DELETE',
        CONCAT('Deleted product: ', OLD.name, ', price=', OLD.price),
        NULL,
        CURRENT_USER()
    );
END$$

DELIMITER ;

-- ================================
-- END OF COMPLETE SCRIPT
-- ================================