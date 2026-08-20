-- ─────────────────────────────────────────────────────────────
-- ShopSight — migration for the Manage Shops (superadmin) feature
-- AND the Forgot Password / security-question recovery feature.
-- Run this ONCE if your database already existed before these updates
-- (i.e. you already ran setup_db.sql previously). Safe to skip if
-- you're setting up the database fresh — setup_db.sql already
-- includes these columns.
--
--   mysql -u root -p sales_dashboard < migrate_admin_features.sql
--
-- Each ALTER is wrapped so it won't error out if the column already
-- exists (e.g. if you re-run this by accident).
-- ─────────────────────────────────────────────────────────────
USE sales_dashboard;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'shops' AND COLUMN_NAME = 'is_active'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE shops ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1',
  'SELECT "shops.is_active already exists, skipping"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'failed_attempts'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN failed_attempts INT NOT NULL DEFAULT 0',
  'SELECT "users.failed_attempts already exists, skipping"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'locked_until'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN locked_until TIMESTAMP NULL',
  'SELECT "users.locked_until already exists, skipping"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'security_question'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN security_question VARCHAR(255) NULL',
  'SELECT "users.security_question already exists, skipping"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'security_answer_hash'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN security_answer_hash VARCHAR(255) NULL',
  'SELECT "users.security_answer_hash already exists, skipping"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'Migration complete.' AS status;
